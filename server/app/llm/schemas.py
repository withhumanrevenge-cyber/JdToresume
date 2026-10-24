"""Pydantic contracts for every pipeline step.

Design rules (see .claude/skills/llm-pipeline-standards):
- Every LLM step returns one of these models via Groq strict structured outputs, so the JSON schema must be
  "strict-compatible": all properties required, optional = `X | None`, no dict-typed fields, no `const`,
  no numeric/length constraints (use descriptions instead). `strict_json_schema()` enforces the rest.
- The LLM never outputs layout or employer facts it could inflate: a tailored role references `experience_id`
  and the renderer pulls title/company/dates from the CareerProfile.
- Contact details live in `ContactDetails`, which is never sent to the LLM.
"""

from __future__ import annotations

import copy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- career profile

_DATE = "YYYY-MM, or just YYYY when the source shows only the year. Never invent a month."


class Fact(Strict):
    id: str = Field(description="Stable id, e.g. 'f-acme-3'. Never reuse ids.")
    text: str = Field(description="One atomic, verifiable statement in the user's own words.")
    metrics: list[str] = Field(description="Numbers/quantities exactly as stated in the source, e.g. '40%', '2M events/day'.")
    skills: list[str] = Field(description="Skills/tools this fact demonstrates, spelled as in the source.")
    source: Literal["upload", "answer", "edit"]


class Experience(Strict):
    id: str
    company: str
    title: str
    location: str | None
    start: str = Field(description=_DATE)
    end: str | None = Field(description=f"{_DATE} Null if current role.")
    facts: list[Fact]


class Project(Strict):
    id: str
    name: str
    link: str | None
    start: str | None = Field(description=f"{_DATE} Null if not stated.")
    end: str | None = Field(description=f"{_DATE} Null if not stated.")
    facts: list[Fact]


class Education(Strict):
    id: str
    institution: str
    degree: str
    field: str | None
    start: str | None = Field(description=f"{_DATE} Null if not stated.")
    end: str | None = Field(description=f"{_DATE} Null if not stated.")
    grade: str | None = Field(description="e.g. 'CGPA 8.4/10' or 'GPA 3.7/4.0', exactly as in source")
    facts: list[Fact]


class Certification(Strict):
    id: str
    name: str
    issuer: str | None
    date: str | None = Field(description=f"{_DATE} Null if not stated.")


class Skill(Strict):
    name: str
    evidence_fact_ids: list[str] = Field(description="Facts proving this skill. Empty = declared by the user without evidence.")


class Preferences(Strict):
    target_roles: list[str]
    region: Literal["US", "CA", "UK", "IE", "IN", "DE", "AE", "AU", "OTHER"]
    page_limit: int | None
    spelling: Literal["en-US", "en-GB", "en-IN", "en-AU", "en-CA"]


class StyleProfile(Strict):
    avg_bullet_words: int
    number_style: str = Field(description="How the user writes numbers, e.g. 'digits with % sign; 2M not 2,000,000'")
    voice_samples: list[str] = Field(description="2-4 verbatim bullets from the user's original resume")
    notes: str


class CareerProfile(Strict):
    schema_version: int = Field(description="Always 1 for now")
    headline: str
    summary_facts: list[Fact]
    experience: list[Experience]
    projects: list[Project]
    education: list[Education]
    certifications: list[Certification]
    skills: list[Skill]
    languages: list[str]
    awards: list[Fact]
    preferences: Preferences
    style: StyleProfile

    def all_facts(self) -> dict[str, Fact]:
        facts: list[Fact] = [*self.summary_facts, *self.awards]
        for group in (self.experience, self.projects, self.education):
            for item in group:
                facts.extend(item.facts)
        return {f.id: f for f in facts}


class ContactDetails(Strict):
    """PII. Never sent to the LLM; merged in at render time only."""
    full_name: str
    email: str
    phone: str | None
    city: str | None
    links: list[str]


# --------------------------------------------------------------------------- job spec

class Requirement(Strict):
    id: str = Field(description="'r1', 'r2', ... in order of appearance")
    text: str = Field(description="The requirement as written in the posting (trimmed)")
    kind: Literal["skill", "tool", "cert", "degree", "years", "domain", "language", "other"]
    tier: Literal["basic", "preferred"] = Field(description="basic = required/must-have; preferred = nice-to-have/bonus")
    evidence_terms: list[str] = Field(description="Exact terms a matching resume would contain, JD spelling first")


class Keyword(Strict):
    term: str = Field(description="Exact spelling used in the posting")
    synonyms: list[str]
    weight: int = Field(description="1 = mentioned once, 2 = important, 3 = central to the role")


class SalaryRange(Strict):
    min: float | None
    max: float | None
    currency: str | None
    period: Literal["year", "month", "hour"] | None


