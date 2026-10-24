"""Job endpoints: add a job (pasted text or a link) and read it back."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, status

from app.features.jobs.dependencies import FetcherDep, JobServiceDep
from app.features.jobs.schemas import JobIn, JobOut
from app.features.users.dependencies import CurrentUser
from app.llm.dependencies import LLMDep

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "",
    response_model=JobOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a job from pasted text or a link (201 when new, 200 when it was already known)",
)
async def add_job(user: CurrentUser, jobs: JobServiceDep, llm: LLMDep, fetcher: FetcherDep, body: JobIn,
                  response: Response) -> JobOut:
    if body.url:
        job = await jobs.add_from_url(user, body.url, llm, fetcher)
    else:
        job = await jobs.add_from_text(user, body.text or "", llm)
    if job.reused:
        response.status_code = status.HTTP_200_OK
    return job


@router.get("/{job_id}", response_model=JobOut, summary="A job I added, or any job read from a public link")
async def read_job(user: CurrentUser, jobs: JobServiceDep, job_id: uuid.UUID) -> JobOut:
    return await jobs.get(user, job_id)
