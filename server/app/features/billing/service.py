"""Plans, entitlements and usage metering: may this user start a pack, in which mode, and paid for how?

Rules (COSTS §3):
- Free: 3 Quick packs per calendar month (UTC), plus Deep credits (1 at sign-up, more from credit packs).
- Sprint / Pro: Quick and Deep, up to 100 packs in any 7 days (fair use). A plan that ran out is Free again.
- A pack is spent when Generate starts (so parallel presses can't overspend) and given back if the run ends
  without the resume (the AI service failed, the browser left), even when other pieces finished.

Nothing here commits: the caller does, so a pack is spent in the same transaction as the run it pays for.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PaymentRequiredError, TooManyRequestsError
from app.features.billing.models import EntitlementRow, UsageRow
from app.features.billing.plans import (
    FREE, PLANS, SIGNUP_DEEP_CREDITS, Plan, PlanId, next_month, window_start,
)
from app.features.billing.repository import BillingRepository
from app.features.billing.schemas import PackAllowance, PlanOut
from app.llm.router import Mode

ROLLING_WINDOW = timedelta(days=7)


class QuotaExceededError(PaymentRequiredError):
    code = "quota_exceeded"


class UpgradeRequiredError(PaymentRequiredError):
    code = "upgrade_required"


class FairUseLimitError(TooManyRequestsError):
    code = "fair_use_limit"


@dataclass(frozen=True)
class _Window:
    plan: Plan  # the plan in effect now
    used: int  # packs counted against its allowance in the current window
    resets_at: datetime | None


class BillingService:
    def __init__(self, session: AsyncSession):
        self._billing = BillingRepository(session)

    # ----------------------------------------------------------------- reading

    async def plan_status(self, user_id: uuid.UUID, now: datetime) -> PlanOut:
        entitlement = await self._billing.get_entitlement(user_id)
        credits = entitlement.deep_credits if entitlement else SIGNUP_DEEP_CREDITS  # row appears on first pack
        window = await self._window(user_id, entitlement, now)
        plan = window.plan
        if plan.paid:
            next_mode = "deep" if window.used < plan.packs else None
        else:
            next_mode = "deep" if credits > 0 else "quick" if window.used < plan.packs else None
        return PlanOut(
            plan=plan.id,
            name=plan.name,
            expires_at=entitlement.plan_expires_at if plan.paid else None,
            deep_included=plan.deep,
            deep_credits=credits,
            packs=PackAllowance(used=window.used, limit=plan.packs, window=plan.window, resets_at=window.resets_at),
            next_pack_mode=next_mode,
        )

    # ----------------------------------------------------------------- spending and giving back

    async def reserve_pack(self, user_id: uuid.UUID, requested: Mode | None, now: datetime) -> UsageRow:
        """Spend one pack, or raise 402/429. `requested=None` picks the best mode the user has.

        Returns the new ledger row; the caller links it to the run (`usage.run_id`) and commits.
        """
        entitlement = await self._billing.lock_entitlement(user_id, initial_deep_credits=SIGNUP_DEEP_CREDITS)
        window = await self._window(user_id, entitlement, now)
        plan = window.plan

        if plan.paid:
            if window.used >= plan.packs:
                wait = math.ceil((window.resets_at - now).total_seconds()) if window.resets_at else 3600
                raise FairUseLimitError(
                    f"You've generated {plan.packs} packs in the last 7 days, the fair-use limit of your plan",
                    details={"retry_at": window.resets_at.isoformat() if window.resets_at else None},
                    headers={"Retry-After": str(max(wait, 1))},
                )
            return await self._billing.add_usage(user_id, requested or "deep", "plan")

        if requested == "deep" or (requested is None and entitlement.deep_credits > 0):
            if entitlement.deep_credits == 0:
                raise UpgradeRequiredError("Deep packs come with a paid plan or a Deep credit. Quick is included "
                                           "in Free", details={"plan": plan.id})
            entitlement.deep_credits -= 1  # safe: the row is locked
            return await self._billing.add_usage(user_id, "deep", "deep_credit")

        if window.used >= plan.packs:
            raise QuotaExceededError(
                f"You've used this month's {plan.packs} free packs",
                details={"plan": plan.id, "resets_at": window.resets_at.isoformat(),
                         "deep_credits": entitlement.deep_credits},
            )
        return await self._billing.add_usage(user_id, "quick", "free_allowance")

    async def release_run(self, run_id: uuid.UUID) -> None:
        """Give back the pack a run paid with, because the resume never arrived. Does nothing if already given back."""
        usage = await self._billing.usage_for_run(run_id)
        if usage is None:
            return
        usage.refunded_at = datetime.now(UTC)
        if usage.paid_with == "deep_credit":
            await self._billing.add_deep_credits(usage.user_id, 1)

    # ----------------------------------------------------------------- granting (admin CLI now, payment webhooks later)

    async def grant_plan(self, user_id: uuid.UUID, plan_id: PlanId, now: datetime) -> EntitlementRow:
        """Start or extend a paid plan. Time left on a current paid plan is kept: the new period starts when it ends."""
        plan = PLANS[plan_id]
        if not plan.paid:
            raise ValueError("only paid plans can be granted")
        entitlement = await self._billing.lock_entitlement(user_id, initial_deep_credits=SIGNUP_DEEP_CREDITS)
        current = entitlement.plan_expires_at
        starts = current if current is not None and current > now else now
        entitlement.plan = plan.id
        entitlement.plan_expires_at = starts + plan.duration
        return entitlement

    async def add_deep_credits(self, user_id: uuid.UUID, count: int) -> EntitlementRow:
        if count < 1:
            raise ValueError("count must be at least 1")
        entitlement = await self._billing.lock_entitlement(user_id, initial_deep_credits=SIGNUP_DEEP_CREDITS)
        entitlement.deep_credits += count
        return entitlement

    # ----------------------------------------------------------------- helpers

    async def _window(self, user_id: uuid.UUID, entitlement: EntitlementRow | None, now: datetime) -> _Window:
        """The plan in effect and how much of its allowance is used."""
        plan = PLANS.get(entitlement.plan, FREE) if entitlement else FREE
        if plan.paid and (entitlement.plan_expires_at is None or entitlement.plan_expires_at <= now):
            plan = FREE
        paid_with = "plan" if plan.paid else "free_allowance"  # which ledger rows count against this plan
        used, oldest = await self._billing.count_packs(user_id, paid_with, window_start(plan.window, now))
        if plan.window == "calendar_month":
            resets_at = next_month(now)
        else:
            resets_at = oldest + ROLLING_WINDOW if oldest else None
        return _Window(plan=plan, used=used, resets_at=resets_at)
