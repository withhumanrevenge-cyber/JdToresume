"""Free match scan: POST /v1/scans and GET /v1/scans (real database, fake Groq)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.features.billing.plans import SCANS_PER_DAY
from app.features.scans.models import ScanRow
from app.features.scans.service import profile_text
from app.llm.client import GroqLLM
from app.llm.dependencies import get_llm
from app.llm.ledger import LlmCallRow
from app.llm.router import GPT_OSS_20B
from app.llm.schemas import CareerProfile
from server.tests.fakes import FailingGroq
from server.tests.packs import ANSWERS, CONTACT, JOB, JOB_TEXT, PROFILE

pytestmark = pytest.mark.anyio


async def _job(client, headers, with_profile: bool = True) -> str:
    if with_profile:
        assert (await client.put("/v1/profile", headers=headers, json={"base_version": 0, "profile": PROFILE})).status_code == 200
    return (await client.post("/v1/jobs", headers=headers, json={"text": JOB_TEXT})).json()["id"]


async def _count(db, model, *where) -> int:
    async with db.sessions() as session:
        return await session.scalar(select(func.count()).select_from(model).where(*where))


async def test_a_scan_matches_the_profile_without_spending_a_pack(client, sign_in, ai, db):
    headers = sign_in("jordan@example.com")
    assert (await client.put("/v1/profile/contact", headers=headers, json=CONTACT)).status_code == 200
    job_id = await _job(client, headers)
    requests_before = len(ai.requests)

    response = await client.post("/v1/scans", headers=headers, json={"job_id": job_id})
    plan = (await client.get("/v1/me/plan", headers=headers)).json()

    assert response.status_code == 201
    scan = response.json()
    assert scan["match_report"]["requirement_matches"] and scan["profile_version"] == 1 and not scan["stale"]
    assert sorted(scan["keywords_found"] + scan["keywords_missing"]) == sorted(k["term"] for k in JOB["keywords"])
    assert 0 <= scan["keyword_coverage"] <= 1 and scan["scans_left_today"] == SCANS_PER_DAY - 1
    sent = ai.requests[requests_before:]
    assert [r["model"] for r in sent] == [GPT_OSS_20B]  # one Quick match step, nothing generated
    assert all(CONTACT["email"] not in str(r["messages"]) for r in sent)  # contact details stay out of the AI
    assert (plan["packs"]["used"], plan["deep_credits"]) == (0, 1)  # no pack spent
    assert await _count(db, LlmCallRow, LlmCallRow.purpose == "scan") == 1


async def test_a_repeat_scan_is_free_until_the_profile_changes(client, sign_in, ai):
    headers = sign_in("jordan@example.com")
    job_id = await _job(client, headers)
    first = (await client.post("/v1/scans", headers=headers, json={"job_id": job_id})).json()
    requests_before = len(ai.requests)

    again = await client.post("/v1/scans", headers=headers, json={"job_id": job_id})
    assert again.status_code == 200 and again.json()["id"] == first["id"] and len(ai.requests) == requests_before

    edited = {**PROFILE, "headline": "Backend engineer, payments"}
    assert (await client.put("/v1/profile", headers=headers, json={"base_version": 1, "profile": edited})).status_code == 200
    stale = (await client.get(f"/v1/scans?job_id={job_id}", headers=headers)).json()
    rescanned = await client.post("/v1/scans", headers=headers, json={"job_id": job_id})

    assert stale["id"] == first["id"] and stale["stale"] is True
    assert rescanned.status_code == 201 and rescanned.json()["profile_version"] == 2 and not rescanned.json()["stale"]


async def test_the_daily_fair_use_limit(client, sign_in, ai, db):
    headers = sign_in("jordan@example.com")
    job_id = await _job(client, headers)
    user_id = uuid.UUID((await client.get("/v1/me", headers=headers)).json()["id"])
    async with db.sessions() as session:  # today's scans of other jobs, already used up
        session.add_all(ScanRow(user_id=user_id, job_id=uuid.UUID(job_id), profile_version=0, mode="quick", result={})
                        for _ in range(SCANS_PER_DAY))
        await session.commit()

    refused = await client.post("/v1/scans", headers=headers, json={"job_id": job_id})

    assert (refused.status_code, refused.json()["code"]) == (429, "scan_limit")
    assert int(refused.headers["retry-after"]) > 0 and "retry_at" in refused.json()["details"]


async def test_scans_need_a_profile_and_your_own_job(client, sign_in, ai):
    jordan, priya = sign_in("jordan@example.com"), sign_in("priya@example.com")
    job_id = await _job(client, jordan, with_profile=False)

    no_profile = await client.post("/v1/scans", headers=jordan, json={"job_id": job_id})
    not_scanned = await client.get(f"/v1/scans?job_id={job_id}", headers=jordan)
    assert (await client.put("/v1/profile", headers=priya, json={"base_version": 0, "profile": PROFILE})).status_code == 200
    strangers_job = await client.post("/v1/scans", headers=priya, json={"job_id": job_id})  # a pasted job is private

    assert (no_profile.status_code, no_profile.json()["code"]) == (422, "profile_required")
    assert (not_scanned.status_code, not_scanned.json()["code"]) == (404, "not_scanned")
    assert (strangers_job.status_code, strangers_job.json()["code"]) == (404, "not_found")


async def test_an_ai_failure_is_a_clean_502_and_saves_nothing(api_app, client, sign_in, ai, db):
    headers = sign_in("jordan@example.com")
    job_id = await _job(client, headers)
    failing = FailingGroq({kind: list(answers) for kind, answers in ANSWERS.items()}, fail="MatchReport")
    api_app.dependency_overrides[get_llm] = lambda: GroqLLM(client=failing)

    response = await client.post("/v1/scans", headers=headers, json={"job_id": job_id})

    assert (response.status_code, response.json()["code"]) == (502, "upstream_error")
    assert await _count(db, ScanRow) == 0
    assert await _count(db, LlmCallRow, LlmCallRow.purpose == "scan") == 0  # the call failed before it was billed


async def test_scans_are_in_the_account_export(client, sign_in, ai):
    headers = sign_in("jordan@example.com")
    job_id = await _job(client, headers)
    await client.post("/v1/scans", headers=headers, json={"job_id": job_id})

    exported = (await client.get("/v1/me/export", headers=headers)).json()

    assert [(s["job_id"], s["profile_version"]) for s in exported["scans"]] == [(job_id, 1)]


def test_the_profile_text_covers_what_a_resume_can_truthfully_say():
    profile = CareerProfile.model_validate(PROFILE)
    text = profile_text(profile)

    role = profile.experience[0]
    assert role.title in text and role.company in text  # company names are evidence too (e.g. a domain)
    assert all(skill.name in text for skill in profile.skills)
    assert all(fact.text in text for fact in profile.all_facts().values())
