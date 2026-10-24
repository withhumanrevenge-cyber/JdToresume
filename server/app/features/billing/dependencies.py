"""FastAPI dependency for the billing service."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.core.db import SessionDep
from app.features.billing.service import BillingService


def get_billing_service(session: SessionDep) -> BillingService:
    return BillingService(session)


BillingServiceDep = Annotated[BillingService, Depends(get_billing_service)]
