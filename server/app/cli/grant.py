"""Give a user a paid plan or Deep credits, by email (admin tool; Phase 0 pilot users, comps, goodwill refunds).

    .venv/Scripts/python.exe -m app.cli.grant --email jordan@example.com --plan sprint
    .venv/Scripts/python.exe -m app.cli.grant --email jordan@example.com --deep-credits 10

It calls the same BillingService functions the payment webhooks will call. The user must have signed in once.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
from typing import get_args

from sqlalchemy import func, select

import app.models  # noqa: F401  (registers every table)
from app.core.config import get_settings
from app.core.db import Database
from app.features.billing.plans import PLANS, PlanId
from app.features.billing.service import BillingService
from app.features.users.models import UserRow


async def grant(database: Database, email: str, plan: PlanId | None, deep_credits: int | None) -> str:
    """Apply the grant and describe what was done (or why nothing was)."""
    async with database.sessions() as session:
        user = await session.scalar(select(UserRow).where(func.lower(UserRow.email) == email.lower()))
        if user is None:
            return f"No user with email {email}: they need to sign in once first"
        billing = BillingService(session)
        done = []
        if plan:
            entitlement = await billing.grant_plan(user.id, plan, datetime.now(UTC))
            done.append(f"{PLANS[plan].name} until {entitlement.plan_expires_at:%Y-%m-%d %H:%M} UTC")
        if deep_credits:
            entitlement = await billing.add_deep_credits(user.id, deep_credits)
            done.append(f"{deep_credits} Deep credits (balance {entitlement.deep_credits})")
        await session.commit()
        return f"{email}: " + "; ".join(done)


async def _run(email: str, plan: PlanId | None, deep_credits: int | None) -> str:
    database = Database(get_settings().database_url)
    try:
        return await grant(database, email, plan, deep_credits)
    finally:
        await database.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True)
    parser.add_argument("--plan", choices=[p for p in get_args(PlanId) if PLANS[p].paid])
    parser.add_argument("--deep-credits", type=int)
    args = parser.parse_args()
    if not args.plan and not args.deep_credits:
        parser.error("give --plan, --deep-credits, or both")
    if args.deep_credits is not None and args.deep_credits < 1:
        parser.error("--deep-credits must be at least 1")
    print(asyncio.run(_run(args.email, args.plan, args.deep_credits)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
