"""What the job endpoints accept and return."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.llm.schemas import JobSpec


class JobIn(BaseModel):
    """Exactly one of `url` or `text`."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    url: str | None = Field(default=None, max_length=2000, description="A link to the job posting")
    text: str | None = Field(default=None, max_length=30_000, description="The job description, pasted")

    @model_validator(mode="after")
    def _exactly_one(self) -> JobIn:
        if bool(self.url) == bool(self.text):
            raise ValueError("send either 'url' or 'text', not both and not neither")
        return self


class JobOut(BaseModel):
    id: uuid.UUID
    source: str = Field(description="text, ats_feed, embedded_data or page_text")
    ats_vendor: str | None
    url: str | None
    title: str
    company: str | None
    created_at: datetime
    spec: JobSpec
    reused: bool = Field(description="True when this job was already known, so nothing was fetched or parsed")
