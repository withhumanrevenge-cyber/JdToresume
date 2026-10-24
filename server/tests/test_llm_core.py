"""Tests for schemas, prompts, PII guard, linters, the Groq client wrapper and the pipeline. No network."""

from __future__ import annotations

import asyncio
import json

import groq
import httpx
import pytest

from app.features.generation.pipeline import generate_pack
from app.llm.client import BudgetExceeded, GroqLLM, StepTruncated
from app.llm.pii import PIILeak, assert_no_contact_pii, restore_placeholders
from app.llm.prompts import global_policy, prompt_version
from app.llm.router import GPT_OSS_120B, QWEN_38_27B, step_config
from app.llm.schemas import (
    CareerProfile, ContactDetails, CoverLetter, JobSpec, MatchReport, OutreachPack, PairwiseVerdict,
    TailoredResume, VerifyReport, strict_json_schema,
)
from app.core.text import term_present
from app.llm.style.linters import lint_resume
from server.tests.fakes import FakeGroq

PROFILE = CareerProfile.model_validate({
    "schema_version": 1,
    "headline": "Backend engineer",
    "summary_facts": [],
    "experience": [{
        "id": "e-acme", "company": "Acme Freight", "title": "Software Engineer", "location": "Austin, TX",
        "start": "2021-03", "end": None,
        "facts": [
            {"id": "f-acme-1", "text": "Built Java/Spring services handling 2M shipment events per day",
             "metrics": ["2M events/day"], "skills": ["Java", "Spring Boot"], "source": "upload"},
            {"id": "f-acme-2", "text": "Cut p95 API latency by 40% by adding Redis caching",
             "metrics": ["40%"], "skills": ["Redis"], "source": "upload"},
        ],
    }],
    "projects": [], "education": [], "certifications": [],
    "skills": [{"name": "Java", "evidence_fact_ids": ["f-acme-1"]}, {"name": "Redis", "evidence_fact_ids": ["f-acme-2"]},
               {"name": "Spring Boot", "evidence_fact_ids": ["f-acme-1"]}],
    "languages": ["English"], "awards": [],
    "preferences": {"target_roles": ["Backend Engineer"], "region": "US", "page_limit": 1, "spelling": "en-US"},
    "style": {"avg_bullet_words": 18, "number_style": "digits", "voice_samples": ["Cut p95 API latency by 40% by adding Redis caching"], "notes": ""},
})
CONTACT = ContactDetails(full_name="Jordan Example", email="jordan@example.com", phone="+1 555-0142",
                         city="Austin, TX", links=["linkedin.com/in/jordan-example"])


def resume(**overrides) -> TailoredResume:
    data = {
        "summary": "Backend engineer building high-volume Java services.",
        "summary_source_fact_ids": ["f-acme-1"],
        "section_order": ["summary", "experience", "skills"],
        "experience": [{"experience_id": "e-acme", "bullets": [
            {"text": "Built Java and Spring Boot services that process 2M shipment events per day for dispatch",
             "source_fact_ids": ["f-acme-1"], "targets_requirement_ids": ["r1"]},
            {"text": "Cut p95 API latency 40% by introducing Redis caching in front of the order service",
             "source_fact_ids": ["f-acme-2"], "targets_requirement_ids": ["r2"]},
        ]}],
        "projects": [], "education": [],
        "skill_groups": [{"label": "Backend", "skills": ["Java", "Spring Boot", "Redis"]}],
        "certification_ids": [],
    }
    data.update(overrides)
    return TailoredResume.model_validate(data)


# --------------------------------------------------------------------------- schemas & prompts

@pytest.mark.parametrize("model", [CareerProfile, JobSpec, MatchReport, TailoredResume, VerifyReport,
                                   CoverLetter, OutreachPack, PairwiseVerdict])
def test_strict_schema_closes_every_object(model):
    def walk(node):
        if isinstance(node, dict):
            if "properties" in node:
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for key in ("default", "title", "const"):
                assert key not in node
            for key, value in node.items():
                if key in ("properties", "$defs"):  # name -> schema maps: field names are not keywords
                    for sub in value.values():
                        walk(sub)
                else:
                    walk(value)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(strict_json_schema(model))


