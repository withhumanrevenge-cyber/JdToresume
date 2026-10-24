"""Business rules for user accounts."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.errors import ConflictError
from app.features.users.models import UserRow
from app.features.users.repository import UserRepository


class UserService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._users = UserRepository(session)

    async def get_or_create(self, principal: Principal) -> UserRow:
        """The user behind a valid sign-in token. Their row is created on their first request (no separate sign-up)."""
        user = await self._users.get_by_subject(principal.subject)
        if user is not None:
            return user
        try:
            user = await self._users.add(principal.subject, principal.email)
            await self._session.commit()
            return user
        except IntegrityError:
            await self._session.rollback()
            # Two "first" requests can arrive at once; if the other one created the row, use it.
            existing = await self._users.get_by_subject(principal.subject)
            if existing is not None:
                return existing
            # Otherwise the email belongs to a different sign-in identity.
            raise ConflictError("An account with this email address already exists") from None

    async def delete_account(self, user: UserRow) -> None:
        """Delete the user and, through ON DELETE CASCADE, everything stored about them (DPDP/GDPR erasure)."""
        await self._users.delete(user.id)
        await self._session.commit()
