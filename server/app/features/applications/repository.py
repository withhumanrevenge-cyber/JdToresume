"""Database queries for applications. Only data access lives here; rules are in service.py."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.applications.models import ApplicationRow
from app.features.jobs.models import JobRow


class ApplicationRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_with_job(self, user_id: uuid.UUID, application_id: uuid.UUID) -> tuple[ApplicationRow, JobRow] | None:
        """The user's application and its job. Someone else's application is simply not found."""
        row = (await self._session.execute(
            select(ApplicationRow, JobRow)
            .join(JobRow, JobRow.id == ApplicationRow.job_id)
            .where(ApplicationRow.id == application_id, ApplicationRow.user_id == user_id)
        )).one_or_none()
        return (row[0], row[1]) if row else None

    async def find(self, user_id: uuid.UUID, job_id: uuid.UUID) -> ApplicationRow | None:
        return await self._session.scalar(
            select(ApplicationRow).where(ApplicationRow.user_id == user_id, ApplicationRow.job_id == job_id)
        )

    async def add(self, user_id: uuid.UUID, job_id: uuid.UUID) -> ApplicationRow:
        application = ApplicationRow(user_id=user_id, job_id=job_id)
        self._session.add(application)
        await self._session.flush()
        return application

    async def newest_first(
        self, user_id: uuid.UUID, *, before: datetime | None, limit: int
    ) -> list[tuple[ApplicationRow, JobRow]]:
        """One page of the user's applications, newest first. `before` is the previous page's last `created_at`."""
        query = (
            select(ApplicationRow, JobRow)
            .join(JobRow, JobRow.id == ApplicationRow.job_id)
            .where(ApplicationRow.user_id == user_id)
            .order_by(ApplicationRow.created_at.desc(), ApplicationRow.id.desc())
            .limit(limit)
        )
        if before is not None:
            query = query.where(ApplicationRow.created_at < before)
        return [(application, job) for application, job in (await self._session.execute(query)).all()]
