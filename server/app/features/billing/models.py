"""Database tables for plans and usage.

- `entitlements`: one row per user: the plan they bought (and when it runs out) and their Deep credit balance.
  Created the first time it's needed, with the sign-up Deep credit.
- `usage_ledger`: one row per pack a user started, saying how it was paid for. Free allowances and fair-use caps
  are counted from it. Its link to the run is SET NULL on delete, so deleting an application never gives packs back.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, created_at_column


class EntitlementRow(Base):
    __tablename__ = "entitlements"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    plan: Mapped[str] = mapped_column(String(20), server_default="free")  # a PlanId (billing/plans.py)
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # None on Free
    deep_credits: Mapped[int] = mapped_column(server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (CheckConstraint("deep_credits >= 0", name="deep_credits_not_negative"),)
    __mapper_args__ = {"eager_defaults": True}


class UsageRow(Base):
    __tablename__ = "usage_ledger"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("generation_runs.id", ondelete="SET NULL"))
    mode: Mapped[str] = mapped_column(String(10))  # quick | deep
    paid_with: Mapped[str] = mapped_column(String(20))  # free_allowance | deep_credit | plan
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # the run ended without the resume
    created_at: Mapped[datetime] = created_at_column()

    __table_args__ = (Index("ix_usage_ledger_user_id_created_at", "user_id", "created_at"),)  # "packs this month"
