"""One complete application pack as the fake AI writes it, shared by the generation and document tests."""

from __future__ import annotations

import json
from pathlib import Path

from app.llm.schemas import CareerProfile

FIXTURES = Path(__file__).parent / "fixtures"
PROFILE = json.loads((FIXTURES / "sample_profile.json").read_text(encoding="utf-8"))
JOB = json.loads((FIXTURES / "sample_job.json").read_text(encoding="utf-8"))
RESUME = json.loads((FIXTURES / "sample_tailored_resume.json").read_text(encoding="utf-8"))
CONTACT = json.loads((FIXTURES / "sample_contact.json").read_text(encoding="utf-8"))
FACTS = list(CareerProfile.model_validate(PROFILE).all_facts())
JOB_TEXT = "Senior Backend Engineer at Kestrel Pay. Build payment services in Go. " * 4

# Output schema name -> the answers the fake Groq gives, in order (see fakes.FakeGroq).
ANSWERS = {
    "JobSpec": [JOB],
    "MatchReport": [{
        "requirement_matches": [{"requirement_id": r["id"], "status": "evidenced", "evidence_fact_ids": FACTS[:1],
                                 "note": "covered"} for r in JOB["requirements"]],
        "fact_relevance": [{"fact_id": f, "score": 2} for f in FACTS],
        "keyword_plan": ["Go"], "angle": "Payments backend engineer.", "gap_questions": [],
    }],
    "TailoredResume": [RESUME],
    "VerifyReport": [{"violations": []}],
    "CoverLetter": [{"salutation": "Dear Hiring Team,", "paragraphs": ["word " * 260], "closing": "Best regards,",
                     "source_fact_ids": FACTS[:1], "addressed_gap_requirement_ids": []}],
    "OutreachPack": [{"recruiter_email_subject": "Backend Engineer", "recruiter_email_body": "Hi. {{FULL_NAME}}",
                      "linkedin_note": "Hello", "referral_ask": "Could you refer me? [job link]",
                      "follow_up": "Following up.", "source_fact_ids": FACTS[:1]}],
}


async def new_application(client, headers, *, with_profile: bool = True) -> str:
    """Save the sample profile (optionally), add the sample job from pasted text, and start an application."""
    if with_profile:
        assert (await client.put("/v1/profile", headers=headers, json={"base_version": 0, "profile": PROFILE})).status_code == 200
    job_id = (await client.post("/v1/jobs", headers=headers, json={"text": JOB_TEXT})).json()["id"]
    return (await client.post("/v1/applications", headers=headers, json={"job_id": job_id})).json()["id"]
