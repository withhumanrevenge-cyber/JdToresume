"""Database table for job postings.

Two kinds of rows:
- **Shared** (`owner_user_id` is NULL): read from a public link. One row per canonical URL serves every user, so a
  popular job is fetched and parsed once (the partial unique index enforces "one per URL").
- **Private** (`owner_user_id` set): pasted text. Only its owner can see it. Pasting the same text twice reuses
  the row (matched by `content_hash`).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, created_at_column


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(20))  # text | ats_feed | embedded_data | page_text
    ats_vendor: Mapped[str | None] = mapped_column(String(20))
    canonical_url: Mapped[str | None] = mapped_column(Text)
    url_hash: Mapped[str | None] = mapped_column(String(64))
    content_hash: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(300))  # copied out of `spec` so lists don't need to read the JSON
    company: Mapped[str | None] = mapped_column(String(300))
    raw_text: Mapped[str] = mapped_column(Text)  # kept so the posting can be re-parsed when prompts improve
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB)  # a JobSpec (app/llm/schemas.py)
    created_at: Mapped[datetime] = created_at_column()

    __table_args__ = (
        Index("uq_jobs_shared_url_hash", "url_hash", unique=True, postgresql_where=text("owner_user_id IS NULL")),
        Index("ix_jobs_owner_content_hash", "owner_user_id", "content_hash"),
    )

    def is_visible_to(self, user_id: uuid.UUID) -> bool:
        """Shared jobs are visible to everyone; a pasted job only to the person who pasted it."""
        return self.owner_user_id is None or self.owner_user_id == user_id
