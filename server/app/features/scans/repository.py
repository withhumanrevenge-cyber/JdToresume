"""Database queries for match scans. Only data access lives here; the rules are in service.py."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.scans.models import ScanRow


class ScanRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def latest(self, user_id: uuid.UUID, job_id: uuid.UUID, profile_version: int | None = None) -> ScanRow | None:
        """My newest scan of this job (of one profile version, when given)."""
        query = select(ScanRow).where(ScanRow.user_id == user_id, ScanRow.job_id == job_id)
        if profile_version is not None:
            query = query.where(ScanRow.profile_version == profile_version)
        return await self._session.scalar(query.order_by(ScanRow.created_at.desc()).limit(1))

    async def count_since(self, user_id: uuid.UUID, since: datetime) -> int:
        return await self._session.scalar(
            select(func.count()).select_from(ScanRow).where(ScanRow.user_id == user_id, ScanRow.created_at >= since)
        ) or 0

    async def add(self, user_id: uuid.UUID, job_id: uuid.UUID, profile_version: int, mode: str,
                  result: dict[str, Any]) -> ScanRow:
        row = ScanRow(user_id=user_id, job_id=job_id, profile_version=profile_version, mode=mode, result=result)
        self._session.add(row)
        await self._session.flush()
        return row
