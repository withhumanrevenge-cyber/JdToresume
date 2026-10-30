"""Scan endpoints: check how my profile matches a job (free, no pack spent), and read my latest scan of it."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.features.scans.dependencies import ScanServiceDep
from app.features.scans.schemas import ScanIn, ScanOut
from app.features.users.dependencies import CurrentUser
from app.llm.dependencies import LLMDep

router = APIRouter(prefix="/scans", tags=["scans"])


@router.post(
    "",
    response_model=ScanOut,
    status_code=status.HTTP_201_CREATED,
    summary="Scan a job against my profile (free; 201 when new, 200 when the saved scan still applies)",
)
async def scan_job(user: CurrentUser, scans: ScanServiceDep, llm: LLMDep, body: ScanIn, response: Response) -> ScanOut:
    scan, created = await scans.scan(user, body.job_id, llm, datetime.now(UTC))
    if not created:
        response.status_code = status.HTTP_200_OK
    return scan


@router.get("", response_model=ScanOut, summary="My latest scan of a job")
async def latest_scan(user: CurrentUser, scans: ScanServiceDep,
                      job_id: Annotated[uuid.UUID, Query(description="The job that was scanned")]) -> ScanOut:
    return await scans.latest(user, job_id, datetime.now(UTC))
