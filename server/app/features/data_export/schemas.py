"""The account export file: everything we store about a person, in a stable, documented shape (format_version 1).

Our internal figures (what each AI call cost us, prompt versions) are left out: they are about our business, not
about the person.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.llm.schemas import ContactDetails


class ExportedAccount(BaseModel):
    id: uuid.UUID
    email: str
    created_at: datetime


class ExportedProfileVersion(BaseModel):
    version: int
    created_at: datetime
    profile: dict[str, Any] = Field(description="A CareerProfile")


class ExportedJob(BaseModel):
    id: uuid.UUID
    title: str
    company: str | None
    url: str | None
    added_by_you: bool = Field(description="False for a public posting that other people's applications share")
    created_at: datetime
    spec: dict[str, Any] = Field(description="The job as we read it (a JobSpec)")
    text: str | None = Field(description="The text you pasted or we read for you; only for jobs you added")


class ExportedRun(BaseModel):
    id: uuid.UUID
    mode: str
    status: str
    profile_version: int
    started_at: datetime
    finished_at: datetime | None
    pieces: dict[str, Any] = Field(description="kind -> content: match_report, resume, cover_letter, outreach")


class ExportedApplication(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    status: str
    created_at: datetime
    runs: list[ExportedRun]


class ExportedPlan(BaseModel):
    plan: str
    plan_expires_at: datetime | None
    deep_credits: int


class ExportedUsage(BaseModel):
    created_at: datetime
    mode: str
    paid_with: str
    run_id: uuid.UUID | None
    refunded_at: datetime | None


class ExportedScan(BaseModel):
    created_at: datetime
    job_id: uuid.UUID
    profile_version: int
    result: dict[str, Any] = Field(description="What the scan found (match report and keyword coverage)")


class ExportedAiCall(BaseModel):
    created_at: datetime
    purpose: str
    step: str
    model: str = Field(description="Which AI model processed your data")


class AccountExport(BaseModel):
    format_version: Literal[1] = 1
    exported_at: datetime
    account: ExportedAccount
    contact_details: ContactDetails | None
    profile_versions: list[ExportedProfileVersion]
    jobs: list[ExportedJob]
    applications: list[ExportedApplication]
    plan: ExportedPlan | None
    usage: list[ExportedUsage]
    scans: list[ExportedScan]
    ai_calls: list[ExportedAiCall]
