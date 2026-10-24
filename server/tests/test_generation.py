"""Part 6: applications, the streaming generate endpoint, saved pieces and the cost ledger.

The pipeline-only tests need no database; the API tests use the real test database and a fake Groq.
"""

from __future__ import annotations

import json
import time
import uuid

import anyio
import groq
import pytest
from sqlalchemy import func, select, update

from app.core.sse import with_keepalive
from app.features.generation.models import ArtifactRow, GenerationRunRow
from app.features.generation.pipeline import stream_pack
from app.features.generation.service import GenerationService
from app.features.users.models import UserRow
from app.llm.client import GroqLLM
from app.llm.dependencies import get_llm
from app.llm.ledger import LlmCallRow
from app.llm.schemas import CareerProfile, ContactDetails, JobSpec
from server.tests.fakes import FailingGroq, FakeGroq
from server.tests.packs import ANSWERS, CONTACT, JOB, JOB_TEXT, PROFILE, RESUME, new_application

pytestmark = pytest.mark.anyio


def parse_events(body: str) -> list[tuple[str, dict]]:
    """Turn an SSE body into [(event, data)], skipping keep-alive comments."""
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if not line.startswith(":"))
        if lines:
            events.append((lines["event"], json.loads(lines["data"])))
    return events


async def count(db, *conditions) -> int:
    async with db.sessions() as session:
        return await session.scalar(select(func.count()).select_from(LlmCallRow).where(*conditions))


# --------------------------------------------------------------------------- the pipeline on its own

async def test_with_a_parsed_job_the_stream_starts_at_the_match_report():
    fake = FakeGroq({k: list(v) for k, v in ANSWERS.items()})
    pieces = [p.kind async for p in stream_pack(GroqLLM(client=fake), CareerProfile.model_validate(PROFILE),
                                                ContactDetails.model_validate(CONTACT),
                                                job=JobSpec.model_validate(JOB))]
    assert pieces[0] == "match_report" and sorted(pieces[1:]) == ["cover_letter", "outreach", "resume"]
    assert all(r["response_format"]["json_schema"]["name"] != "JobSpec" for r in fake.requests)  # no re-extraction


async def test_one_failing_piece_stops_the_others_instead_of_leaving_them_running():
    fake = FailingGroq({k: list(v) for k, v in ANSWERS.items()}, fail="CoverLetter", slow="OutreachPack")
    started = time.perf_counter()
    with pytest.raises(groq.BadRequestError):
        async for _ in stream_pack(GroqLLM(client=fake), CareerProfile.model_validate(PROFILE),
                                   ContactDetails(full_name="", email="", phone=None, city=None, links=[]),
                                   job=JobSpec.model_validate(JOB)):
            pass
    assert time.perf_counter() - started < 5  # the 30-second outreach call was cancelled, not awaited


# --------------------------------------------------------------------------- applications (the `ai` fixture is in conftest)

async def test_start_list_and_read_applications(client, sign_in, ai):
    priya = sign_in("priya@example.com")
    job_id = (await client.post("/v1/jobs", headers=priya, json={"text": JOB_TEXT})).json()["id"]

    first = await client.post("/v1/applications", headers=priya, json={"job_id": job_id})
    again = await client.post("/v1/applications", headers=priya, json={"job_id": job_id})
    stranger = await client.post("/v1/applications", headers=sign_in("jordan@example.com"), json={"job_id": job_id})

    assert first.status_code == 201 and again.status_code == 200 and again.json()["id"] == first.json()["id"]
    assert stranger.status_code == 404  # someone else's pasted job
    page = (await client.get("/v1/applications?limit=1", headers=priya)).json()
    assert [item["id"] for item in page["items"]] == [first.json()["id"]] and page["next_before"] is not None
    detail = (await client.get(f"/v1/applications/{first.json()['id']}", headers=priya)).json()
    assert detail["job"]["title"] == JOB["title"] and detail["latest_run"] is None
    assert detail["pieces"] == {"match_report": None, "resume": None, "cover_letter": None, "outreach": None}


# --------------------------------------------------------------------------- generate

async def test_generate_streams_every_piece_saves_them_and_records_every_ai_call(client, sign_in, ai, db):
    headers = sign_in("priya@example.com")
    application_id = await new_application(client, headers)
    calls_before = len(ai.requests)

    response = await client.post(f"/v1/applications/{application_id}/generate", headers=headers)

    assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
    events = parse_events(response.text)
    kinds = [event for event, _ in events]
    assert kinds[:2] == ["run", "match_report"] and kinds[-1] == "done"
    assert sorted(kinds[2:-1]) == ["cover_letter", "outreach", "resume"]
    run_id = events[0][1]["run_id"]

    detail = (await client.get(f"/v1/applications/{application_id}", headers=headers)).json()
    assert detail["latest_run"]["status"] == "succeeded" and detail["latest_run"]["cost_usd"] > 0
    assert sorted(detail["pieces"]) == ["cover_letter", "match_report", "outreach", "resume"]
    assert detail["pieces"]["resume"]["resume"]["summary"] == RESUME["summary"]

    generation_calls = len(ai.requests) - calls_before
    assert await count(db, LlmCallRow.purpose == "generation", LlmCallRow.run_id == run_id) == generation_calls
    assert await count(db, LlmCallRow.purpose == "job_extract") == 1  # Part 5's call is in the ledger too


