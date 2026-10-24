"""Database table for applications: one row per job a user is preparing (or has sent) an application for."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, created_at_column


class ApplicationRow(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), server_default="draft")  # the tracker adds more states later
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_applications_user_id_job_id"),  # one per job per person
        Index("ix_applications_user_id_created_at", "user_id", "created_at"),  # "my applications, newest first"
    )
    __mapper_args__ = {"eager_defaults": True}  # read status/updated_at back right after saving
