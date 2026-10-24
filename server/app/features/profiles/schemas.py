"""What the profile endpoints accept and return.

The profile document itself is the shared `CareerProfile` contract (app/llm/schemas.py) that every pipeline step
uses, so what the user edits is exactly what the AI reads.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.llm.schemas import CareerProfile, ContactDetails


class ProfileOut(BaseModel):
    version: int
    created_at: datetime
    profile: CareerProfile


class ProfileUpdateIn(BaseModel):
    base_version: int = Field(
        ge=0,
        description="The version you loaded and edited (0 if there is no profile yet). "
        "If a newer version was saved in the meantime, the save is refused with 409 instead of overwriting it.",
    )
    profile: CareerProfile


Link = Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=300)]


class ContactIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=50)
    city: str | None = Field(default=None, max_length=120)
    links: list[Link] = Field(default_factory=list, max_length=10)


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: str
    email: str
    phone: str | None
    city: str | None
    links: list[str]
    updated_at: datetime


class ResumeImportOut(BaseModel):
    profile: ProfileOut
    contact: ContactOut | None = Field(description="The saved contact details (None until name and email are known)")
    detected_contact: ContactDetails = Field(description="What was found in this file, for the user to confirm")
    facts_without_numbers: int = Field(description="Facts with no metric; worth asking the user for numbers")
