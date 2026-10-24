"""Database queries for entitlements and the usage ledger. Only data access lives here; the rules are in service.py."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.billing.models import EntitlementRow, UsageRow


class BillingRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    # ----------------------------------------------------------------- entitlements

    async def get_entitlement(self, user_id: uuid.UUID) -> EntitlementRow | None:
        return await self._session.get(EntitlementRow, user_id)

    async def lock_entitlement(self, user_id: uuid.UUID, *, initial_deep_credits: int) -> EntitlementRow:
        """The user's entitlement row, created if missing, and locked (FOR UPDATE) until the transaction ends.

        The lock makes a user's concurrent "Generate" presses take turns, so two of them can't both spend the
        last free pack or the last Deep credit.
        """
        await self._session.execute(
            insert(EntitlementRow)
            .values(user_id=user_id, deep_credits=initial_deep_credits)
            .on_conflict_do_nothing(index_elements=[EntitlementRow.user_id])
        )
        return await self._session.scalar(
            select(EntitlementRow)
            .where(EntitlementRow.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)  # read the locked row fresh, not a copy cached earlier
        )

    # ----------------------------------------------------------------- usage ledger

    async def count_packs(self, user_id: uuid.UUID, paid_with: str, since: datetime) -> tuple[int, datetime | None]:
        """(packs paid this way since `since`, when the oldest of them started). Refunded packs don't count."""
        count, oldest = (await self._session.execute(
            select(func.count(), func.min(UsageRow.created_at)).where(
                UsageRow.user_id == user_id,
                UsageRow.paid_with == paid_with,
                UsageRow.refunded_at.is_(None),
                UsageRow.created_at >= since,
            )
        )).one()
        return count, oldest

    async def add_usage(self, user_id: uuid.UUID, mode: str, paid_with: str) -> UsageRow:
        usage = UsageRow(user_id=user_id, mode=mode, paid_with=paid_with)
        self._session.add(usage)
        await self._session.flush()
        return usage

    async def usage_for_run(self, run_id: uuid.UUID) -> UsageRow | None:
        return await self._session.scalar(
            select(UsageRow).where(UsageRow.run_id == run_id, UsageRow.refunded_at.is_(None))
        )

    async def add_deep_credits(self, user_id: uuid.UUID, count: int) -> None:
        """Atomic in SQL (no read-modify-write), so it's safe without the row lock."""
        await self._session.execute(
            update(EntitlementRow)
            .where(EntitlementRow.user_id == user_id)
            .values(deep_credits=EntitlementRow.deep_credits + count)
        )

    async def usage(self, user_id: uuid.UUID) -> list[UsageRow]:
        """The whole ledger for one user, oldest first (account export)."""
        return list(await self._session.scalars(
            select(UsageRow).where(UsageRow.user_id == user_id).order_by(UsageRow.created_at)
        ))
