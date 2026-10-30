"""Database table for match scans: one row per scan that called the AI (a repeated scan reuses the saved row)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, created_at_column


class ScanRow(Base):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    profile_version: Mapped[int]  # the profile version that was scanned
    mode: Mapped[str] = mapped_column(String(10))  # quick | deep
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)  # ScanResult (scans/schemas.py)
    created_at: Mapped[datetime] = created_at_column()

    __table_args__ = (
        Index("ix_scans_user_id_created_at", "user_id", "created_at"),  # "scans today", for the fair-use limit
        Index("ix_scans_user_id_job_id", "user_id", "job_id"),  # "my latest scan of this job"
    )
