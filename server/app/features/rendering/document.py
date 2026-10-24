"""Resolve a TailoredResume into plain render data for the Typst templates.

The LLM output only *references* the CareerProfile by id. Everything an employer could check (role title,
company, location, dates, project and education headers, certification names) is pulled from the profile here,
never from LLM text. Contact details are merged in at this point, at render time; they never pass through the LLM.

The returned dict is JSON-serialisable and is the only input the templates in `templates/` read.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.llm.schemas import Bullet, CareerProfile, ContactDetails, Fact, SectionName, TailoredResume

TemplateName = Literal["classic", "modern"]
PageSize = Literal["us-letter", "a4"]

# ats-compliance §2: US Letter for the US and Canada, A4 everywhere else.
_LETTER_REGIONS = frozenset({"US", "CA"})

# ats-compliance §2: standard headings only, so parsers can detect sections.
SECTION_HEADINGS: dict[SectionName, str] = {
    "summary": "Summary",
    "experience": "Experience",
    "projects": "Projects",
    "education": "Education",
    "skills": "Skills",
    "certifications": "Certifications",
}

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
PRESENT = "Present"
DATE_SEPARATOR = " – "  # en dash, as in "Mar 2022 – Present"

_PROFILE_DATE_RE = re.compile(r"^(\d{4})(?:-(\d{2}))?(?:-\d{2})?$")


class UnknownReferenceError(LookupError):
    """The tailored resume references an id that does not exist in the career profile."""


class RenderOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    template: TemplateName = "classic"
    page_size: PageSize

    @staticmethod
    def page_size_for_region(region: str) -> PageSize:
        return "us-letter" if region in _LETTER_REGIONS else "a4"

    @classmethod
    def for_profile(cls, profile: CareerProfile, template: TemplateName = "classic") -> RenderOptions:
        return cls(template=template, page_size=cls.page_size_for_region(profile.preferences.region))


_TWO_PAGE_REGIONS = frozenset({"UK", "IE", "AU", "DE", "AE"})


def default_page_limit(profile: CareerProfile, *, this_year: int) -> int:
    """resume-tailoring §2: one page under ~8 years of experience in US-style markets, otherwise two.
    The user's own preference always wins."""
    if profile.preferences.page_limit:
        return profile.preferences.page_limit
    if profile.preferences.region in _TWO_PAGE_REGIONS:
        return 2
    starts = [int(e.start[:4]) for e in profile.experience if e.start[:4].isdigit()]
    ends = [int(e.end[:4]) if e.end and e.end[:4].isdigit() else this_year for e in profile.experience]
    years = max(ends) - min(starts) if starts else 0
    return 2 if years >= 8 else 1


# --------------------------------------------------------------------------- dates

def format_month(value: str) -> str:
    """'2022-03' -> 'Mar 2022'. A year-only value stays 'YYYY': we never invent a month."""
    match = _PROFILE_DATE_RE.match(value.strip())
    if match is None:
        raise ValueError(f"unparseable profile date {value!r}; expected YYYY-MM")
    year, month = match.group(1), match.group(2)
    if month is None:
        return year
    index = int(month)
    if not 1 <= index <= 12:
        raise ValueError(f"invalid month in profile date {value!r}")
    return f"{MONTHS[index - 1]} {year}"


def format_range(start: str | None, end: str | None) -> str:
    """'Mon YYYY – Mon YYYY', or 'Mon YYYY – Present' when there is a start but no end.

    Only an end date (e.g. a graduation) renders as a single date; no dates render as "".
    """
    if start is None:
        return format_month(end) if end is not None else ""
    first = format_month(start)
    last = format_month(end) if end is not None else PRESENT
    return first if first == last else f"{first}{DATE_SEPARATOR}{last}"


# --------------------------------------------------------------------------- links

def _link(raw: str) -> dict[str, str]:
    """Visible URL text ('linkedin.com/in/name') plus a working target. Parsers keep the text, not the target."""
    raw = raw.strip()
    url = raw if re.match(r"^[a-z][a-z0-9+.-]*:", raw, re.I) else f"https://{raw}"
    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", raw, flags=re.I)
    text = re.sub(r"^www\.", "", text, flags=re.I).rstrip("/")
    return {"text": text, "url": url}


# --------------------------------------------------------------------------- builder

def build_resume_document(
    resume: TailoredResume,
    profile: CareerProfile,
    contact: ContactDetails,
    options: RenderOptions,
) -> dict[str, Any]:
    """Plain render data for a template. Raises UnknownReferenceError for any id not in the profile."""
    facts = profile.all_facts()
    _check_fact_ids(resume.summary_source_fact_ids, facts, "summary")

    builders = {
        "summary": lambda: _summary_section(resume),
        "experience": lambda: _experience_section(resume, profile, facts),
        "projects": lambda: _projects_section(resume, profile, facts),
        "education": lambda: _education_section(resume, profile, facts),
        "skills": lambda: _skills_section(resume),
        "certifications": lambda: _certifications_section(resume, profile),
    }

    sections: list[dict[str, Any]] = []
    seen: set[str] = set()
    for kind in resume.section_order:
        if kind in seen:
            continue
        seen.add(kind)
        section = builders[kind]()
        if section is not None:
            sections.append({"kind": kind, "heading": SECTION_HEADINGS[kind], **section})

    return {
        "page": {"paper": options.page_size},
        "header": _header(profile, contact),
        "sections": sections,
    }


