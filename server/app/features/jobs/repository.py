"""Database queries for job postings. Only data access lives here; rules are in service.py."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.jobs.ingestion.raw import RawJob
from app.features.jobs.models import JobRow
from app.llm.schemas import JobSpec


class JobRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, job_id: uuid.UUID) -> JobRow | None:
        return await self._session.get(JobRow, job_id)

    async def find_shared(self, url_hash: str) -> JobRow | None:
        return await self._session.scalar(
            select(JobRow).where(JobRow.url_hash == url_hash, JobRow.owner_user_id.is_(None))
        )

    async def find_private(self, owner_id: uuid.UUID, content_hash: str) -> JobRow | None:
        return await self._session.scalar(
            select(JobRow)
            .where(JobRow.owner_user_id == owner_id, JobRow.content_hash == content_hash)
            .order_by(JobRow.created_at.desc())
            .limit(1)
        )

    async def add(
        self,
        *,
        owner_id: uuid.UUID | None,
        raw: RawJob,
        content_hash: str,
        spec: JobSpec,
        canonical_url: str | None = None,
        url_hash: str | None = None,
    ) -> JobRow:
        row = JobRow(
            owner_user_id=owner_id,
            source=raw.source,
            ats_vendor=raw.ats_vendor,
            canonical_url=canonical_url,
            url_hash=url_hash,
            content_hash=content_hash,
            title=spec.title[:300],
            company=spec.company[:300] if spec.company else None,
            raw_text=raw.text,
            spec=spec.model_dump(mode="json"),
        )
        self._session.add(row)
        await self._session.flush()  # a race with another user adding the same link surfaces here
        return row