async def test_generate_needs_a_profile_first(client, sign_in, ai):
    headers = sign_in("priya@example.com")
    application_id = await new_application(client, headers, with_profile=False)
    response = await client.post(f"/v1/applications/{application_id}/generate", headers=headers)
    assert (response.status_code, response.json()["code"]) == (422, "profile_required")


async def test_nobody_can_generate_for_someone_elses_application(client, sign_in, ai):
    application_id = await new_application(client, sign_in("priya@example.com"))
    response = await client.post(f"/v1/applications/{application_id}/generate", headers=sign_in("jordan@example.com"))
    assert response.status_code == 404


async def test_a_second_generate_while_one_is_running_is_refused(client, sign_in, ai, db):
    headers = sign_in("priya@example.com")
    application_id = await new_application(client, headers)
    async with db.sessions() as session:
        session.add(GenerationRunRow(application_id=application_id, profile_version=1, mode="deep", status="running"))
        await session.commit()

    response = await client.post(f"/v1/applications/{application_id}/generate", headers=headers)
    assert (response.status_code, response.json()["code"]) == (409, "conflict")


async def test_an_ai_failure_midway_keeps_finished_pieces_and_still_records_the_cost(api_app, client, sign_in, db):
    headers = sign_in("priya@example.com")
    api_app.dependency_overrides[get_llm] = lambda: GroqLLM(client=FakeGroq({k: list(v) for k, v in ANSWERS.items()}))
    application_id = await new_application(client, headers)
    failing = FailingGroq({k: list(v) for k, v in ANSWERS.items()}, fail="CoverLetter")
    api_app.dependency_overrides[get_llm] = lambda: GroqLLM(client=failing)

    events = parse_events((await client.post(f"/v1/applications/{application_id}/generate", headers=headers)).text)

    assert events[-1][0] == "error" and events[-1][1]["code"] == "upstream_error"
    detail = (await client.get(f"/v1/applications/{application_id}", headers=headers)).json()
    assert detail["latest_run"]["status"] == "failed" and "match_report" in detail["pieces"]
    run_id = events[0][1]["run_id"]
    assert await count(db, LlmCallRow.run_id == run_id) >= 1  # the calls that did run were paid for, and recorded


async def test_a_browser_disconnect_still_closes_the_run_and_records_what_was_paid_for(client, sign_in, ai, db):
    headers = sign_in("priya@example.com")
    application_id = await new_application(client, headers)
    async with db.sessions() as session:
        user = await session.scalar(select(UserRow).where(UserRow.email == "priya@example.com"))
        service = GenerationService(session, db)
        run = await service.prepare(user, uuid.UUID(application_id), "deep")
    llm = GroqLLM(client=FailingGroq({k: list(v) for k, v in ANSWERS.items()}, slow="OutreachPack"))

    received = []
    # Starlette cancels a disconnected request like this: the cancellation keeps firing at every await.
    with anyio.move_on_after(1.0):
        async for chunk in with_keepalive(service.stream(run, llm), interval_seconds=5):
            received.append(chunk)

    assert any(chunk.startswith("event: match_report") for chunk in received)
    async with db.sessions() as session:
        row = await session.get(GenerationRunRow, run.run_id)
    assert (row.status, row.error) == ("cancelled", "client_disconnected") and row.finished_at is not None
    assert row.cost_usd > 0 and await count(db, LlmCallRow.run_id == run.run_id) == len(llm.calls) > 0


async def test_resume_upload_is_recorded_in_the_ledger_too(api_app, client, sign_in, db):
    api_app.dependency_overrides[get_llm] = lambda: GroqLLM(client=FakeGroq({"CareerProfile": [PROFILE]}))
    resume = b"Jordan Rivera\njordan.rivera@example.com\n\nEXPERIENCE\nBuilt Go services for card payments."
    response = await client.post("/v1/profile/resume", headers=sign_in("jordan@example.com"),
                                 files={"file": ("resume.txt", resume, "text/plain")})
    assert response.status_code == 201
    assert await count(db, LlmCallRow.purpose == "resume_parse") == 1


async def test_a_saved_piece_that_no_longer_fits_the_schema_is_left_out_not_a_500(client, sign_in, ai, db):
    headers = sign_in("priya@example.com")
    application_id = await new_application(client, headers)
    await client.post(f"/v1/applications/{application_id}/generate", headers=headers)
    async with db.sessions() as session:  # an older version saved the cover letter without `findings`
        await session.execute(update(ArtifactRow).where(ArtifactRow.kind == "cover_letter").values(content={"letter": {}}))
        await session.commit()

    response = await client.get(f"/v1/applications/{application_id}", headers=headers)

    assert response.status_code == 200
    pieces = response.json()["pieces"]
    assert pieces["cover_letter"] is None and pieces["resume"]["resume"]["summary"] == RESUME["summary"]
