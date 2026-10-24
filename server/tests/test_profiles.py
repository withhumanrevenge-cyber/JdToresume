"""Part 4: resume upload, versioned profile edits, contact details (real database, fake Groq)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.llm.client import GroqLLM
from app.llm.dependencies import get_llm
from server.tests.fakes import FakeGroq

pytestmark = pytest.mark.anyio

PARSED_PROFILE = json.loads((Path(__file__).parent / "fixtures" / "sample_profile.json").read_text(encoding="utf-8"))
RESUME_TEXT = """Jordan Rivera | Backend Software Engineer
jordan.rivera@example.com · +1 (555) 010-4477 · github.com/jrivera-example · Austin, TX

EXPERIENCE
Senior Software Engineer, Northwind Payments    Mar 2022 - Present
- Built Go services for card authorisation handling 1,200 requests per second
"""


@pytest.fixture
def fake_groq(api_app) -> FakeGroq:
    """Replace the real LLM with a fake that 'parses' every resume into the sample profile."""
    fake = FakeGroq({"CareerProfile": [PARSED_PROFILE]})
    api_app.dependency_overrides[get_llm] = lambda: GroqLLM(client=fake)
    return fake


async def upload(client, headers, *, name="resume.txt", content: bytes = RESUME_TEXT.encode()):
    return await client.post("/v1/profile/resume", headers=headers, files={"file": (name, content, "text/plain")})


# --------------------------------------------------------------------------- upload

async def test_upload_creates_version_1_and_contact_details_without_sending_them_to_the_ai(client, sign_in, fake_groq):
    response = await upload(client, sign_in("jordan@example.com"))

    assert response.status_code == 201
    body = response.json()
    assert body["profile"]["version"] == 1
    assert body["profile"]["profile"]["headline"] == "Backend Software Engineer"
    assert body["contact"]["full_name"] == "Jordan Rivera"
    assert body["contact"]["email"] == "jordan.rivera@example.com"
    # What actually went to the AI: placeholders, never the person's details.
    sent = fake_groq.requests[0]["messages"][1]["content"]
    assert "jordan.rivera@example.com" not in sent and "010-4477" not in sent and "Jordan Rivera" not in sent
    assert "{{EMAIL}}" in sent and "{{FULL_NAME}}" in sent


async def test_a_new_upload_adds_a_version_and_keeps_confirmed_contact_details(client, sign_in, fake_groq):
    headers = sign_in("jordan@example.com")
    await client.put("/v1/profile/contact", headers=headers,
                     json={"full_name": "Jordan A. Rivera", "email": "jordan@example.com"})

    response = await upload(client, headers)

    assert response.json()["profile"]["version"] == 1
    assert response.json()["contact"]["full_name"] == "Jordan A. Rivera"  # not overwritten by what was detected
    assert response.json()["detected_contact"]["full_name"] == "Jordan Rivera"
    assert (await upload(client, headers)).json()["profile"]["version"] == 2


@pytest.mark.parametrize(("name", "content", "status", "code"), [
    pytest.param("resume.docx", b"PK\x03\x04", 422, "invalid_input", id="unsupported-type"),
    pytest.param("resume.txt", b"   \n\t ", 422, "invalid_input", id="no-text"),
    pytest.param("resume.txt", b"a" * (5 * 1024 * 1024 + 1), 413, "payload_too_large", id="over-5MB"),
])
async def test_bad_uploads_are_rejected_before_calling_the_ai(client, sign_in, fake_groq, name, content, status, code):
    response = await upload(client, sign_in("jordan@example.com"), name=name, content=content)
    assert (response.status_code, response.json()["code"]) == (status, code)
    assert fake_groq.requests == []


async def test_upload_answers_503_when_the_ai_is_not_configured(client, sign_in):
    response = await upload(client, sign_in("jordan@example.com"))
    assert (response.status_code, response.json()["code"]) == (503, "service_unavailable")


async def test_an_inconsistent_ai_result_is_a_502_and_nothing_is_saved(api_app, client, sign_in):
    broken = copy.deepcopy(PARSED_PROFILE)
    broken["experience"][1]["facts"][0]["id"] = broken["experience"][0]["facts"][0]["id"]  # duplicate fact id
    api_app.dependency_overrides[get_llm] = lambda: GroqLLM(client=FakeGroq({"CareerProfile": [broken]}))
    headers = sign_in("jordan@example.com")

    response = await upload(client, headers)

    assert (response.status_code, response.json()["code"]) == (502, "upstream_error")
    assert (await client.get("/v1/profile", headers=headers)).status_code == 404


# --------------------------------------------------------------------------- reading and editing the profile

async def test_editing_creates_new_versions_and_refuses_to_overwrite_a_newer_one(client, sign_in):
    headers = sign_in("jordan@example.com")
    assert (await client.get("/v1/profile", headers=headers)).status_code == 404

    first = await client.put("/v1/profile", headers=headers, json={"base_version": 0, "profile": PARSED_PROFILE})
    edited = {**PARSED_PROFILE, "headline": "Staff Backend Engineer"}
    second = await client.put("/v1/profile", headers=headers, json={"base_version": 1, "profile": edited})
    stale = await client.put("/v1/profile", headers=headers, json={"base_version": 1, "profile": PARSED_PROFILE})

    assert (first.json()["version"], second.json()["version"]) == (1, 2)
    assert stale.status_code == 409 and stale.json()["details"] == {"current_version": 2}
    latest = (await client.get("/v1/profile", headers=headers)).json()
    assert (latest["version"], latest["profile"]["headline"]) == (2, "Staff Backend Engineer")


async def test_an_inconsistent_edit_lists_its_problems(client, sign_in):
    broken = copy.deepcopy(PARSED_PROFILE)
    broken["skills"][0]["evidence_fact_ids"] = ["f-does-not-exist"]
    broken["experience"][0]["start"] = "March 2022"

    response = await client.put("/v1/profile", headers=sign_in("jordan@example.com"),
                                json={"base_version": 0, "profile": broken})

    assert (response.status_code, response.json()["code"]) == (422, "invalid_input")
    problems = " | ".join(response.json()["details"]["problems"])
    assert "unknown fact 'f-does-not-exist'" in problems and "should look like 2023-06" in problems


async def test_people_only_ever_see_their_own_profile(client, sign_in, fake_groq):
    await upload(client, sign_in("jordan@example.com"))
    response = await client.get("/v1/profile", headers=sign_in("someone-else@example.com"))
    assert response.status_code == 404


# --------------------------------------------------------------------------- contact details

async def test_contact_details_can_be_created_read_and_replaced(client, sign_in):
    headers = sign_in("jordan@example.com")
    assert (await client.get("/v1/profile/contact", headers=headers)).status_code == 404

    created = await client.put("/v1/profile/contact", headers=headers, json={
        "full_name": "Jordan Rivera", "email": "jordan@example.com", "phone": "+1 555 010 4477",
        "city": "Austin, TX", "links": ["github.com/jrivera-example"],
    })
    replaced = await client.put("/v1/profile/contact", headers=headers,
                                json={"full_name": "Jordan Rivera", "email": "j.rivera@example.com"})
    read = await client.get("/v1/profile/contact", headers=headers)

    assert created.status_code == 200 and created.json()["city"] == "Austin, TX"
    assert replaced.status_code == 200 and replaced.json()["city"] is None  # a replace, not a merge
    assert read.json()["email"] == "j.rivera@example.com" and read.json()["links"] == []
    assert read.json()["updated_at"] >= created.json()["updated_at"]


@pytest.mark.parametrize("body", [
    {"full_name": "", "email": "jordan@example.com"},
    {"full_name": "Jordan Rivera", "email": "not-an-email"},
    {"full_name": "Jordan Rivera", "email": "jordan@example.com", "surprise": "extra field"},
])
async def test_invalid_contact_details_are_rejected(client, sign_in, body):
    response = await client.put("/v1/profile/contact", headers=sign_in("jordan@example.com"), json=body)
    assert (response.status_code, response.json()["code"]) == (422, "validation_error")
