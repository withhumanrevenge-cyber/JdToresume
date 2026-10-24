"""FastAPI dependencies for jobs: the service and the safe fetcher."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.core.db import DatabaseDep, SessionDep
from app.features.jobs.ingestion.fetch import SafeFetcher
from app.features.jobs.service import JobService


def get_job_service(session: SessionDep, database: DatabaseDep) -> JobService:
    return JobService(session, database)


def get_fetcher(request: Request) -> SafeFetcher:
    return request.app.state.fetcher  # one per app, created at startup (it caches robots.txt rules)


JobServiceDep = Annotated[JobService, Depends(get_job_service)]
FetcherDep = Annotated[SafeFetcher, Depends(get_fetcher)]
