"""Database queries for users. Only data access lives here; the rules are in service.py."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import UserRow


class UserRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_subject(self, subject: str) -> UserRow | None:
        return await self._session.scalar(select(UserRow).where(UserRow.auth_subject == subject))

    async def add(self, subject: str, email: str) -> UserRow:
        user = UserRow(auth_subject=subject, email=email)
        self._session.add(user)
        await self._session.flush()  # sends the INSERT now, so constraint violations surface here
        return user

    async def delete(self, user_id: uuid.UUID) -> None:
        await self._session.execute(delete(UserRow).where(UserRow.id == user_id))
