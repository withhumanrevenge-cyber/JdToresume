"""Business rules for applications: start one for a job, list them, and show one with its latest results."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.features.applications.models import ApplicationRow
from app.features.applications.repository import ApplicationRepository
from app.features.applications.schemas import (
    ApplicationDetailOut, ApplicationOut, ApplicationPage, JobSummary, Pieces, RunOut,
)
from app.features.generation.models import ArtifactRow, GenerationRunRow
from app.features.generation.repository import GenerationRepository
from app.features.jobs.models import JobRow
from app.features.jobs.repository import JobRepository
from app.features.users.models import UserRow

logger = logging.getLogger(__name__)


class ApplicationService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._applications = ApplicationRepository(session)
        self._runs = GenerationRepository(session)
        self._jobs = JobRepository(session)

    async def start(self, user: UserRow, job_id: uuid.UUID) -> tuple[ApplicationOut, bool]:
        """The user's application for this job, created if needed. Returns (application, created)."""
        job = await self._jobs.get(job_id)
        if job is None or not job.is_visible_to(user.id):
            raise NotFoundError("Job not found")

        existing = await self._applications.find(user.id, job.id)
        if existing is not None:
            return _out(existing, job, await self._runs.latest_run(existing.id)), False
        try:
            application = await self._applications.add(user.id, job.id)
            await self._session.commit()
        except IntegrityError:
            # The same request arrived twice at once; the other one created it.
            await self._session.rollback()
            application = await self._applications.find(user.id, job.id)
            if application is None:
                raise
            return _out(application, job, await self._runs.latest_run(application.id)), False
        return _out(application, job, None), True

    async def page(self, user: UserRow, *, before: datetime | None, limit: int) -> ApplicationPage:
        rows = await self._applications.newest_first(user.id, before=before, limit=limit)
        latest = await self._runs.latest_runs([application.id for application, _ in rows])
        items = [_out(application, job, latest.get(application.id)) for application, job in rows]
        next_before = rows[-1][0].created_at if len(rows) == limit else None
        return ApplicationPage(items=items, next_before=next_before)

    async def detail(self, user: UserRow, application_id: uuid.UUID) -> ApplicationDetailOut:
        found = await self._applications.get_with_job(user.id, application_id)
        if found is None:
            raise NotFoundError("Application not found")
        application, job = found
        run = await self._runs.latest_run(application.id)
        pieces = _pieces(await self._runs.artifacts(run.id)) if run else Pieces()
        return ApplicationDetailOut(**_out(application, job, run).model_dump(), pieces=pieces)


def _pieces(artifacts: list[ArtifactRow]) -> Pieces:
    """Each saved piece checked on its own: one that no longer matches today's schema (saved by an older version)
    is left out and logged, instead of failing the whole page."""
    found = {}
    for artifact in artifacts:
        field = Pieces.model_fields.get(artifact.kind)
        if field is None:
            continue
        try:
            found[artifact.kind] = TypeAdapter(field.annotation).validate_python(artifact.content)
        except ValidationError:
            logger.warning("Artifact %s (%s) doesn't match the current schema; left out", artifact.id, artifact.kind)
    return Pieces(**found)


def _out(application: ApplicationRow, job: JobRow, run: GenerationRunRow | None) -> ApplicationOut:
    return ApplicationOut(
        id=application.id,
        status=application.status,
        created_at=application.created_at,
        job=JobSummary(id=job.id, title=job.title, company=job.company, url=job.canonical_url),
        latest_run=RunOut.model_validate(run) if run else None,
    )
