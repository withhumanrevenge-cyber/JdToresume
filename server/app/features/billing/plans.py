"""The plans (COSTS §3 / PRD §7) as code: what each one includes and how many packs it allows.

Prices live with the payment provider, not here. When payments arrive, a webhook maps a purchase to one of these
plan ids (or to Deep credits) and calls `BillingService.grant_plan` / `add_deep_credits`, the same functions the
admin CLI uses today.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

PlanId = Literal["free", "sprint", "pro_monthly", "pro_quarter"]
Window = Literal["calendar_month", "rolling_7_days"]


@dataclass(frozen=True)
class Plan:
    id: PlanId
    name: str
    duration: timedelta | None  # how long one purchase lasts; None = never expires (Free)
    deep: bool  # Deep mode included (Free gets Deep only through credits)
    packs: int  # packs allowed per `window`
    window: Window

    @property
    def paid(self) -> bool:
        return self.duration is not None


FREE = Plan("free", "Free", None, deep=False, packs=3, window="calendar_month")
# Paid plans are "unlimited" with a fair-use cap, so a leaked account can't run up an unbounded AI bill.
SPRINT = Plan("sprint", "Sprint pass", timedelta(days=7), deep=True, packs=100, window="rolling_7_days")
PRO_MONTHLY = Plan("pro_monthly", "Pro (monthly)", timedelta(days=30), deep=True, packs=100, window="rolling_7_days")
PRO_QUARTER = Plan("pro_quarter", "Pro (quarter)", timedelta(days=90), deep=True, packs=100, window="rolling_7_days")

PLANS: dict[str, Plan] = {plan.id: plan for plan in (FREE, SPRINT, PRO_MONTHLY, PRO_QUARTER)}

SIGNUP_DEEP_CREDITS = 1  # "1 Deep pack at signup": the first pack shows the best we can do
CREDIT_PACK_DEEP_CREDITS = 10  # India credit pack: ₹99 for 10 Deep packs
SCANS_PER_DAY = 20  # free match scans per UTC day, on every plan ("unlimited, fair use 20/day")


def window_start(window: Window, now: datetime) -> datetime:
    """Where the current counting window began. Months are calendar months in UTC."""
    if window == "calendar_month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return now - timedelta(days=7)


def next_month(now: datetime) -> datetime:
    start = window_start("calendar_month", now)
    return start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
