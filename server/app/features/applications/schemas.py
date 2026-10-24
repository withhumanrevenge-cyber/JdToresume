"""What the application endpoints accept and return."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.features.generation.pipeline import CoverLetterOutcome, OutreachOutcome, ResumeOutcome
from app.llm.schemas import MatchReport


class ApplicationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: uuid.UUID = Field(description="A job from POST /v1/jobs")


class JobSummary(BaseModel):
    id: uuid.UUID
    title: str
    company: str | None
    url: str | None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mode: str
    status: str = Field(description="running, succeeded, failed or cancelled")
    profile_version: int
    cost_usd: float
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class ApplicationOut(BaseModel):
    id: uuid.UUID
    status: str
    created_at: datetime
    job: JobSummary
    latest_run: RunOut | None


class ApplicationPage(BaseModel):
    items: list[ApplicationOut]
    next_before: datetime | None = Field(description="Pass as `before` to get the next page; null on the last page")


class Pieces(BaseModel):
    """A run's finished pieces; each is null until it's done. The generate stream sends these same shapes."""

    match_report: MatchReport | None = None
    resume: ResumeOutcome | None = None
    cover_letter: CoverLetterOutcome | None = None
    outreach: OutreachOutcome | None = None


class ApplicationDetailOut(ApplicationOut):
    pieces: Pieces = Field(description="The latest run's finished pieces")
