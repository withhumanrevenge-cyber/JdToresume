"""FastAPI dependency for the application service."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.core.db import SessionDep
from app.features.applications.service import ApplicationService


def get_application_service(session: SessionDep) -> ApplicationService:
    return ApplicationService(session)


ApplicationServiceDep = Annotated[ApplicationService, Depends(get_application_service)]
