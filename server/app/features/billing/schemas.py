"""What the API returns about a user's plan and usage."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.features.billing.plans import PlanId, Window
from app.llm.router import Mode


class PackAllowance(BaseModel):
    used: int
    limit: int
    window: Window = Field(description="calendar_month (Free, UTC) or rolling_7_days (fair use on paid plans)")
    resets_at: datetime | None = Field(
        description="Free: start of next month. Paid: when the oldest counted pack leaves the 7-day window")


class PlanOut(BaseModel):
    plan: PlanId = Field(description="The plan in effect now (a paid plan that ran out shows as free)")
    name: str
    expires_at: datetime | None
    deep_included: bool
    deep_credits: int = Field(description="Deep packs on top of the plan (1 at sign-up, credit packs)")
    packs: PackAllowance
    next_pack_mode: Mode | None = Field(
        description="What a Generate without `mode` would use right now; null when nothing is left")
