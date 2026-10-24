"""What every reader produces: the job posting as plain text, plus where it came from."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

JobSource = Literal["text", "ats_feed", "embedded_data", "page_text"]


@dataclass(frozen=True)
class RawJob:
    text: str  # what the jd_extract step reads
    source: JobSource
    ats_vendor: str | None = None  # "greenhouse", "lever", "ashby" (tells us which ATS will parse the resume)


def compose_text(*, title: str | None, company: str | None, location: str | None, body: str,
                 extra: dict[str, str | None] | None = None) -> str:
    """Put the structured bits on top of the description, the way a posting page reads."""
    lines = [f"{label}: {value}" for label, value in
             [("Title", title), ("Company", company), ("Location", location), *(extra or {}).items()] if value]
    return "\n".join(lines) + ("\n\n" if lines else "") + body.strip()
