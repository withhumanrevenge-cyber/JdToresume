"""FastAPI dependency for the profile service."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.core.db import DatabaseDep, SessionDep
from app.features.profiles.service import ProfileService


def get_profile_service(session: SessionDep, database: DatabaseDep) -> ProfileService:
    return ProfileService(session, database)


ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]
