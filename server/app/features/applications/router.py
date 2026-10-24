"""Application endpoints: start an application for a job, list mine, show one with its latest pack."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.features.applications.dependencies import ApplicationServiceDep
from app.features.applications.schemas import ApplicationDetailOut, ApplicationIn, ApplicationOut, ApplicationPage
from app.features.users.dependencies import CurrentUser

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post(
    "",
    response_model=ApplicationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Start an application for a job (201 when new, 200 when it already exists)",
)
async def start_application(user: CurrentUser, applications: ApplicationServiceDep, body: ApplicationIn,
                            response: Response) -> ApplicationOut:
    application, created = await applications.start(user, body.job_id)
    if not created:
        response.status_code = status.HTTP_200_OK
    return application


@router.get("", response_model=ApplicationPage, summary="My applications, newest first")
async def list_applications(
    user: CurrentUser,
    applications: ApplicationServiceDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    before: Annotated[datetime | None, Query(description="`next_before` from the previous page")] = None,
) -> ApplicationPage:
    return await applications.page(user, before=before, limit=limit)


@router.get("/{application_id}", response_model=ApplicationDetailOut, summary="One application with its latest pack")
async def read_application(user: CurrentUser, applications: ApplicationServiceDep,
                           application_id: uuid.UUID) -> ApplicationDetailOut:
    return await applications.detail(user, application_id)