def contact_items(contact: ContactDetails) -> list[dict[str, str | None]]:
    """Email, phone, city, then links as visible text. Shared by the resume and the cover letter."""
    items: list[dict[str, str | None]] = [{"text": contact.email.strip(), "url": None}]
    if contact.phone and contact.phone.strip():
        items.append({"text": contact.phone.strip(), "url": None})
    if contact.city and contact.city.strip():
        items.append({"text": contact.city.strip(), "url": None})
    items.extend(_link(link) for link in contact.links if link.strip())
    return items


def _header(profile: CareerProfile, contact: ContactDetails) -> dict[str, Any]:
    headline = profile.headline.strip()
    return {"name": contact.full_name.strip(), "headline": headline or None, "contact": contact_items(contact)}


def _check_fact_ids(fact_ids: list[str], facts: dict[str, Fact], where: str) -> None:
    for fact_id in fact_ids:
        if fact_id not in facts:
            raise UnknownReferenceError(f"{where}: unknown fact id {fact_id!r}")


def _bullets(bullets: list[Bullet], facts: dict[str, Fact], where: str) -> list[str]:
    for index, bullet in enumerate(bullets):
        _check_fact_ids(bullet.source_fact_ids, facts, f"{where}.bullets[{index}]")
    return [b.text.strip() for b in bullets if b.text.strip()]


def _entry(
    title: str,
    *,
    org: str | None = None,
    location: str | None = None,
    dates: str = "",
    link: dict[str, str] | None = None,
    detail: str | None = None,
    bullets: list[str],
) -> dict[str, Any]:
    """Uniform entry shape shared by experience, projects and education."""
    return {
        "title": title,
        "org": org or None,
        "location": location or None,
        "dates": dates,
        "link": link,
        "detail": detail or None,
        "bullets": bullets,
    }


def _summary_section(resume: TailoredResume) -> dict[str, Any] | None:
    text = resume.summary.strip()
    return {"text": text} if text else None


def _experience_section(
    resume: TailoredResume, profile: CareerProfile, facts: dict[str, Fact]
) -> dict[str, Any] | None:
    by_id = {e.id: e for e in profile.experience}
    entries = []
    for index, role in enumerate(resume.experience):
        exp = by_id.get(role.experience_id)
        if exp is None:
            raise UnknownReferenceError(f"experience[{index}]: unknown experience_id {role.experience_id!r}")
        entries.append(_entry(
            exp.title,
            org=exp.company,
            location=exp.location,
            dates=format_range(exp.start, exp.end),
            bullets=_bullets(role.bullets, facts, f"experience[{index}]"),
        ))
    return {"entries": entries} if entries else None


def _projects_section(
    resume: TailoredResume, profile: CareerProfile, facts: dict[str, Fact]
) -> dict[str, Any] | None:
    by_id = {p.id: p for p in profile.projects}
    entries = []
    for index, item in enumerate(resume.projects):
        project = by_id.get(item.project_id)
        if project is None:
            raise UnknownReferenceError(f"projects[{index}]: unknown project_id {item.project_id!r}")
        entries.append(_entry(
            project.name,
            dates=format_range(project.start, project.end),
            link=_link(project.link) if project.link and project.link.strip() else None,
            bullets=_bullets(item.bullets, facts, f"projects[{index}]"),
        ))
    return {"entries": entries} if entries else None


def _education_section(
    resume: TailoredResume, profile: CareerProfile, facts: dict[str, Fact]
) -> dict[str, Any] | None:
    by_id = {e.id: e for e in profile.education}
    entries = []
    for index, item in enumerate(resume.education):
        edu = by_id.get(item.education_id)
        if edu is None:
            raise UnknownReferenceError(f"education[{index}]: unknown education_id {item.education_id!r}")
        title = f"{edu.degree}, {edu.field}" if edu.field else edu.degree
        entries.append(_entry(
            title,
            org=edu.institution,
            dates=format_range(edu.start, edu.end),
            detail=edu.grade,
            bullets=_bullets(item.bullets, facts, f"education[{index}]"),
        ))
    return {"entries": entries} if entries else None


def _skills_section(resume: TailoredResume) -> dict[str, Any] | None:
    groups = []
    for group in resume.skill_groups:
        skills = [s.strip() for s in group.skills if s.strip()]
        if skills:
            groups.append({"label": group.label.strip(), "items": ", ".join(skills)})
    return {"groups": groups} if groups else None


def _certifications_section(resume: TailoredResume, profile: CareerProfile) -> dict[str, Any] | None:
    by_id = {c.id: c for c in profile.certifications}
    items = []
    for cert_id in resume.certification_ids:
        cert = by_id.get(cert_id)
        if cert is None:
            raise UnknownReferenceError(f"certification_ids: unknown certification id {cert_id!r}")
        parts = [cert.name, cert.issuer, format_month(cert.date) if cert.date else None]
        items.append(", ".join(p.strip() for p in parts if p and p.strip()))
    return {"items": items} if items else None
