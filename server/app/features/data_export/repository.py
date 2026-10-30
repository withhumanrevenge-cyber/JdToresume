"""Read-only queries for "everything we store about one user". The only module that reads across every feature's
tables, so the account export can't miss one (tests/test_account.py checks the list against the schema)."""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.applications.models import ApplicationRow
from app.features.billing.models import EntitlementRow, UsageRow
from app.features.generation.models import ArtifactRow, GenerationRunRow
from app.features.jobs.models import JobRow
from app.features.profiles.models import CareerProfileRow, ContactDetailsRow
from app.features.scans.models import ScanRow
from app.llm.ledger import LlmCallRow


class ExportRepository:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID):
        self._session = session
        self._user_id = user_id

    async def contact(self) -> ContactDetailsRow | None:
        return await self._session.get(ContactDetailsRow, self._user_id)

    async def profile_versions(self) -> list[CareerProfileRow]:
        return list(await self._session.scalars(
            select(CareerProfileRow).where(CareerProfileRow.user_id == self._user_id).order_by(CareerProfileRow.version)
        ))

    async def applications(self) -> list[ApplicationRow]:
        return list(await self._session.scalars(
            select(ApplicationRow).where(ApplicationRow.user_id == self._user_id).order_by(ApplicationRow.created_at)
        ))

    async def jobs(self) -> list[JobRow]:
        """Jobs the user added privately, plus shared ones their applications point at."""
        applied = select(ApplicationRow.job_id).where(ApplicationRow.user_id == self._user_id)
        return list(await self._session.scalars(
            select(JobRow).where(or_(JobRow.owner_user_id == self._user_id, JobRow.id.in_(applied)))
            .order_by(JobRow.created_at)
        ))

    async def runs(self) -> list[GenerationRunRow]:
        return list(await self._session.scalars(
            select(GenerationRunRow)
            .join(ApplicationRow, ApplicationRow.id == GenerationRunRow.application_id)
            .where(ApplicationRow.user_id == self._user_id)
            .order_by(GenerationRunRow.started_at)
        ))

    async def artifacts(self) -> list[ArtifactRow]:
        return list(await self._session.scalars(
            select(ArtifactRow)
            .join(GenerationRunRow, GenerationRunRow.id == ArtifactRow.run_id)
            .join(ApplicationRow, ApplicationRow.id == GenerationRunRow.application_id)
            .where(ApplicationRow.user_id == self._user_id)
            .order_by(ArtifactRow.created_at)
        ))

    async def entitlement(self) -> EntitlementRow | None:
        return await self._session.get(EntitlementRow, self._user_id)

    async def usage(self) -> list[UsageRow]:
        return list(await self._session.scalars(
            select(UsageRow).where(UsageRow.user_id == self._user_id).order_by(UsageRow.created_at)
        ))

    async def ai_calls(self) -> list[LlmCallRow]:
        return list(await self._session.scalars(
            select(LlmCallRow).where(LlmCallRow.user_id == self._user_id).order_by(LlmCallRow.created_at)
        ))

    async def scans(self) -> list[ScanRow]:
        return list(await self._session.scalars(
            select(ScanRow).where(ScanRow.user_id == self._user_id).order_by(ScanRow.created_at)
        ))
