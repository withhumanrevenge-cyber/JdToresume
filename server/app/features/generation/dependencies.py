"""FastAPI dependency for the generation service."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.core.db import DatabaseDep, SessionDep
from app.features.generation.service import GenerationService


def get_generation_service(session: SessionDep, database: DatabaseDep) -> GenerationService:
    return GenerationService(session, database)


GenerationServiceDep = Annotated[GenerationService, Depends(get_generation_service)]
