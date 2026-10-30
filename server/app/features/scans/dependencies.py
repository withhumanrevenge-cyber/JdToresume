"""FastAPI dependency for the scan service."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.core.db import DatabaseDep, SessionDep
from app.features.scans.service import ScanService


def get_scan_service(session: SessionDep, database: DatabaseDep) -> ScanService:
    return ScanService(session, database)


ScanServiceDep = Annotated[ScanService, Depends(get_scan_service)]
