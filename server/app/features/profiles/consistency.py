"""Consistency checks for a CareerProfile that Pydantic's type checks can't express.

Every later step relies on these holding: resumes cite facts by id, the renderer looks roles up by id, and dates
are formatted from `YYYY-MM` (or `YYYY` when the source shows only the year). Used when a user saves an edited profile (a 422 lists the problems) and on the LLM's
parse output (a 502, because the problem is ours, not the user's).
"""

from __future__ import annotations

import re
from collections import Counter

from app.llm.schemas import CareerProfile

_DATE = re.compile(r"^\d{4}(-(0[1-9]|1[0-2]))?$")  # "2023-06", or just "2023" when the month is unknown


def find_problems(profile: CareerProfile) -> list[str]:
    problems: list[str] = []

    # 1. Ids are unique across the whole profile.
    ids = [entry.id for group in (profile.experience, profile.projects, profile.education, profile.certifications)
           for entry in group]
    fact_ids = [fact.id for fact in _all_facts(profile)]
    for duplicate in sorted(id_ for id_, n in Counter(ids + fact_ids).items() if n > 1):
        problems.append(f"id {duplicate!r} is used more than once")

    # 2. Skill evidence points at facts that exist.
    known_facts = set(fact_ids)
    for skill in profile.skills:
        for fact_id in skill.evidence_fact_ids:
            if fact_id not in known_facts:
                problems.append(f"skill {skill.name!r} cites unknown fact {fact_id!r}")

    # 3. Dates use YYYY-MM (or YYYY) and never end before they start.
    ranges = [(f"experience {e.id}", e.start, e.end) for e in profile.experience]
    ranges += [(f"project {p.id}", p.start, p.end) for p in profile.projects]
    ranges += [(f"education {e.id}", e.start, e.end) for e in profile.education]
    dates = [(where, label, value) for where, start, end in ranges
             for label, value in (("start date", start), ("end date", end))]
    dates += [(f"certification {c.id}", "date", c.date) for c in profile.certifications]
    for where, label, value in dates:
        if value is not None and not _DATE.match(value):
            problems.append(f"{where}: {label} {value!r} should look like 2023-06, or 2023 if the month isn't known")
    for where, start, end in ranges:
        if start and end and _DATE.match(start) and _DATE.match(end) and _ends_before(start, end):
            problems.append(f"{where}: ends ({end}) before it starts ({start})")

    return problems


def _ends_before(start: str, end: str) -> bool:
    """Compared at the coarser precision: "2019-06" to "2019" is a range within 2019, not a backwards one."""
    n = min(len(start), len(end))
    return end[:n] < start[:n]


def _all_facts(profile: CareerProfile):
    yield from profile.summary_facts
    yield from profile.awards
    for group in (profile.experience, profile.projects, profile.education):
        for entry in group:
            yield from entry.facts
