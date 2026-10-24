"""Resume onboarding: file → text → (contact details kept locally, redacted text) → CareerProfile via Groq.

Groq has no PDF input (ADR-0001), so text extraction is local. Contact details are pulled out with regexes
*before* anything is sent and replaced by placeholders, so the LLM never sees them (CLAUDE.md non-negotiable #2).
The user then reviews both the profile and the contact details (GET/PUT /v1/profile and /v1/profile/contact).
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from app.llm.client import GroqLLM
from app.llm.pii import PLACEHOLDERS
from app.llm.router import Mode, step_config
from app.llm.schemas import CareerProfile, ContactDetails

SUPPORTED_SUFFIXES = (".pdf", ".txt", ".md")  # DOCX and scanned PDFs (OCR) come later

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_URL = re.compile(r"(?:https?://)?(?:www\.)?(?:linkedin\.com/in|github\.com|gitlab\.com|behance\.net|dribbble\.com)/[\w\-./]+", re.I)
_DATE_RANGE = re.compile(r"^\D*(19|20)\d{2}\D+(19|20)\d{2}\D*$")
_JANUARY = re.compile(r"^(\d{4})-01$")


class UnsupportedResumeError(ValueError):
    """The file type isn't supported, or it contains no extractable text."""


def extract_text_from_bytes(data: bytes, suffix: str) -> str:
    """Plain text from a resume file. Raises UnsupportedResumeError for other formats."""
    suffix = suffix.lower()
    if suffix == ".pdf":
        from pdfminer.high_level import extract_text as pdf_text  # imported lazily: it's slow to import
        return pdf_text(io.BytesIO(data))
    if suffix in (".txt", ".md"):
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UnsupportedResumeError("Text files must be UTF-8 encoded") from exc
    raise UnsupportedResumeError(f"Unsupported file type {suffix or '(none)'}: use one of {', '.join(SUPPORTED_SUFFIXES)}")


def extract_text(path: Path) -> str:
    return extract_text_from_bytes(path.read_bytes(), path.suffix)


def split_contact(text: str) -> tuple[ContactDetails, str]:
    """Find the user's contact details locally and return them plus the text with placeholders."""
    emails = _EMAIL.findall(text)
    phones = [p for p in _PHONE.findall(text) if len(re.sub(r"\D", "", p)) >= 10 and not _DATE_RANGE.match(p)]
    links = sorted({m.rstrip("/.") for m in _URL.findall(text)})
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    name = re.split(r"\s+[|•·]\s+|\s{3,}", first_line)[0].strip()  # "Jane Doe | Engineer" -> "Jane Doe"
    # A name is short and has no digits or @; otherwise leave it for the user to fill in (and the guard can't check it).
    if not 1 < len(name.split()) <= 5 or re.search(r"[\d@]", name):
        name = ""

    redacted = text
    if name:
        redacted = redacted.replace(name, PLACEHOLDERS["full_name"])
    for email in emails:
        redacted = redacted.replace(email, PLACEHOLDERS["email"])
    for phone in phones:
        redacted = redacted.replace(phone, PLACEHOLDERS["phone"])
    for i, link in enumerate(links):
        redacted = re.sub(re.escape(link), f"{{{{LINK_{i}}}}}", redacted, flags=re.I)

    contact = ContactDetails(full_name=name, email=emails[0] if emails else "", phone=phones[0].strip() if phones else None,
                             city=None, links=links)
    return contact, redacted


async def parse_resume_text(llm: GroqLLM, text: str, *, mode: Mode = "deep") -> tuple[CareerProfile, ContactDetails]:
    """Contact details (found locally) + the CareerProfile parsed by the LLM from the redacted text."""
    contact, redacted = split_contact(text)
    profile = await llm.run_step(
        "resume_parse", output=CareerProfile, cfg=step_config("resume_parse", mode),
        blocks=[("resume_text", redacted)], contact=contact,
    )
    return drop_unseen_january(profile, text), contact


def drop_unseen_january(profile: CareerProfile, text: str) -> CareerProfile:
    """Turn a parsed "YYYY-01" back into "YYYY" when the resume never shows January of that year.

    January is the month a model fills in for a year-only date ("2015 - 2019" -> "2019-01"), which would print an
    invented month on the user's resume (CLAUDE.md non-negotiable #1). The prompt asks for "YYYY"; this makes sure.
    """
    def checked(value: str) -> str:
        match = _JANUARY.match(value)
        return value if match is None or _shows_january(text, match.group(1)) else match.group(1)

    for entry in (*profile.experience, *profile.projects, *profile.education):
        entry.start = checked(entry.start) if entry.start else entry.start
        entry.end = checked(entry.end) if entry.end else entry.end
    for cert in profile.certifications:
        cert.date = checked(cert.date) if cert.date else cert.date
    return profile


def _shows_january(text: str, year: str) -> bool:
    """'Jan 2019', 'January - March 2019', "Jan '19", '2019 Jan', '01/2019', '1/19', '2019-01' and the like."""
    yy = year[2:]
    patterns = (
        rf"\bjan[a-z]*\.?\D{{0,15}}(?:{year}|['’]{yy})\b",
        rf"\b{year}\s+jan",
        rf"\b0?1\s*[/.-]\s*(?:{year}|{yy})\b",
        rf"\b{year}\s*[/.-]\s*0?1\b",
    )
    return any(re.search(pattern, text, re.I) for pattern in patterns)


async def parse_resume(llm: GroqLLM, path: Path, *, mode: Mode = "deep") -> tuple[CareerProfile, ContactDetails]:
    """File-path version, used by the concierge CLI."""
    return await parse_resume_text(llm, extract_text(path), mode=mode)
