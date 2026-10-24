"""Typst PDF rendering and the fit-to-page loop.

Rendering is deterministic: system fonts are ignored (only the fonts embedded in Typst plus any vendored under
`templates/fonts/` are visible), and the templates set `document(date: none)`, so the same input gives the same
bytes on every host. That keeps page counts, and therefore fit-to-page trimming, identical in dev, CI and prod.

Rendering is CPU-bound and synchronous; call it from async code with `asyncio.to_thread`.
"""

from __future__ import annotations

import io
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, get_args

import typst
from pypdf import PdfReader

from app.features.rendering.document import (
    RenderOptions,
    TemplateName,
    build_resume_document,
)
from app.llm.schemas import Bullet, CareerProfile, ContactDetails, TailoredResume

logger = logging.getLogger(__name__)

# server/app/features/rendering/typst_renderer.py -> repo root
TEMPLATES_DIR = Path(__file__).resolve().parents[4] / "templates"
FONTS_DIR = TEMPLATES_DIR / "fonts"
TEMPLATES: frozenset[str] = frozenset(get_args(TemplateName))


class RenderError(RuntimeError):
    """Typst failed to compile a template."""


@lru_cache(maxsize=1)
def _fonts() -> typst.Fonts:
    paths = [str(FONTS_DIR)] if FONTS_DIR.is_dir() else []
    return typst.Fonts(include_system_fonts=False, include_embedded_fonts=True, font_paths=paths)


def render_pdf(document: dict[str, Any], template: str) -> bytes:
    """Compile `templates/<template>.typ` with `document` passed as JSON in `sys.inputs.resume`."""
    if template not in TEMPLATES:
        raise ValueError(f"unknown template {template!r}; expected one of {sorted(TEMPLATES)}")
    return _compile(f"{template}.typ", "resume", document)


def render_cover_letter_pdf(document: dict[str, Any]) -> bytes:
    """Compile `templates/cover_letter.typ` with `document` passed as JSON in `sys.inputs.letter`."""
    return _compile("cover_letter.typ", "letter", document)


def _compile(template_file: str, input_name: str, data: dict[str, Any]) -> bytes:
    try:
        pdf = typst.compile(
            str(TEMPLATES_DIR / template_file),
            root=str(TEMPLATES_DIR),
            font_paths=_fonts(),
            ignore_system_fonts=True,
            sys_inputs={input_name: json.dumps(data, ensure_ascii=False)},
            format="pdf",
        )
    except typst.TypstError as exc:
        raise RenderError(f"typst failed to render {template_file}: {exc.message}") from exc
    if not isinstance(pdf, bytes):  # multi-page output is only returned as a list for png/svg
        raise RenderError(f"typst returned {type(pdf).__name__}, expected PDF bytes")
    return pdf


def count_pages(pdf: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf)).pages)


# --------------------------------------------------------------------------- fit to page

_TRIMMABLE = ("experience", "projects", "education")


def _bullet_score(bullet: Bullet, relevance: dict[str, int]) -> int:
    """A bullet is as relevant as the most relevant fact it cites."""
    return max((relevance.get(fact_id, 0) for fact_id in bullet.source_fact_ids), default=0)


def _next_bullet_to_drop(
    resume: TailoredResume, profile: CareerProfile, relevance: dict[str, int]
) -> tuple[str, int, int] | None:
    """(section, entry index, bullet index) of the bullet to drop next, or None when nothing can go.

    Lowest relevance first; ties go to the oldest entry (by profile start date; undated counts as oldest),
    then to its last bullet. An entry is never left with zero bullets, and only rendered sections count.
    """
    starts: dict[str, dict[str, str]] = {
        "experience": {e.id: e.start for e in profile.experience},
        "projects": {p.id: p.start or "" for p in profile.projects},
        "education": {e.id: e.start or "" for e in profile.education},
    }
    entries = {
        "experience": [(r.experience_id, r.bullets) for r in resume.experience],
        "projects": [(p.project_id, p.bullets) for p in resume.projects],
        "education": [(e.education_id, e.bullets) for e in resume.education],
    }
    best: tuple[tuple[int, str, int], tuple[str, int, int]] | None = None
    for section in _TRIMMABLE:
        if section not in resume.section_order:
            continue
        for entry_index, (entry_id, bullets) in enumerate(entries[section]):
            if len(bullets) <= 1:
                continue
            start = starts[section].get(entry_id, "")
            for bullet_index, bullet in enumerate(bullets):
                key = (_bullet_score(bullet, relevance), start, -bullet_index)
                if best is None or key < best[0]:
                    best = (key, (section, entry_index, bullet_index))
    return best[1] if best else None


def render_fit(
    resume: TailoredResume,
    profile: CareerProfile,
    contact: ContactDetails,
    options: RenderOptions,
    page_limit: int,
    relevance: dict[str, int],
) -> tuple[bytes, TailoredResume]:
    """Render, dropping the least relevant bullet and re-rendering until the PDF fits `page_limit` pages.

    `relevance` maps fact id -> MatchReport.fact_relevance score. The input resume is not modified. If every
    entry is down to one bullet and the PDF still does not fit, the last render is returned as is (log warning);
    callers can check `count_pages` on the result.
    """
    if page_limit < 1:
        raise ValueError("page_limit must be >= 1")
    current = resume.model_copy(deep=True)
    while True:
        pdf = render_pdf(build_resume_document(current, profile, contact, options), options.template)
        pages = count_pages(pdf)
        if pages <= page_limit:
            return pdf, current
        victim = _next_bullet_to_drop(current, profile, relevance)
        if victim is None:
            logger.warning("render_fit: %d pages after trimming every entry to one bullet (limit %d)",
                           pages, page_limit)
            return pdf, current
        section, entry_index, bullet_index = victim
        getattr(current, section)[entry_index].bullets.pop(bullet_index)
