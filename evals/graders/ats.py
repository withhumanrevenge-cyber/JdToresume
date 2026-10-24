"""Render a pack's final resume (fit-to-page) and run the deterministic ATS round-trip check."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.features.generation.pipeline import PackResult
from app.features.rendering.ats_roundtrip import check_pdf
from app.features.rendering.document import (
    RenderOptions, UnknownReferenceError, build_resume_document, default_page_limit,
)
from app.features.rendering.typst_renderer import count_pages, render_fit
from app.llm.schemas import CareerProfile, ContactDetails, TailoredResume


def render_and_check(
    resume: TailoredResume, profile: CareerProfile, contact: ContactDetails, pack: PackResult, template: str = "classic"
) -> tuple[dict[str, Any], bytes | None]:
    options = RenderOptions.for_profile(profile, template=template)
    relevance = {fr.fact_id: fr.score for fr in pack.match.fact_relevance}
    limit = default_page_limit(profile, this_year=date.today().year)
    try:
        pdf, final = render_fit(resume, profile, contact, options, limit, relevance)
        expected = [s["kind"] for s in build_resume_document(final, profile, contact, options)["sections"]]
    except (UnknownReferenceError, ValueError) as exc:
        return {"parse_ok": False, "issues": [f"render failed: {exc}"]}, None
    check = check_pdf(pdf, contact, expected, pack.job)
    bullets = lambda r: sum(len(x.bullets) for x in (*r.experience, *r.projects, *r.education))  # noqa: E731
    pages = count_pages(pdf)
    result = {**check.model_dump(), "pages": pages, "page_limit": limit, "bullets_dropped": bullets(resume) - bullets(final)}
    if pages > limit:
        result["issues"] = [*result["issues"], f"{pages} pages after trimming (limit {limit})"]
    return result, pdf