def test_property_named_title_survives():
    assert "title" in strict_json_schema(JobSpec)["properties"]


def test_global_policy_injects_banned_phrases_and_versions_are_stable():
    policy = global_policy()
    assert "{{BANNED_PHRASES}}" not in policy and '"spearheaded"' in policy
    assert '"furthermore"' not in policy  # soft phrases are not banned outright
    assert prompt_version("resume_tailor") == prompt_version("resume_tailor")
    assert prompt_version("resume_tailor") != prompt_version("verify")


def test_router_override_and_unknown_model():
    assert step_config("verify", "quick").model == "openai/gpt-oss-20b"
    assert step_config("verify", "deep", QWEN_38_27B).model == QWEN_38_27B
    with pytest.raises(ValueError):
        step_config("verify", "deep", "made-up/model")


# --------------------------------------------------------------------------- PII

def test_pii_guard_blocks_user_contact_but_allows_recruiter_email():
    assert_no_contact_pii("Send resumes to talent@kestrelpay.example", CONTACT)
    for leak in ("jordan@example.com", "call 555-0142", "Jordan Example wrote", "linkedin.com/in/jordan-example"):
        with pytest.raises(PIILeak):
            assert_no_contact_pii(leak, CONTACT)


def test_redact_profile_strips_own_links_and_contact_strings():
    from app.llm.pii import redact_profile
    profile = PROFILE.model_copy(deep=True)
    profile.projects = [CareerProfile.model_validate({**PROFILE.model_dump(), "projects": [{
        "id": "p-x", "name": "X", "link": "https://github.com/jordan-example/x", "start": None, "end": None,
        "facts": [{"id": "f-p-1", "text": "Open-sourced at linkedin.com/in/jordan-example and jordan@example.com",
                   "metrics": [], "skills": [], "source": "upload"}]}]}).projects[0]]
    data = redact_profile(profile, CONTACT)
    text = json.dumps(data)
    assert data["projects"][0]["link"] is None
    assert "jordan@example.com" not in text and "linkedin.com/in/jordan-example" not in text
    assert "{{EMAIL}}" in text and "{{LINK_0}}" in text
    assert_no_contact_pii(text, CONTACT)


def test_skill_implications_allow_implied_but_not_swapped_tools():
    from app.llm.style.linters import supported_skills
    profile = PROFILE.model_copy(deep=True)
    profile.skills = [*profile.skills, *CareerProfile.model_validate({**PROFILE.model_dump(), "skills": [
        {"name": "PostgreSQL", "evidence_fact_ids": []}, {"name": "RabbitMQ", "evidence_fact_ids": []}]}).skills]
    known = supported_skills(profile)
    assert "sql" in known and "jvm" in known  # PostgreSQL -> SQL, Java -> JVM
    assert "kafka" not in known  # RabbitMQ never implies Kafka
    ok = resume(skill_groups=[{"label": "Data", "skills": ["SQL", "PostgreSQL", "Java"]}])
    assert not [f for f in lint_resume(ok, profile) if f.check == "new_skill"]


def test_restore_placeholders():
    assert restore_placeholders("Best, {{FULL_NAME}} ({{EMAIL}})", CONTACT) == "Best, Jordan Example (jordan@example.com)"


# --------------------------------------------------------------------------- linters

def test_clean_resume_has_no_high_findings():
    assert [f for f in lint_resume(resume(), PROFILE) if f.severity == "high"] == []


def test_inflated_number_unknown_fact_and_new_skill_are_high():
    bad = resume(experience=[{"experience_id": "e-acme", "bullets": [
        {"text": "Built Java services processing 5M events per day", "source_fact_ids": ["f-acme-1"], "targets_requirement_ids": []},
        {"text": "Owned Kafka streaming for dispatch at scale", "source_fact_ids": ["f-ghost"], "targets_requirement_ids": []},
    ]}], skill_groups=[{"label": "Backend", "skills": ["Java", "Kafka"]}])
    checks = {(f.check, f.severity) for f in lint_resume(bad, PROFILE)}
    assert ("numbers", "high") in checks
    assert ("provenance", "high") in checks
    assert ("new_skill", "high") in checks


