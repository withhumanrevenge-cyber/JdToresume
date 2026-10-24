"""Deterministic ATS round-trip check (ats-compliance skill §3).

Reads a rendered PDF back the way a generic parser would and measures what it can actually see: two independent
extractors (pdfminer.six and pypdf) must agree, section headings must appear in the expected order, the email and
phone must be near the top, date ranges must parse and run in reverse-chronological order, the job's keywords and
must-have evidence terms are counted in the *extracted* text (never in our JSON), and there must be no
private-use, ligature or unmapped glyphs and no text under 8 pt.

`parse_ok` is true exactly when `issues` is empty. Keyword and must-have coverage are reported but never block,
since they measure content, not parsing.

A .docx gets the same check (`check_docx`), read by python-docx and by a raw walk of its XML.

CLI: python -m app.features.rendering.ats_roundtrip resume.pdf [--name ... --email ... --phone ...]
     [--sections summary,experience,...] [--job job.json]
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import zipfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from xml.etree import ElementTree

from docx import Document as DocxDocument
from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTChar, LTContainer, LTItem, LTTextContainer
from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader

from app.core.text import term_present  # re-exported: the one keyword matcher
from app.llm.schemas import ContactDetails, JobSpec

AGREEMENT_THRESHOLD = 0.95
CONTACT_REGION = 0.15  # email/phone must sit in the first ~15% of the text...
CONTACT_REGION_MIN_CHARS = 300  # ...but never less than this, so a short document still has a header region
MIN_FONT_SIZE_PT = 8.0
_FONT_SIZE_TOLERANCE = 0.05

# Canonical section -> headings a generic parser would recognise. Whole-line, case-insensitive match.
SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "summary": ("summary", "professional summary", "career summary", "profile", "professional profile"),
    "experience": ("experience", "work experience", "professional experience", "employment history",
                   "work history", "employment"),
    "projects": ("projects", "personal projects", "selected projects", "key projects"),
    "education": ("education", "education and training", "academic background"),
    "skills": ("skills", "technical skills", "core skills", "key skills", "core competencies"),
    "certifications": ("certifications", "certificates", "licenses and certifications",
                       "licenses & certifications"),
}
_HEADING_TO_SECTION = {alias: section for section, aliases in SECTION_ALIASES.items() for alias in aliases}

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d ().-]{6,}\d")

# Date ranges: "Mar 2022 – Present", but also the non-canonical forms we want to flag ("03/2022 - 2023-05").
_MONTH = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?"
          r"|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?")
_YEAR = r"(?:19|20)\d{2}"
_DATE = rf"(?:{_MONTH}\s+{_YEAR}|\d{{1,2}}/{_YEAR}|{_YEAR}(?:[-/.]\d{{1,2}})?)"
_RANGE_RE = re.compile(
    rf"(?<![\w/.-])({_DATE})\s*(?:–|—|-|to)\s*({_DATE}|present|current|now)(?![\w/])", re.IGNORECASE)
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_CANONICAL_DATE_RE = re.compile(rf"^(?:({'|'.join(_MONTHS)}) ({_YEAR})|({_YEAR})|(Present))$")

_LIGATURES = frozenset("ﬀﬁﬂﬃﬄﬅﬆ")


class AtsCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parse_ok: bool = Field(description="True exactly when `issues` is empty")
    extractors_agree: bool
    extractor_agreement: float = Field(description="Word-sequence similarity of the two extractors, 0..1")
    sections_found: list[str] = Field(description="Canonical section names in the order they were found")
    contact_found: bool
    date_issues: list[str]
    keyword_coverage: float | None = Field(description="Share of JobSpec.keywords found; None without a job")
    keywords_missing: list[str]
    must_have_coverage: float | None = Field(
        description="Share of basic requirements with an evidence term in the text; None if there are none")
    issues: list[str]


# --------------------------------------------------------------------------- extraction

@dataclass(frozen=True)
class ExtractedText:
    """One document as read by two independent readers (pdfminer.six and pypdf for a PDF)."""

    primary: str
    secondary: str
    min_font_size: float | None  # None for a .docx: it has no rendered glyphs to measure
    readers: tuple[str, str] = ("pdfminer", "pypdf")


def normalize_text(text: str) -> str:
    """Collapse whitespace within lines and drop empty lines."""
    lines = (re.sub(r"\s+", " ", line).strip() for line in re.split(r"[\r\n\f\v]+", text.replace("\xa0", " ")))
    return "\n".join(line for line in lines if line)


def _chars(item: LTItem) -> Iterator[LTChar]:
    if isinstance(item, LTChar):
        yield item
    elif isinstance(item, LTContainer):
        for child in item:
            yield from _chars(child)


def extract(pdf: bytes) -> ExtractedText:
    """Text from both extractors (normalized) plus the smallest glyph size pdfminer saw."""
    parts: list[str] = []
    min_size: float | None = None
    for page in extract_pages(io.BytesIO(pdf), laparams=LAParams()):
        for element in page:
            if isinstance(element, LTTextContainer):
                parts.append(element.get_text())
                parts.append("\n")
            for char in _chars(element):
                if char.get_text().strip():
                    min_size = char.size if min_size is None else min(min_size, char.size)
    reader = PdfReader(io.BytesIO(pdf))
    pypdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return ExtractedText(normalize_text("".join(parts)), normalize_text(pypdf_text), min_size)


def extract_docx(data: bytes) -> ExtractedText:
    """Text of a .docx read two ways: python-docx's body paragraphs, and every <w:p> in the raw XML.

    The two disagree exactly when text sits where a simple parser doesn't look (tables, text boxes), which is
    what the agreement check is for. Text in the page header or footer is in neither, as with most parsers.
    """
    paragraphs = "\n".join(p.text for p in DocxDocument(io.BytesIO(data)).paragraphs)
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        root = ElementTree.fromstring(package.read("word/document.xml"))
    raw = "\n".join(_xml_paragraph_text(p) for p in root.iter(f"{_W}p"))
    return ExtractedText(normalize_text(paragraphs), normalize_text(raw), None, readers=("python-docx", "raw xml"))


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _xml_paragraph_text(paragraph: ElementTree.Element) -> str:
    parts: list[str] = []
    for run in paragraph.iter(f"{_W}r"):  # runs inside hyperlinks included
        for node in run:
            if node.tag == f"{_W}t":
                parts.append(node.text or "")
            elif node.tag == f"{_W}tab":
                parts.append("\t")
            elif node.tag in (f"{_W}br", f"{_W}cr"):
                parts.append("\n")
    return "".join(parts)


# --------------------------------------------------------------------------- individual checks

def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def extractor_agreement(a: str, b: str) -> float:
    words_a, words_b = _words(a), _words(b)
    if not words_a and not words_b:
        return 1.0
    return SequenceMatcher(None, words_a, words_b, autojunk=False).ratio()


def find_sections(text: str) -> list[tuple[str, int]]:
    """(canonical section, line index) for each heading line, first occurrence only."""
    found: list[tuple[str, int]] = []
    seen: set[str] = set()
    for index, line in enumerate(text.split("\n")):
        key = re.sub(r"\s+", " ", line.strip().rstrip(":").lower())
        section = _HEADING_TO_SECTION.get(key)
        if section and section not in seen:
            seen.add(section)
            found.append((section, index))
    return found


def _section_order_issues(found: list[str], expected: Sequence[str]) -> list[str]:
    issues = [f"section '{name}' not found" for name in expected if name not in found]
    present_expected = [name for name in expected if name in found]
    found_expected = [name for name in found if name in expected]
    if present_expected != found_expected:
        issues.append(f"sections out of order: expected {present_expected}, found {found_expected}")
    return issues


def _contact_issues(text: str, contact: ContactDetails | None) -> list[str]:
    head = text[: max(int(len(text) * CONTACT_REGION), CONTACT_REGION_MIN_CHARS)]
    head_lower = head.lower()
    issues: list[str] = []
    if contact is None:
        if not _EMAIL_RE.search(head):
            issues.append("no email address near the top")
        if not _PHONE_RE.search(head):
            issues.append("no phone number near the top")
        return issues
    name = re.sub(r"\s+", " ", contact.full_name.strip()).lower()
    if name and name not in re.sub(r"\s+", " ", head_lower):
        issues.append("name not found near the top")
    if contact.email.strip().lower() not in head_lower:
        issues.append("email not found near the top")
    wanted = re.sub(r"\D", "", contact.phone or "")
    if wanted and not any(wanted in re.sub(r"\D", "", m) for m in _PHONE_RE.findall(head)):
        issues.append("phone not found near the top")
    return issues


def _parse_date(token: str, *, is_end: bool) -> tuple[int, int] | None:
    """Canonical token -> (year, month). Present sorts after everything. None if not canonical."""
    match = _CANONICAL_DATE_RE.match(token)
    if match is None:
        return None
    month_name, year, year_only, present = match.groups()
    if present:
        return (9999, 12)
    if year_only:
        return (int(year_only), 12 if is_end else 1)
    return (int(year), _MONTHS.index(month_name) + 1)


def _date_issues(text: str, sections: list[tuple[str, int]]) -> list[str]:
    lines = text.split("\n")
    experience_span: tuple[int, int] | None = None
    for position, (section, line_index) in enumerate(sections):
        if section == "experience":
            end = sections[position + 1][1] if position + 1 < len(sections) else len(lines)
            experience_span = (line_index, end)

    issues: list[str] = []
    role_ends: list[tuple[tuple[int, int], str]] = []
    for index, line in enumerate(lines):
        for match in _RANGE_RE.finditer(line):
            raw = match.group(0)
            start = _parse_date(match.group(1), is_end=False)
            end = _parse_date(match.group(2), is_end=True)
            if start is None or end is None:
                issues.append(f"non-standard date '{raw}' (use 'Mon YYYY – Mon YYYY' or '... – Present')")
                continue
            if start > end:
                issues.append(f"date range ends before it starts: '{raw}'")
            if experience_span and experience_span[0] < index < experience_span[1]:
                role_ends.append((end, raw))
    for (previous_end, previous_raw), (end, raw) in zip(role_ends, role_ends[1:]):
        if end > previous_end:
            issues.append(f"experience not in reverse-chronological order: '{raw}' listed after '{previous_raw}'")
    return issues


def _glyph_issues(text: str, extractor: str) -> list[str]:
    issues: list[str] = []
    private = sorted({c for c in text if 0xE000 <= ord(c) <= 0xF8FF or ord(c) >= 0xF0000})
    if private:
        codes = ", ".join(f"U+{ord(c):04X}" for c in private[:5])
        issues.append(f"{extractor}: private-use glyphs in extracted text ({codes})")
    ligatures = sorted({c for c in text if c in _LIGATURES})
    if ligatures:
        issues.append(f"{extractor}: ligature glyphs in extracted text ({' '.join(ligatures)})")
    # pdfminer writes "(cid:N)" for a glyph with no Unicode mapping; pypdf emits a control character instead.
    if "�" in text or "(cid:" in text or any(ord(c) < 32 and c not in "\t\n" for c in text):
        issues.append(f"{extractor}: unmapped glyphs in extracted text")
    return issues


def _keyword_coverage(text: str, job: JobSpec) -> tuple[float | None, list[str]]:
    if not job.keywords:
        return None, []
    missing = [k.term for k in job.keywords if not any(term_present(t, text) for t in (k.term, *k.synonyms))]
    return (len(job.keywords) - len(missing)) / len(job.keywords), missing


def _must_have_coverage(text: str, job: JobSpec) -> float | None:
    """Over basic requirements that list evidence terms; one without terms cannot be checked from text."""
    checkable = [r for r in job.requirements if r.tier == "basic" and r.evidence_terms]
    if not checkable:
        return None
    covered = sum(1 for r in checkable if any(term_present(t, text) for t in r.evidence_terms))
    return covered / len(checkable)


# --------------------------------------------------------------------------- the check

def check_text(
    extracted: ExtractedText,
    contact: ContactDetails | None,
    expected_sections: Sequence[str],
    job: JobSpec | None,
) -> AtsCheck:
    text, other = extracted.primary, extracted.secondary
    first_reader, second_reader = extracted.readers
    issues: list[str] = []
    if not text or not other:
        issues.append("no extractable text (image-only or unmapped fonts?)")

    sections = find_sections(text)
    section_names = [name for name, _ in sections]
    agreement = extractor_agreement(text, other)
    same_order = section_names == [name for name, _ in find_sections(other)]
    extractors_agree = agreement >= AGREEMENT_THRESHOLD and same_order
    if not extractors_agree:
        issues.append(f"extractors disagree (similarity {agreement:.3f}, same section order: {same_order})")

    issues += _section_order_issues(section_names, [s.lower() for s in expected_sections])
    contact_issues = _contact_issues(text, contact)
    issues += contact_issues
    date_issues = _date_issues(text, sections)
    issues += date_issues
    issues += _glyph_issues(text, first_reader) + _glyph_issues(other, second_reader)
    if extracted.min_font_size is not None and extracted.min_font_size < MIN_FONT_SIZE_PT - _FONT_SIZE_TOLERANCE:
        issues.append(f"text smaller than {MIN_FONT_SIZE_PT:g} pt ({extracted.min_font_size:.1f} pt)")

    keyword_coverage, keywords_missing, must_have = None, [], None
    if job is not None:
        flat = text.replace("\n", " ")
        keyword_coverage, keywords_missing = _keyword_coverage(flat, job)
        must_have = _must_have_coverage(flat, job)

    return AtsCheck(
        parse_ok=not issues,
        extractors_agree=extractors_agree,
        extractor_agreement=round(agreement, 4),
        sections_found=section_names,
        contact_found=not contact_issues,
        date_issues=date_issues,
        keyword_coverage=keyword_coverage,
        keywords_missing=keywords_missing,
        must_have_coverage=must_have,
        issues=issues,
    )


def check_pdf(
    pdf: bytes,
    contact: ContactDetails | None,
    expected_sections: Sequence[str],
    job: JobSpec | None,
) -> AtsCheck:
    """Round-trip check of a rendered PDF. `contact=None` falls back to generic email/phone patterns."""
    return check_text(extract(pdf), contact, expected_sections, job)


def check_docx(
    data: bytes,
    contact: ContactDetails | None,
    expected_sections: Sequence[str],
    job: JobSpec | None,
) -> AtsCheck:
    """The same round-trip check for a .docx (everything except the font-size check)."""
    return check_text(extract_docx(data), contact, expected_sections, job)


# --------------------------------------------------------------------------- CLI

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print what an ATS-style parser reads from a PDF, and check it.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--email", help="expected email; enables exact contact checks (else generic patterns)")
    parser.add_argument("--name", default="", help="expected full name (with --email)")
    parser.add_argument("--phone", help="expected phone (with --email)")
    parser.add_argument("--sections", default="", help="expected section order, e.g. summary,experience,skills")
    parser.add_argument("--job", type=Path, help="JobSpec JSON for keyword and must-have coverage")
    args = parser.parse_args(argv)

    contact = None
    if args.email:
        contact = ContactDetails(full_name=args.name, email=args.email, phone=args.phone, city=None, links=[])
    job = JobSpec.model_validate_json(args.job.read_text(encoding="utf-8")) if args.job else None
    sections = [s.strip() for s in args.sections.split(",") if s.strip()]

    extracted = extract(args.pdf.read_bytes())
    result = check_text(extracted, contact, sections, job)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("===== pdfminer.six =====")
    print(extracted.primary)
    print("===== pypdf =====")
    print(extracted.secondary)
    print("===== check =====")
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    return 0 if result.parse_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