class JobSpec(Strict):
    title: str
    company: str | None
    location: str | None
    remote_policy: Literal["onsite", "hybrid", "remote", "unknown"]
    seniority: Literal["intern", "entry", "mid", "senior", "lead", "executive", "unknown"]
    employment_type: Literal["full_time", "part_time", "contract", "internship", "unknown"]
    visa_sponsorship: Literal["yes", "no", "unknown"]
    salary: SalaryRange | None
    requirements: list[Requirement]
    responsibilities: list[str]
    keywords: list[Keyword]
    company_signals: list[str] = Field(description="Concrete facts about the company/team from the posting, usable as a cover-letter hook")
    application_questions: list[str]
    language: str = Field(description="ISO 639-1 code of the posting language")
    unreadable_fields: list[str] = Field(description="Fields that could not be determined; never guess")


# --------------------------------------------------------------------------- match report

class RequirementMatch(Strict):
    requirement_id: str
    status: Literal["evidenced", "partial", "gap"]
    evidence_fact_ids: list[str]
    note: str = Field(description="One short sentence: why this status")


class FactRelevance(Strict):
    fact_id: str
    score: int = Field(description="0 = irrelevant, 1 = weak, 2 = relevant, 3 = directly evidences a basic requirement")


class GapQuestion(Strict):
    requirement_id: str
    question: str = Field(description="Short question to the user, answerable in one line")


class MatchReport(Strict):
    requirement_matches: list[RequirementMatch]
    fact_relevance: list[FactRelevance]
    keyword_plan: list[str] = Field(description="JD terms the resume can use truthfully, exact JD spelling")
    angle: str = Field(description="1-2 sentences: how to position this candidate for this job")
    gap_questions: list[GapQuestion]


# --------------------------------------------------------------------------- tailored resume

SectionName = Literal["summary", "experience", "projects", "education", "skills", "certifications"]


class Bullet(Strict):
    text: str
    source_fact_ids: list[str] = Field(description="Profile fact ids that support EVERY claim in this bullet. Never empty.")
    targets_requirement_ids: list[str]


class ResumeRole(Strict):
    experience_id: str = Field(description="Id of a CareerProfile.experience entry; title/company/dates come from the profile")
    bullets: list[Bullet]


class ResumeProject(Strict):
    project_id: str
    bullets: list[Bullet]


class ResumeEducation(Strict):
    education_id: str
    bullets: list[Bullet]


class SkillGroup(Strict):
    label: str = Field(description="e.g. 'Languages', 'Cloud & Infra'")
    skills: list[str]


class TailoredResume(Strict):
    summary: str
    summary_source_fact_ids: list[str]
    section_order: list[SectionName]
    experience: list[ResumeRole]
    projects: list[ResumeProject]
    education: list[ResumeEducation]
    skill_groups: list[SkillGroup]
    certification_ids: list[str]


# --------------------------------------------------------------------------- verify, letters, outreach

class Violation(Strict):
    location: str = Field(description="Path such as 'experience[0].bullets[2]' or 'summary'")
    kind: Literal["unsupported_claim", "inflated_number", "inflated_scope", "title_change", "new_skill",
                  "banned_phrase", "generic", "other"]
    quote: str
    explanation: str
    severity: Literal["high", "medium", "low"]


class VerifyReport(Strict):
    violations: list[Violation]


class CoverLetter(Strict):
    salutation: str
    paragraphs: list[str]
    closing: str = Field(description="e.g. 'Best regards,' — the name placeholder is added by the renderer")
    source_fact_ids: list[str]
    addressed_gap_requirement_ids: list[str]


class OutreachPack(Strict):
    recruiter_email_subject: str
    recruiter_email_body: str
    linkedin_note: str = Field(description="200 characters or fewer")
    referral_ask: str
    follow_up: str
    source_fact_ids: list[str]


# --------------------------------------------------------------------------- eval judge

class JudgeScores(Strict):
    truthfulness: int = Field(description="1-5")
    relevance: int = Field(description="1-5")
    specificity: int = Field(description="1-5")
    voice: int = Field(description="1-5, sounds like a sharp human, not generic AI")
    readability: int = Field(description="1-5, 7-second recruiter skim")


class PairwiseVerdict(Strict):
    scores_a: JudgeScores
    scores_b: JudgeScores
    winner: Literal["A", "B", "tie"]
    rationale: str


# --------------------------------------------------------------------------- strict JSON schema for Groq

_DROP_KEYS = {"title", "default", "examples"}


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema accepted by Groq strict mode: every object closed, every property required.

    `properties` and `$defs` are name->schema maps, so their keys are never dropped (a field may be called "title").
    """
    schema = copy.deepcopy(model.model_json_schema())

    def fix(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                fix(item)
            return
        if not isinstance(node, dict):
            return
        for key in _DROP_KEYS:
            node.pop(key, None)
        props = node.get("properties")
        if isinstance(props, dict):
            node["additionalProperties"] = False
            node["required"] = list(props)
        for key, value in node.items():
            if key in ("properties", "$defs") and isinstance(value, dict):
                for sub in value.values():
                    fix(sub)
            else:
                fix(value)

    fix(schema)
    return schema