def test_unknown_experience_id_and_banned_phrase():
    bad = resume(experience=[{"experience_id": "e-nope", "bullets": [
        {"text": "Spearheaded Java services handling 2M shipment events per day", "source_fact_ids": ["f-acme-1"], "targets_requirement_ids": []}]}])
    checks = {(f.check, f.severity) for f in lint_resume(bad, PROFILE)}
    assert ("reference", "high") in checks
    assert ("banned_phrase", "medium") in checks


def test_term_in_word_boundaries():
    assert term_present("Java", "Java and Spring") and not term_present("Java", "JavaScript only")
    assert term_present("Go", "Go, Kafka") and not term_present("Go", "go-live support")
    assert term_present("C++", "Modern C++ code") and term_present("CI/CD", "built CI/CD pipelines")


# --------------------------------------------------------------------------- resume parsing (local part)

RAW_RESUME = """Priya Example | Backend Engineer
priya.example@example.com · +91 90000 01234 · linkedin.com/in/priya-example · github.com/priya-example
Bengaluru, India

EXPERIENCE
Software Engineer, Northwind Logistics    Jun 2021 - Present
- Built Java/Spring services handling 2M shipment events per day
"""


def test_split_contact_redacts_before_llm():
    from app.features.profiles.parse import split_contact
    contact, redacted = split_contact(RAW_RESUME)
    assert contact.full_name == "Priya Example"
    assert contact.email == "priya.example@example.com"
    assert contact.phone and contact.phone.replace(" ", "").endswith("9000001234")
    assert "linkedin.com/in/priya-example" in contact.links and "github.com/priya-example" in contact.links
    assert_no_contact_pii(redacted, contact)  # nothing of the user's left in what we would send
    assert "2M shipment events" in redacted and "Jun 2021 - Present" in redacted


def test_parse_step_is_routed():
    assert step_config("resume_parse").model == GPT_OSS_120B
    assert prompt_version("resume_parse").startswith("resume_parse@")


UW = {"id": "ed-uw", "institution": "University of Washington", "degree": "B.S.", "field": "Computer Science",
      "start": "2015-01", "end": "2019-01", "grade": None, "facts": []}


def with_education(**dates) -> CareerProfile:
    return CareerProfile.model_validate({**PROFILE.model_dump(), "education": [{**UW, **dates}]})


def test_a_year_only_date_is_parsed_as_just_the_year():
    """Seen live on 2026-10-22: "(2015 - 2019)" came back as 2015-01 / 2019-01 and showed as "Jan 2019"."""
    from app.features.profiles.consistency import find_problems
    from app.features.profiles.parse import parse_resume_text
    text = RAW_RESUME + "\nEDUCATION\nB.S. Computer Science, University of Washington (2015 - 2019)\n"
    parsed = with_education().model_dump()  # what the model returned: a January it couldn't have seen

    profile, _ = asyncio.run(parse_resume_text(GroqLLM(client=FakeGroq({"CareerProfile": [parsed]})), text))

    assert (profile.education[0].start, profile.education[0].end) == ("2015", "2019")
    assert profile.experience[0].start == "2021-03"  # a real month is left alone
    assert find_problems(profile) == []


@pytest.mark.parametrize(("source", "end"), [
    ("Jan 2019 - Present", "2019-01"),
    ("January – March 2019", "2019-01"),
    ("Jan. '19 - Mar. '20", "2019-01"),
    ("01/2019 - 03/2020", "2019-01"),
    ("2019-01 to 2020-03", "2019-01"),
    ("2015 - 2019", "2019"),
    ("Jan 2018 - 2019", "2019"),
    ("2011 – 2019", "2019"),
])
def test_january_is_kept_only_when_the_resume_shows_it(source, end):
    from app.features.profiles.parse import drop_unseen_january
    assert drop_unseen_january(with_education(start=None), source).education[0].end == end


