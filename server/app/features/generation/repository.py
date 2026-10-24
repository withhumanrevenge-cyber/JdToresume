"""Database queries for generation runs and their artifacts. Only data access lives here."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.generation.models import ArtifactRow, GenerationRunRow


class GenerationRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def latest_run(self, application_id: uuid.UUID) -> GenerationRunRow | None:
        return await self._session.scalar(
            select(GenerationRunRow)
            .where(GenerationRunRow.application_id == application_id)
            .order_by(GenerationRunRow.started_at.desc())
            .limit(1)
        )

    async def latest_runs(self, application_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, GenerationRunRow]:
        """The newest run of each application, in one query (no query per application)."""
        if not application_ids:
            return {}
        rows = await self._session.scalars(
            select(GenerationRunRow)
            .where(GenerationRunRow.application_id.in_(application_ids))
            .ext(distinct_on(GenerationRunRow.application_id))  # PostgreSQL DISTINCT ON: first row per application
            .order_by(GenerationRunRow.application_id, GenerationRunRow.started_at.desc())
        )
        return {row.application_id: row for row in rows}

    async def add_run(self, application_id: uuid.UUID, profile_version: int, mode: str) -> GenerationRunRow:
        run = GenerationRunRow(application_id=application_id, profile_version=profile_version, mode=mode,
                               status="running")
        self._session.add(run)
        await self._session.flush()
        return run

    async def finish_run(self, run_id: uuid.UUID, *, status: str, error: str | None, cost_usd: float) -> None:
        await self._session.execute(
            update(GenerationRunRow)
            .where(GenerationRunRow.id == run_id)
            .values(status=status, error=error, cost_usd=cost_usd, finished_at=func.now())
        )

    async def artifacts(self, run_id: uuid.UUID) -> list[ArtifactRow]:
        return list(await self._session.scalars(select(ArtifactRow).where(ArtifactRow.run_id == run_id)))

    async def artifact(self, run_id: uuid.UUID, kind: str) -> ArtifactRow | None:
        return await self._session.scalar(select(ArtifactRow).where(ArtifactRow.run_id == run_id,
                                                                    ArtifactRow.kind == kind))

    async def latest_artifact(self, application_id: uuid.UUID, kind: str) -> tuple[GenerationRunRow, ArtifactRow] | None:
        """The newest saved piece of this kind, with the run that wrote it. A later run that failed before
        reaching this piece doesn't hide the one an earlier run finished."""
        row = (await self._session.execute(
            select(GenerationRunRow, ArtifactRow)
            .join(ArtifactRow, ArtifactRow.run_id == GenerationRunRow.id)
            .where(GenerationRunRow.application_id == application_id, ArtifactRow.kind == kind)
            .order_by(GenerationRunRow.started_at.desc())
            .limit(1)
        )).one_or_none()
        return (row[0], row[1]) if row else None

    async def add_artifact(self, run_id: uuid.UUID, kind: str, content: dict[str, Any]) -> None:
        self._session.add(ArtifactRow(run_id=run_id, kind=kind, content=content))
        await self._session.flush()
