"""Health checks.

- `GET /health`        liveness: the process is up. Load balancers use it to decide whether to restart a task.
- `GET /health/ready`  readiness: the API can serve real traffic (the database answers). Returns 503 if not,
                       so the load balancer stops sending requests here until it recovers.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.db import Database, get_database

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["ok", "unreachable"]


@router.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(status="ok", version=settings.app_version, environment=settings.environment)


@router.get("/health/ready", response_model=ReadinessResponse, responses={503: {"model": ReadinessResponse}})
async def ready(database: Annotated[Database, Depends(get_database)], response: Response) -> ReadinessResponse:
    if await database.is_reachable():
        return ReadinessResponse(status="ok", database="ok")
    response.status_code = 503
    return ReadinessResponse(status="unavailable", database="unreachable")
