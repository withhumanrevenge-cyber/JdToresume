"""Part 5: POST /v1/jobs and GET /v1/jobs/{id} (real database, fake network, fake Groq)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.features.jobs.dependencies import get_fetcher
from app.llm.client import GroqLLM
from app.llm.dependencies import get_llm
from server.tests import job_pages as pages
from server.tests.fakes import FakeGroq

pytestmark = pytest.mark.anyio

JOB_SPEC = json.loads((Path(__file__).parent / "fixtures" / "sample_job.json").read_text(encoding="utf-8"))
JOB_TEXT = ("Senior Backend Engineer at Kestrel Pay. You will build payment services in Go. "
            "Requirements: 5+ years of backend experience, Go, Kafka, PostgreSQL. Nice to have: Kubernetes.")


@pytest.fixture
def ai(api_app) -> FakeGroq:
    fake = FakeGroq({"JobSpec": [JOB_SPEC]})
    api_app.dependency_overrides[get_llm] = lambda: GroqLLM(client=fake)
    return fake


@pytest.fixture
def internet(api_app) -> list[str]:
    """Serve the sample job sites; returns the list of URLs the server actually fetched."""
    seen: list[str] = []
    fetcher = pages.job_site_fetcher(seen)
    api_app.dependency_overrides[get_fetcher] = lambda: fetcher
    return seen


# --------------------------------------------------------------------------- pasted text

async def test_pasted_text_becomes_a_private_job_and_is_reused_when_pasted_again(client, sign_in, ai):
    headers = sign_in("priya@example.com")
    first = await client.post("/v1/jobs", headers=headers, json={"text": JOB_TEXT})
    again = await client.post("/v1/jobs", headers=headers, json={"text": "  " + JOB_TEXT.upper() + "\n"})

    assert first.status_code == 201
    assert first.json()["source"] == "text" and first.json()["url"] is None
    assert first.json()["title"] == JOB_SPEC["title"] and first.json()["reused"] is False
    assert again.status_code == 200 and again.json()["id"] == first.json()["id"] and again.json()["reused"] is True
    assert len(ai.requests) == 1  # the second paste cost nothing
    assert JOB_TEXT in ai.requests[0]["messages"][1]["content"]  # the posting went in as data, inside its own block


async def test_too_short_text_is_rejected_without_calling_the_ai(client, sign_in, ai):
    response = await client.post("/v1/jobs", headers=sign_in("priya@example.com"), json={"text": "Backend role"})
    assert (response.status_code, response.json()["code"]) == (422, "invalid_input")
    assert ai.requests == []


# --------------------------------------------------------------------------- links

async def test_a_public_link_becomes_a_shared_job_that_everyone_reuses(client, sign_in, ai, internet):
    first = await client.post("/v1/jobs", headers=sign_in("priya@example.com"), json={"url": pages.GREENHOUSE_URL})
    # Another person, the same link with tracking junk on it.
    second = await client.post("/v1/jobs", headers=sign_in("jordan@example.com"),
                               json={"url": pages.GREENHOUSE_URL + "?utm_source=linkedin&gh_src=x"})

    assert first.status_code == 201
    assert (first.json()["source"], first.json()["ats_vendor"]) == ("ats_feed", "greenhouse")
    assert first.json()["url"] == pages.GREENHOUSE_URL
    assert second.status_code == 200 and second.json()["id"] == first.json()["id"]
    assert internet == [pages.GREENHOUSE_API] and len(ai.requests) == 1  # fetched and parsed exactly once


async def test_embedded_job_data_is_read_from_ordinary_career_pages(client, sign_in, ai, internet):
    response = await client.post("/v1/jobs", headers=sign_in("priya@example.com"), json={"url": pages.CAREERS_URL})
    assert response.status_code == 201 and response.json()["source"] == "embedded_data"
    assert "Site Reliability Engineer" in ai.requests[0]["messages"][1]["content"]


@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/jobs/view/4012345678",
    "https://in.indeed.com/viewjob?jk=abc123",
    "https://www.naukri.com/job-listings-backend-engineer-123",
])
async def test_linkedin_indeed_and_naukri_are_never_fetched(client, sign_in, ai, internet, url):
    response = await client.post("/v1/jobs", headers=sign_in("priya@example.com"), json={"url": url})

    assert (response.status_code, response.json()["code"]) == (422, "client_only_source")
    assert "paste the text" in response.json()["message"]
    assert internet == [] and ai.requests == []  # no network call, no AI call


async def test_a_page_without_a_job_description_is_a_clear_422(client, sign_in, ai, internet):
    response = await client.post("/v1/jobs", headers=sign_in("priya@example.com"), json={"url": pages.LOGIN_WALL_URL})
    assert (response.status_code, response.json()["code"]) == (422, "job_not_readable")
    assert ai.requests == []


@pytest.mark.parametrize("body", [{}, {"url": pages.GREENHOUSE_URL, "text": JOB_TEXT}, {"url": "   "}])
async def test_send_exactly_one_of_url_or_text(client, sign_in, ai, body):
    response = await client.post("/v1/jobs", headers=sign_in("priya@example.com"), json=body)
    assert (response.status_code, response.json()["code"]) == (422, "validation_error")


async def test_adding_a_job_needs_the_ai_service(client, sign_in):
    response = await client.post("/v1/jobs", headers=sign_in("priya@example.com"), json={"text": JOB_TEXT})
    assert (response.status_code, response.json()["code"]) == (503, "service_unavailable")


# --------------------------------------------------------------------------- reading a job back

async def test_who_can_see_which_job(client, sign_in, ai, internet):
    priya, jordan = sign_in("priya@example.com"), sign_in("jordan@example.com")
    private_id = (await client.post("/v1/jobs", headers=priya, json={"text": JOB_TEXT})).json()["id"]
    shared_id = (await client.post("/v1/jobs", headers=priya, json={"url": pages.LEVER_URL})).json()["id"]

    assert (await client.get(f"/v1/jobs/{private_id}", headers=priya)).status_code == 200
    assert (await client.get(f"/v1/jobs/{private_id}", headers=jordan)).status_code == 404  # someone else's paste
    assert (await client.get(f"/v1/jobs/{shared_id}", headers=jordan)).status_code == 200  # public link: shared
    assert (await client.get(f"/v1/jobs/{uuid.uuid4()}", headers=jordan)).status_code == 404
