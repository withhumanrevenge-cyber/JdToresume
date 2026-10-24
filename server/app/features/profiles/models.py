"""Database tables for what we know about a user's career.

- `contact_details`: name, email, phone, city, links. Kept apart from everything else because it is the part
  that must never be sent to the LLM (CLAUDE.md non-negotiable #2).
- `career_profiles`: the structured career profile (a `CareerProfile` from app/llm/schemas.py) stored as JSONB.
  Edits never overwrite: every change inserts a new row with `version + 1`, so a generated resume can always point
  at the exact profile version it was made from. The current profile is the highest version.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.llm.schemas import ContactDetails

from app.core.db import Base, created_at_column


class ContactDetailsRow(Base):
    __tablename__ = "contact_details"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(50))
    city: Mapped[str | None] = mapped_column(String(120))
    links: Mapped[list[str]] = mapped_column(JSONB, server_default="[]")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Read database-generated values (updated_at) back right after INSERT/UPDATE, so they can be returned.
    __mapper_args__ = {"eager_defaults": True}

    def to_contact(self) -> ContactDetails:
        return ContactDetails(full_name=self.full_name, email=self.email, phone=self.phone, city=self.city,
                              links=list(self.links))


class CareerProfileRow(Base):
    __tablename__ = "career_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    version: Mapped[int]
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at_column()

    __table_args__ = (
        # Also serves as the index for "latest version of this user's profile" lookups.
        UniqueConstraint("user_id", "version", name="uq_career_profiles_user_id_version"),
        CheckConstraint("version >= 1", name="version_positive"),
    )