def test_year_only_dates_are_consistent_and_compared_at_the_coarser_precision():
    from app.features.profiles.consistency import find_problems
    assert find_problems(with_education(start="2015", end="2019")) == []
    assert find_problems(with_education(start="2019-06", end="2019")) == []  # within 2019, not backwards
    assert find_problems(with_education(start="2019", end="2019-06")) == []
    assert find_problems(with_education(start="2019-06", end="2018")) == [
        "education ed-uw: ends (2018) before it starts (2019-06)"]
    assert find_problems(with_education(start="Fall 2015", end="2019")) == [
        "education ed-uw: start date 'Fall 2015' should look like 2023-06, or 2023 if the month isn't known"]
    cert = {"id": "c-aws", "name": "AWS Certified Developer", "issuer": "Amazon Web Services", "date": "April 2023"}
    profile = CareerProfile.model_validate({**PROFILE.model_dump(), "certifications": [cert]})
    assert find_problems(profile) == [
        "certification c-aws: date 'April 2023' should look like 2023-06, or 2023 if the month isn't known"]


# --------------------------------------------------------------------------- client & pipeline with a fake Groq

JOB = {"title": "Backend Engineer", "company": "Kestrel Pay", "location": None, "remote_policy": "remote",
       "seniority": "mid", "employment_type": "full_time", "visa_sponsorship": "unknown", "salary": None,
       "requirements": [{"id": "r1", "text": "Java", "kind": "skill", "tier": "basic", "evidence_terms": ["Java"]},
                        {"id": "r2", "text": "Kafka", "kind": "tool", "tier": "basic", "evidence_terms": ["Kafka"]}],
       "responsibilities": [], "keywords": [], "company_signals": [], "application_questions": [],
       "language": "en", "unreadable_fields": []}
MATCH = {"requirement_matches": [{"requirement_id": "r1", "status": "evidenced", "evidence_fact_ids": ["f-acme-1"], "note": "x"},
                                 {"requirement_id": "r2", "status": "gap", "evidence_fact_ids": [], "note": "no Kafka"}],
         "fact_relevance": [{"fact_id": "f-acme-1", "score": 3}, {"fact_id": "f-acme-2", "score": 2}],
         "keyword_plan": ["Java"], "angle": "High-volume Java backend.", "gap_questions": []}
LETTER = {"salutation": "Dear Hiring Team,", "paragraphs": ["word " * 260], "closing": "Best regards,",
          "source_fact_ids": ["f-acme-1"], "addressed_gap_requirement_ids": []}
OUTREACH = {"recruiter_email_subject": "Backend Engineer", "recruiter_email_body": "Hi, short note. {{FULL_NAME}}",
            "linkedin_note": "Hi!", "referral_ask": "Would you refer me? [job link]", "follow_up": "Following up.",
            "source_fact_ids": ["f-acme-1"]}


def test_run_step_records_cost_and_sends_gpt_oss_params():
    fake = FakeGroq({"JobSpec": [JOB]})
    llm = GroqLLM(client=fake)
    job = asyncio.run(llm.run_step("jd_extract", output=JobSpec, cfg=step_config("jd_extract"),
                                   blocks=[("job_description", "Backend Engineer at Kestrel Pay")], contact=CONTACT))
    assert job.company == "Kestrel Pay"
    req = fake.requests[0]
    assert req["model"] == GPT_OSS_120B and req["include_reasoning"] is False and req["reasoning_effort"] == "low"
    assert req["response_format"]["json_schema"]["strict"] is True
    call = llm.calls[0]
    # 400 uncached @0.15 + 600 cached @0.075 + 500 out @0.60, per 1M tokens
    assert call.cost_usd == pytest.approx((400 * 0.15 + 600 * 0.075 + 500 * 0.60) / 1e6)
    assert call.reasoning_tokens == 200 and call.prompt_version.startswith("jd_extract@")


