"""Offline end-to-end check of the eval harness: fake Groq -> pipeline -> render + ATS -> grade -> report."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.features.generation.pipeline import generate_pack
from app.llm.client import GroqLLM
from app.llm.schemas import CareerProfile, ContactDetails, JobSpec, TailoredResume
from evals.case import EvalCase, Expectations
from app.features.rendering.document import default_page_limit
from evals.graders.ats import render_and_check
from evals.graders.deterministic import grade_pack, summarize
from evals.run_eval import estimate, failed_gates, render_report, win_rates
from server.tests.fakes import FakeGroq

FIXTURES = Path(__file__).resolve().parents[2] / "server" / "tests" / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_case(trap: str = "Rust") -> EvalCase:
    return EvalCase(
        id="fixture-case", description="renderer fixture", tags=["fixture"],
        profile=CareerProfile.model_validate(load("sample_profile.json")),
        contact=ContactDetails.model_validate(load("sample_contact.json")),
        jd_text="Backend engineer. Must have: Python. Nice to have: " + trap,
        expectations=Expectations(evidenced_terms=["Python"], trap_terms=[trap], trap_notes=""),
    )


def fake_answers(case: EvalCase, resume: dict) -> dict:
    facts = list(case.profile.all_facts())
    job = load("sample_job.json")
    match = {"requirement_matches": [{"requirement_id": r["id"], "status": "evidenced", "evidence_fact_ids": facts[:1],
                                      "note": "fixture"} for r in job["requirements"]],
             "fact_relevance": [{"fact_id": f, "score": 2} for f in facts],
             "keyword_plan": [], "angle": "fixture", "gap_questions": []}
    letter = {"salutation": "Dear Hiring Team,", "paragraphs": ["word " * 260], "closing": "Best regards,",
              "source_fact_ids": facts[:1], "addressed_gap_requirement_ids": []}
    outreach = {"recruiter_email_subject": "Role", "recruiter_email_body": "Short note. {{FULL_NAME}}", "linkedin_note": "Hi",
                "referral_ask": "Could you refer me? [job link]", "follow_up": "Following up.", "source_fact_ids": facts[:1]}
    return {"JobSpec": [job], "MatchReport": [match], "TailoredResume": [resume], "CoverLetter": [letter],
            "OutreachPack": [outreach], "VerifyReport": [{"violations": []}]}


def run_case(case: EvalCase, resume: dict):
    llm = GroqLLM(client=FakeGroq(fake_answers(case, resume)))
    pack = asyncio.run(generate_pack(llm, case.profile, case.contact, case.jd_text))
    ats, pdf = render_and_check(pack.resume, case.profile, case.contact, pack)
    return pack, ats, pdf, grade_pack(case, "fake/model", pack, ats)


def test_clean_pack_renders_passes_ats_and_grades_clean():
    case = make_case()
    pack, ats, pdf, grade = run_case(case, load("sample_tailored_resume.json"))
    assert pdf and pdf.startswith(b"%PDF")
    assert ats["parse_ok"], ats["issues"]
    assert ats["pages"] <= default_page_limit(case.profile, this_year=2026)
    assert grade.fabrication is False and grade.trap_hits_resume == []
    assert grade.cost_usd > 0 and grade.ats["parse_ok"]


def test_trap_term_in_resume_is_fabrication():
    case = make_case()
    resume = load("sample_tailored_resume.json")
    resume["summary"] += " Writes Rust services."
    _, _, _, grade = run_case(case, resume)
    assert grade.fabrication is True and "Rust" in grade.trap_hits_resume


def test_report_and_estimate_render(capsys):
    case = make_case()
    _, _, _, grade = run_case(case, load("sample_tailored_resume.json"))
    results = {
        "started": "test", "dataset": "fixture", "mode": "deep", "models": ["fake/model"], "judge_model": None,
        "prompt_versions": {"resume_tailor": "resume_tailor@x"}, "spent_usd": 0.01,
        "summary": {"fake/model": summarize([grade])}, "win_rates": win_rates(["fake/model"], []),
        "grades": {"fake/model": [grade.model_dump()]}, "judgements": [], "failures": [],
    }
    report = render_report(results)
    assert "fabrication PASS" in report and "ATS parse PASS" in report
    estimate([case], ["openai/gpt-oss-120b", "openai/gpt-oss-20b"], "openai/gpt-oss-120b", True)
    out = capsys.readouterr().out
    assert "ESTIMATED TOTAL" in out and "Developer-tier" in out


def test_fixtures_are_valid_contracts():
    JobSpec.model_validate(load("sample_job.json"))
    TailoredResume.model_validate(load("sample_tailored_resume.json"))


def test_ci_fails_when_a_hard_gate_fails():
    passing = {"models": ["m"], "summary": {"m": {"fabrication_rate": 0, "ats_parse_pass": 1}}}
    renderer_off = {"models": ["m"], "summary": {"m": {"fabrication_rate": 0, "ats_parse_pass": None}}}
    failing = {"models": ["a", "b", "c"], "summary": {
        "a": {"fabrication_rate": 0.25, "ats_parse_pass": 1},
        "b": {"fabrication_rate": 0, "ats_parse_pass": 0.5},
        "c": {},
    }}
    assert failed_gates(passing) == [] and failed_gates(renderer_off) == []
    assert failed_gates(failing) == ["a: fabrication rate 25%", "b: ATS parse pass 50%", "c: no successful packs"]
