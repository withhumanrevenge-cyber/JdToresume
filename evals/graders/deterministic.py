"""Deterministic grading of one application pack against its eval case. No LLM calls."""

from __future__ import annotations

import statistics
from typing import Any

from pydantic import BaseModel

from app.features.generation.pipeline import PackResult
from app.core.text import term_present
from app.llm.style.linters import find_banned, resume_text
from evals.case import EvalCase

FABRICATION_CHECKS = {"provenance", "numbers", "new_skill", "reference"}


class PackGrade(BaseModel):
    case_id: str
    model: str
    fabrication: bool
    fabrication_reasons: list[str]
    trap_hits_resume: list[str]
    trap_mentions_letter: list[str]
    evidenced_coverage: float
    evidenced_missing: list[str]
    lint_high_final: int
    lint_medium_final: int
    verify_high_initial: int
    verify_medium_initial: int
    banned_hits: int
    revised: bool
    letter_words: int
    letter_issues: int
    outreach_issues: int
    cost_usd: float
    wall_ms: int
    cached_ratio: float
    reasoning_tokens: int
    ats: dict[str, Any] | None


def grade_pack(case: EvalCase, model: str, pack: PackResult, ats: dict[str, Any] | None = None) -> PackGrade:
    text = resume_text(pack.resume)
    letter = "\n".join(pack.cover_letter.paragraphs)
    traps = case.expectations.trap_terms
    trap_hits = [t for t in traps if term_present(t, text)]
    evidenced = case.expectations.evidenced_terms
    missing = [t for t in evidenced if not term_present(t, text)]

    reasons = [f"trap term in resume: {t}" for t in trap_hits]
    reasons += [f"{f['check']} @ {f['location']}: {f['message']}" for f in pack.lint_final
                if f["severity"] == "high" and f["check"] in FABRICATION_CHECKS]
    if ats and not ats.get("parse_ok", True):
        reasons.append("ATS round-trip failed")

    prompt = sum(c.prompt_tokens for c in pack.calls)
    cached = sum(c.cached_tokens for c in pack.calls)
    return PackGrade(
        case_id=case.id,
        model=model,
        fabrication=bool(trap_hits) or any(r for r in reasons if not r.startswith("ATS")),
        fabrication_reasons=reasons,
        trap_hits_resume=trap_hits,
        trap_mentions_letter=[t for t in traps if term_present(t, letter)],
        evidenced_coverage=round(1 - len(missing) / len(evidenced), 3) if evidenced else 1.0,
        evidenced_missing=missing,
        lint_high_final=sum(f["severity"] == "high" for f in pack.lint_final),
        lint_medium_final=sum(f["severity"] == "medium" for f in pack.lint_final),
        verify_high_initial=sum(v.severity == "high" for v in pack.verify.violations),
        verify_medium_initial=sum(v.severity == "medium" for v in pack.verify.violations),
        banned_hits=len([p for p, soft in find_banned(text) if not soft]),
        revised=pack.revised,
        letter_words=len(letter.split()),
        letter_issues=len(pack.cover_letter_lint),
        outreach_issues=len(pack.outreach_lint),
        cost_usd=round(sum(c.cost_usd for c in pack.calls), 6),
        wall_ms=pack.wall_ms,
        cached_ratio=round(cached / prompt, 3) if prompt else 0.0,
        reasoning_tokens=sum(c.reasoning_tokens or 0 for c in pack.calls),
        ats=ats,
    )


def summarize(grades: list[PackGrade]) -> dict[str, Any]:
    if not grades:
        return {}
    n = len(grades)
    ats = [g.ats for g in grades if g.ats is not None]
    return {
        "packs": n,
        "fabrication_rate": round(sum(g.fabrication for g in grades) / n, 3),
        "trap_hits": sum(len(g.trap_hits_resume) for g in grades),
        "evidenced_coverage": round(statistics.mean(g.evidenced_coverage for g in grades), 3),
        "verify_high_per_pack": round(statistics.mean(g.verify_high_initial for g in grades), 2),
        "lint_high_final_per_pack": round(statistics.mean(g.lint_high_final for g in grades), 2),
        "banned_hits_per_pack": round(statistics.mean(g.banned_hits for g in grades), 2),
        "revised_share": round(sum(g.revised for g in grades) / n, 2),
        "ats_parse_pass": round(sum(bool(a.get("parse_ok")) for a in ats) / len(ats), 3) if ats else None,
        "cost_per_pack_usd": round(statistics.mean(g.cost_usd for g in grades), 5),
        "wall_s_p50": round(statistics.median(g.wall_ms for g in grades) / 1000, 1),
        "cached_ratio": round(statistics.mean(g.cached_ratio for g in grades), 2),
    }
