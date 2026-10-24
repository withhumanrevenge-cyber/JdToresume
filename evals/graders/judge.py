"""Pairwise LLM judge. Runs both orders (A/B and B/A) to cancel position bias.

Caveat: if the judge model is also a contestant it may prefer its own style. Human recruiter review
(ROADMAP Phase 0 blind test) is the ground truth; this judge is for fast iteration.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from groq import AsyncGroq

from app.llm.client import render_blocks
from app.llm.router import PRICES
from app.llm.schemas import CareerProfile, PairwiseVerdict, TailoredResume, strict_json_schema

JUDGE_PROMPT = Path(__file__).with_name("judge.md").read_text(encoding="utf-8").strip()


def resume_plaintext(resume: TailoredResume, profile: CareerProfile) -> str:
    """Readable plain text with headers resolved from the profile (what a recruiter would see)."""
    exp = {e.id: e for e in profile.experience}
    proj = {p.id: p for p in profile.projects}
    edu = {e.id: e for e in profile.education}
    certs = {c.id: c for c in profile.certifications}
    out: list[str] = []
    for section in resume.section_order:
        if section == "summary" and resume.summary:
            out += ["SUMMARY", resume.summary, ""]
        elif section == "experience" and resume.experience:
            out.append("EXPERIENCE")
            for role in resume.experience:
                e = exp.get(role.experience_id)
                head = f"{e.title}, {e.company} ({e.start} to {e.end or 'present'})" if e else f"[unknown role {role.experience_id}]"
                out += [head, *(f"- {b.text}" for b in role.bullets), ""]
        elif section == "projects" and resume.projects:
            out.append("PROJECTS")
            for p in resume.projects:
                head = proj[p.project_id].name if p.project_id in proj else f"[unknown project {p.project_id}]"
                out += [head, *(f"- {b.text}" for b in p.bullets), ""]
        elif section == "education" and resume.education:
            out.append("EDUCATION")
            for ed in resume.education:
                e = edu.get(ed.education_id)
                out.append(f"{e.degree}, {e.institution}" if e else f"[unknown education {ed.education_id}]")
                out += [f"- {b.text}" for b in ed.bullets]
            out.append("")
        elif section == "skills" and resume.skill_groups:
            out.append("SKILLS")
            out += [f"{g.label}: {', '.join(g.skills)}" for g in resume.skill_groups]
            out.append("")
        elif section == "certifications" and resume.certification_ids:
            out += ["CERTIFICATIONS", *(certs[c].name for c in resume.certification_ids if c in certs), ""]
    return "\n".join(out).strip()


async def _judge_once(client: AsyncGroq, judge_model: str, profile: CareerProfile, jd_text: str,
                      text_a: str, text_b: str) -> tuple[PairwiseVerdict, float]:
    user = render_blocks([
        ("career_profile", profile), ("job_description", jd_text), ("resume_a", text_a), ("resume_b", text_b),
    ])
    kwargs = dict(
        model=judge_model,
        messages=[{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": user}],
        response_format={"type": "json_schema", "json_schema": {
            "name": "PairwiseVerdict", "strict": True, "schema": strict_json_schema(PairwiseVerdict)}},
        max_completion_tokens=8000,
        reasoning_effort="high",
    )
    if judge_model.startswith("openai/gpt-oss"):
        kwargs["include_reasoning"] = False
    elif judge_model.startswith("qwen/"):
        kwargs["reasoning_format"] = "hidden"
    resp = await client.chat.completions.create(**kwargs)
    usage = resp.usage
    cached = (usage.prompt_tokens_details.cached_tokens or 0) if usage.prompt_tokens_details else 0
    cost = PRICES[judge_model].cost(usage.prompt_tokens, cached, usage.completion_tokens)
    return PairwiseVerdict.model_validate_json(resp.choices[0].message.content), cost


async def judge_pair(client: AsyncGroq, judge_model: str, profile: CareerProfile, jd_text: str,
                     name_a: str, resume_a: TailoredResume, name_b: str, resume_b: TailoredResume) -> dict:
    """Returns the winner by name ('tie' if the two orders disagree or both say tie) plus per-order details."""
    text_a, text_b = resume_plaintext(resume_a, profile), resume_plaintext(resume_b, profile)
    (v1, c1), (v2, c2) = await asyncio.gather(
        _judge_once(client, judge_model, profile, jd_text, text_a, text_b),
        _judge_once(client, judge_model, profile, jd_text, text_b, text_a),
    )
    first = {"A": name_a, "B": name_b, "tie": "tie"}[v1.winner]
    second = {"A": name_b, "B": name_a, "tie": "tie"}[v2.winner]
    winner = first if first == second else "tie"
    return {
        "a": name_a, "b": name_b, "winner": winner,
        "orders": [v1.model_dump(), v2.model_dump()],
        "truthfulness": {name_a: (v1.scores_a.truthfulness + v2.scores_b.truthfulness) / 2,
                         name_b: (v1.scores_b.truthfulness + v2.scores_a.truthfulness) / 2},
        "cost_usd": round(c1 + c2, 6),
    }
