"""Resolve a CoverLetter into plain render data for `templates/cover_letter.typ` and the DOCX writer.

This is where the letter meets the person's real details: placeholders such as {{FULL_NAME}} that the LLM wrote
are replaced here, at render time, because the LLM never saw the real values.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.features.rendering.document import RenderOptions, contact_items
from app.llm.pii import restore_placeholders
from app.llm.schemas import ContactDetails, CoverLetter, JobSpec

_MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                "November", "December")
_MONTH_FIRST_REGIONS = frozenset({"US", "CA"})  # "October 21, 2026" there, "21 October 2026" elsewhere


def format_letter_date(day: date, region: str) -> str:
    month = _MONTH_NAMES[day.month - 1]
    return f"{month} {day.day}, {day.year}" if region in _MONTH_FIRST_REGIONS else f"{day.day} {month} {day.year}"


def build_cover_letter_document(
    letter: CoverLetter, contact: ContactDetails, job: JobSpec, *, region: str, today: date
) -> dict[str, Any]:
    def real(text: str) -> str:
        return restore_placeholders(text, contact).strip()

    return {
        "page": {"paper": RenderOptions.page_size_for_region(region)},
        "header": {"name": contact.full_name.strip(), "contact": contact_items(contact)},
        "date": format_letter_date(today, region),
        "recipient": [line for line in (job.company, job.location) if line],
        "salutation": real(letter.salutation),
        "paragraphs": [real(p) for p in letter.paragraphs if p.strip()],
        "closing": real(letter.closing),
        "signature": contact.full_name.strip(),
    }
