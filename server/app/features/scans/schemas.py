"""What the scan endpoints accept and return."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.llm.schemas import MatchReport


class ScanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: uuid.UUID = Field(description="A job from POST /v1/jobs")


class ScanResult(BaseModel):
    """What a scan found. Stored as is, so a repeated scan returns exactly the same answer."""

    match_report: MatchReport
    keyword_coverage: float | None = Field(description="Share of the job's keywords already in the profile; null if the job lists none")
    keywords_found: list[str]
    keywords_missing: list[str]
    must_have_coverage: float | None = Field(
        description="Share of must-have requirements whose evidence terms appear in the profile; null if none can be checked")


class ScanOut(ScanResult):
    id: uuid.UUID
    job_id: uuid.UUID
    profile_version: int
    created_at: datetime
    stale: bool = Field(description="True when the profile has a newer version than the one scanned: scan again")
    scans_left_today: int = Field(description="Free scans left before the daily fair-use limit (resets 00:00 UTC)")
