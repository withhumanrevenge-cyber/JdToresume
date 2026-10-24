"""Plan endpoint: which plan I'm on and how many packs I have left. (Buying arrives with the payment provider.)"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.features.billing.dependencies import BillingServiceDep
from app.features.billing.schemas import PlanOut
from app.features.users.dependencies import CurrentUser

router = APIRouter(prefix="/me", tags=["account"])


@router.get("/plan", response_model=PlanOut, summary="My plan, packs used and left, and Deep credits")
async def read_plan(user: CurrentUser, billing: BillingServiceDep) -> PlanOut:
    return await billing.plan_status(user.id, datetime.now(UTC))