def test_run_step_guards():
    llm = GroqLLM(client=FakeGroq({"JobSpec": [JOB]}))
    with pytest.raises(PIILeak):
        asyncio.run(llm.run_step("jd_extract", output=JobSpec, cfg=step_config("jd_extract"),
                                 blocks=[("job_description", "Contact jordan@example.com")], contact=CONTACT))
    with pytest.raises(StepTruncated):
        asyncio.run(GroqLLM(client=FakeGroq({"JobSpec": [JOB]}, finish="length")).run_step(
            "jd_extract", output=JobSpec, cfg=step_config("jd_extract"), blocks=[("job_description", "x")]))
    broke = GroqLLM(client=FakeGroq({"JobSpec": [JOB]}), budget_usd=0.0)
    with pytest.raises(BudgetExceeded):
        asyncio.run(broke.run_step("jd_extract", output=JobSpec, cfg=step_config("jd_extract"), blocks=[("job_description", "x")]))


def _groq_400(code: str) -> Exception:
    response = httpx.Response(400, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"))
    return groq.BadRequestError("bad request", response=response, body={"error": {"code": code, "message": "x"}})


class FlakyGroq(FakeGroq):
    """Fails the first call with a given 400 error, then answers normally."""

    def __init__(self, answers, error_code: str):
        super().__init__(answers)
        self._error_code, self.attempts = error_code, 0

    async def _create(self, **kwargs):
        self.attempts += 1
        if self.attempts == 1:
            raise _groq_400(self._error_code)
        return await super()._create(**kwargs)


def test_a_schema_mismatch_from_groq_is_retried_once():
    flaky = FlakyGroq({"JobSpec": [JOB]}, "json_validate_failed")
    job = asyncio.run(GroqLLM(client=flaky).run_step(
        "jd_extract", output=JobSpec, cfg=step_config("jd_extract"), blocks=[("job_description", "x")]))
    assert job.company == "Kestrel Pay" and flaky.attempts == 2


def test_other_bad_requests_are_not_retried():
    flaky = FlakyGroq({"JobSpec": [JOB]}, "context_length_exceeded")
    with pytest.raises(groq.BadRequestError):
        asyncio.run(GroqLLM(client=flaky).run_step(
            "jd_extract", output=JobSpec, cfg=step_config("jd_extract"), blocks=[("job_description", "x")]))
    assert flaky.attempts == 1


def test_profile_is_a_stable_prefix_across_steps():
    llm = GroqLLM(client=FakeGroq({}))
    a = llm.build_messages("match_plan", [("career_profile", PROFILE)], [("job_spec", JOB)])
    b = llm.build_messages("resume_tailor", [("career_profile", PROFILE)], [("job_spec", JOB)])
    assert a[0] == b[0]
    prefix = a[1]["content"].split("</career_profile>")[0]
    assert b[1]["content"].startswith(prefix)


def test_pipeline_revises_when_lint_finds_fabrication():
    fabricated = resume(skill_groups=[{"label": "Backend", "skills": ["Java", "Kafka"]}]).model_dump()
    fake = FakeGroq({
        "JobSpec": [JOB], "MatchReport": [MATCH],
        "TailoredResume": [fabricated, resume().model_dump()],  # tailor output, then the revised output
        "CoverLetter": [LETTER], "OutreachPack": [OUTREACH], "VerifyReport": [{"violations": []}],
    })
    pack = asyncio.run(generate_pack(GroqLLM(client=fake), PROFILE, CONTACT, "Backend Engineer, Java + Kafka"))
    assert pack.revised is True
    assert any(f["check"] == "new_skill" for f in pack.lint_initial)
    assert not any(f["severity"] == "high" for f in pack.lint_final)
    steps = [c.step for c in pack.calls]
    assert steps[:2] == ["jd_extract", "match_plan"]
    # The resume chain runs alongside the letters, so only its own order is fixed.
    assert steps.index("resume_tailor") < steps.index("verify") < steps.index("revise")
    assert all("jordan@example.com" not in r["messages"][1]["content"] for r in fake.requests)
