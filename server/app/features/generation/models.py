"""Database tables for generating application packs.

- `generation_runs`: one row per "Generate" press: which profile version it used, how it went, what it cost.
- `artifacts`: the pieces a run produced (match_report, resume, cover_letter, outreach), each saved the moment
  it's ready, so a dropped connection never loses finished work.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, created_at_column


class GenerationRunRow(Base):
    __tablename__ = "generation_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    profile_version: Mapped[int]  # the exact profile version the pack was written from
    mode: Mapped[str] = mapped_column(String(10))  # deep | quick
    status: Mapped[str] = mapped_column(String(12))  # running | succeeded | failed | cancelled
    error: Mapped[str | None] = mapped_column(String(40))  # a short code, never user data
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6, asdecimal=False), server_default="0")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_generation_runs_application_id_started_at", "application_id", "started_at"),)
    __mapper_args__ = {"eager_defaults": True}


class ArtifactRow(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generation_runs.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))  # match_report | resume | cover_letter | outreach
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at_column()

    __table_args__ = (UniqueConstraint("run_id", "kind", name="uq_artifacts_run_id_kind"),)
