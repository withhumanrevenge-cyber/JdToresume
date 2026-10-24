"""FastAPI dependency for the account export service."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.core.db import SessionDep
from app.features.data_export.service import ExportService


def get_export_service(session: SessionDep) -> ExportService:
    return ExportService(session)


ExportServiceDep = Annotated[ExportService, Depends(get_export_service)]
