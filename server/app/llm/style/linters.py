"""Deterministic checks that run on every generated artifact (production Verifier + eval graders).

They never call the LLM. A finding with severity "high" blocks shipping the artifact until revised.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from app.core.text import normalize_key, term_present
from app.llm.schemas import Bullet, CareerProfile, CoverLetter, OutreachPack, TailoredResume

Severity = Literal["high", "medium", "low"]
_BANNED_FILE = Path(__file__).with_name("banned_phrases.txt")
_NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)")


@dataclass(frozen=True)
class Finding:
    check: str
    location: str
    message: str
    severity: Severity


@lru_cache(maxsize=1)
def banned_phrases() -> tuple[tuple[str, bool], ...]:
    """(phrase, soft) pairs from banned_phrases.txt."""
    out = []
    for raw in _BANNED_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append((line.lstrip("~").lower(), line.startswith("~")))
    return tuple(out)


def _phrase_regex(phrase: str) -> re.Pattern[str]:
    return re.compile(r"(?<![\w-])" + re.escape(phrase) + r"(?![\w-])", re.IGNORECASE)


def find_banned(text: str) -> list[tuple[str, bool]]:
    return [(p, soft) for p, soft in banned_phrases() if _phrase_regex(p).search(text)]


def _numbers(text: str) -> set[float]:
    values = set()
    for match in _NUMBER.findall(text):
        try:
            values.add(float(match.replace(",", "")))
        except ValueError:
            continue
    return values


_norm = normalize_key


@lru_cache(maxsize=1)
def skill_implications() -> dict[str, frozenset[str]]:
    implied: dict[str, set[str]] = {}
    for raw in Path(__file__).with_name("skill_implications.txt").read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if "->" in line:
            src, dst = (part.strip() for part in line.split("->", 1))
            implied.setdefault(_norm(src), set()).add(_norm(dst))
    return {k: frozenset(v) for k, v in implied.items()}


def supported_skills(profile: CareerProfile) -> set[str]:
    """Normalized skills the profile supports, closed over skill_implications.txt."""
    facts = profile.all_facts()
    known = {_norm(s.name) for s in profile.skills} | {_norm(s) for f in facts.values() for s in f.skills}
    implications = skill_implications()
    frontier = list(known)
    while frontier:
        for implied in implications.get(frontier.pop(), ()):
            if implied not in known:
                known.add(implied)
                frontier.append(implied)
    return known


def resume_bullets(resume: TailoredResume) -> list[tuple[str, Bullet]]:
    items: list[tuple[str, Bullet]] = []
    for i, role in enumerate(resume.experience):
        items += [(f"experience[{i}].bullets[{j}]", b) for j, b in enumerate(role.bullets)]
    for i, proj in enumerate(resume.projects):
        items += [(f"projects[{i}].bullets[{j}]", b) for j, b in enumerate(proj.bullets)]
    for i, edu in enumerate(resume.education):
        items += [(f"education[{i}].bullets[{j}]", b) for j, b in enumerate(edu.bullets)]
    return items


def resume_text(resume: TailoredResume) -> str:
    parts = [resume.summary, *(b.text for _, b in resume_bullets(resume))]
    parts += [", ".join(g.skills) for g in resume.skill_groups]
    return "\n".join(parts)


def lint_resume(resume: TailoredResume, profile: CareerProfile) -> list[Finding]:
    facts = profile.all_facts()
    findings: list[Finding] = []

    # References must exist: headers are resolved from the profile, so a bad id would render nothing or crash.
    exp_ids = {e.id for e in profile.experience}
    proj_ids = {p.id for p in profile.projects}
    edu_ids = {e.id for e in profile.education}
    cert_ids = {c.id for c in profile.certifications}
    for i, role in enumerate(resume.experience):
        if role.experience_id not in exp_ids:
            findings.append(Finding("reference", f"experience[{i}]", f"unknown experience_id {role.experience_id!r}", "high"))
    for i, proj in enumerate(resume.projects):
        if proj.project_id not in proj_ids:
            findings.append(Finding("reference", f"projects[{i}]", f"unknown project_id {proj.project_id!r}", "high"))
    for i, edu in enumerate(resume.education):
        if edu.education_id not in edu_ids:
            findings.append(Finding("reference", f"education[{i}]", f"unknown education_id {edu.education_id!r}", "high"))
    for cid in resume.certification_ids:
        if cid not in cert_ids:
            findings.append(Finding("reference", "certification_ids", f"unknown certification id {cid!r}", "high"))

    # Provenance: every bullet cites existing facts, and every number in it appears in those facts.
    checks = [("summary", resume.summary, resume.summary_source_fact_ids)]
    checks += [(loc, b.text, b.source_fact_ids) for loc, b in resume_bullets(resume)]
    for loc, text, cited in checks:
        if not cited:
            findings.append(Finding("provenance", loc, "no source_fact_ids", "high"))
            continue
        missing = [fid for fid in cited if fid not in facts]
        if missing:
            findings.append(Finding("provenance", loc, f"cites unknown facts {missing}", "high"))
        source_text = " ".join(f"{facts[f].text} {' '.join(facts[f].metrics)}" for f in cited if f in facts)
        if loc == "summary":  # years of experience are derived from dates, so allow small integers there
            source_text += " " + " ".join(str(n) for n in range(1, 41))
        unsupported = sorted(_numbers(text) - _numbers(source_text))
        if unsupported:
            nums = ", ".join(f"{n:g}" for n in unsupported)
            findings.append(Finding("numbers", loc, f"numbers not in cited facts: {nums}", "high"))

    # Skills must be supported by the profile: declared, attached to a fact, named in a fact's text,
    # or clearly implied by an evidenced skill (skill_implications.txt, e.g. PostgreSQL -> SQL).
    known = supported_skills(profile)
    fact_text = "\n".join(f.text for f in facts.values())
    for group in resume.skill_groups:
        for skill in group.skills:
            if _norm(skill) not in known and not term_present(skill, fact_text):
                findings.append(Finding("new_skill", f"skill_groups[{group.label}]", f"skill not in profile: {skill!r}", "high"))

    # Voice and shape.
    for loc, text, _ in checks:
        for phrase, _soft in find_banned(text):
            findings.append(Finding("banned_phrase", loc, f"banned phrase: {phrase!r}", "medium"))
        words = len(text.split())
        if loc != "summary" and not 6 <= words <= 40:
            findings.append(Finding("length", loc, f"bullet has {words} words (expected ~14-28)", "low"))
    if resume_text(resume).count("—") > 2:
        findings.append(Finding("style", "resume", "more than 2 em dashes", "low"))
    return findings


def lint_cover_letter(letter: CoverLetter, profile: CareerProfile) -> list[Finding]:
    findings: list[Finding] = []
    body = "\n".join(letter.paragraphs)
    words = len(body.split())
    if not 200 <= words <= 400:
        findings.append(Finding("length", "cover_letter", f"{words} words (target 250-350)", "low"))
    soft_hits = 0
    for phrase, soft in find_banned(body):
        if soft:
            soft_hits += 1
        else:
            findings.append(Finding("banned_phrase", "cover_letter", f"banned phrase: {phrase!r}", "medium"))
    if soft_hits > 1:
        findings.append(Finding("banned_phrase", "cover_letter", f"{soft_hits} connector clichés (max 1)", "low"))
    facts = profile.all_facts()
    unknown = [f for f in letter.source_fact_ids if f not in facts]
    if unknown:
        findings.append(Finding("provenance", "cover_letter", f"cites unknown facts {unknown}", "high"))
    allowed = " ".join(f"{facts[f].text} {' '.join(facts[f].metrics)}" for f in letter.source_fact_ids if f in facts)
    unsupported = sorted(_numbers(body) - _numbers(allowed) - set(range(0, 41)))
    if unsupported:
        findings.append(Finding("numbers", "cover_letter", f"numbers not in cited facts: {', '.join(f'{n:g}' for n in unsupported)}", "medium"))
    return findings


def lint_outreach(pack: OutreachPack) -> list[Finding]:
    findings: list[Finding] = []
    if len(pack.linkedin_note) > 200:
        findings.append(Finding("length", "linkedin_note", f"{len(pack.linkedin_note)} chars (max 200)", "medium"))
    for field, limit in (("recruiter_email_body", 120), ("referral_ask", 100), ("follow_up", 80)):
        words = len(getattr(pack, field).split())
        if words > limit * 1.15:
            findings.append(Finding("length", field, f"{words} words (max {limit})", "low"))
    text = "\n".join([pack.recruiter_email_subject, pack.recruiter_email_body, pack.linkedin_note, pack.referral_ask, pack.follow_up])
    for phrase, soft in find_banned(text):
        if not soft:
            findings.append(Finding("banned_phrase", "outreach", f"banned phrase: {phrase!r}", "medium"))
    return findings
