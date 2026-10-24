"""Database queries for career profiles and contact details. Only data access lives here; rules are in service.py."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.profiles.models import CareerProfileRow, ContactDetailsRow
from app.llm.schemas import CareerProfile, ContactDetails


class ProfileRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    # ----------------------------------------------------------------- career profile (append-only versions)

    async def latest_profile(self, user_id: uuid.UUID) -> CareerProfileRow | None:
        return await self._session.scalar(
            select(CareerProfileRow)
            .where(CareerProfileRow.user_id == user_id)
            .order_by(CareerProfileRow.version.desc())
            .limit(1)
        )

    async def profile_version(self, user_id: uuid.UUID, version: int) -> CareerProfileRow | None:
        """A specific version: a generated pack is always rendered against the profile it was written from."""
        return await self._session.scalar(
            select(CareerProfileRow).where(CareerProfileRow.user_id == user_id, CareerProfileRow.version == version)
        )

    async def add_profile_version(self, user_id: uuid.UUID, version: int, profile: CareerProfile) -> CareerProfileRow:
        row = CareerProfileRow(user_id=user_id, version=version, data=profile.model_dump(mode="json"))
        self._session.add(row)
        await self._session.flush()  # a clash with a concurrent save surfaces here, as an IntegrityError
        return row

    # ----------------------------------------------------------------- contact details (one row per user)

    async def get_contact(self, user_id: uuid.UUID) -> ContactDetailsRow | None:
        return await self._session.get(ContactDetailsRow, user_id)

    async def save_contact(self, user_id: uuid.UUID, contact: ContactDetails) -> ContactDetailsRow:
        """Insert or overwrite the user's contact details."""
        row = await self.get_contact(user_id) or ContactDetailsRow(user_id=user_id)
        row.full_name = contact.full_name
        row.email = contact.email
        row.phone = contact.phone
        row.city = contact.city
        row.links = list(contact.links)
        self._session.add(row)
        await self._session.flush()
        return row
