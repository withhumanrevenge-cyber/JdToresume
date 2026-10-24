"""Business rules for career profiles and contact details."""

from __future__ import annotations

import asyncio
import logging
from pathlib import PurePath

from groq import APIError as GroqAPIError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Database, release_connection
from app.core.errors import ConflictError, InvalidInputError, NotFoundError, PayloadTooLargeError, UpstreamError
from app.features.profiles.consistency import find_problems
from app.features.profiles.models import CareerProfileRow
from app.features.profiles.parse import UnsupportedResumeError, extract_text_from_bytes, parse_resume_text
from app.features.profiles.repository import ProfileRepository
from app.features.profiles.schemas import ContactIn, ContactOut, ProfileOut, ResumeImportOut
from app.features.users.models import UserRow
from app.llm.client import BudgetExceeded, GroqLLM, StepError
from app.llm.ledger import record_llm_calls
from app.llm.schemas import CareerProfile, ContactDetails

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_RESUME_CHARS = 40_000  # roughly 10 pages; keeps a single parse call small and cheap


class ProfileService:
    def __init__(self, session: AsyncSession, database: Database):
        self._session = session
        self._db = database  # for the cost ledger, which writes in its own session
        self._repo = ProfileRepository(session)

    # ----------------------------------------------------------------- resume upload

    async def import_resume(self, user: UserRow, filename: str, data: bytes, llm: GroqLLM) -> ResumeImportOut:
        """Turn an uploaded resume into a new profile version (and first-time contact details)."""
        text = await self._read_resume(filename, data)

        await release_connection(self._session)  # no DB connection is held during the slow LLM call
        try:
            profile, detected = await self._parse(llm, text)
        finally:
            await record_llm_calls(self._db, llm.calls, user_id=user.id, purpose="resume_parse")

        contact = await self._repo.get_contact(user.id)
        if contact is None and detected.full_name and detected.email:
            # First upload: keep what we found. Later uploads never overwrite contact details the user confirmed.
            contact = await self._repo.save_contact(user.id, detected)
        row = await self._add_version(user, profile)
        await self._commit()

        facts = profile.all_facts().values()
        logger.info("Resume imported: profile v%d, %d facts, $%.4f", row.version, len(facts), llm.spent_usd)
        return ResumeImportOut(
            profile=_profile_out(row),
            contact=ContactOut.model_validate(contact) if contact else None,
            detected_contact=detected,
            facts_without_numbers=sum(1 for fact in facts if not fact.metrics),
        )

    async def _read_resume(self, filename: str, data: bytes) -> str:
        if len(data) > MAX_UPLOAD_BYTES:
            raise PayloadTooLargeError(f"The file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
        try:
            # PDF text extraction is CPU work, so it runs in a thread instead of blocking other requests.
            text = await asyncio.to_thread(extract_text_from_bytes, data, PurePath(filename).suffix)
        except UnsupportedResumeError as exc:
            raise InvalidInputError(str(exc)) from exc
        text = text.strip()
        if not text:
            raise InvalidInputError(
                "We couldn't find any text in this file. Scanned PDFs aren't supported yet: "
                "upload a text-based PDF or a .txt file."
            )
        if len(text) > MAX_RESUME_CHARS:
            raise InvalidInputError("This resume is too long to import (about 10 pages is the limit)")
        return text

    async def _parse(self, llm: GroqLLM, text: str) -> tuple[CareerProfile, ContactDetails]:
        try:
            profile, detected = await parse_resume_text(llm, text)
        except (StepError, BudgetExceeded, GroqAPIError) as exc:
            logger.warning("Resume parse failed: %s", exc)
            raise UpstreamError("The AI service couldn't read this resume right now. Please try again.") from exc
        problems = find_problems(profile)
        if problems:
            logger.warning("Resume parse produced an inconsistent profile: %s", problems)
            raise UpstreamError("The AI service returned an unusable result for this resume. Please try again.")
        return profile, detected

    # ----------------------------------------------------------------- profile

    async def get_profile(self, user: UserRow) -> ProfileOut:
        row = await self._repo.latest_profile(user.id)
        if row is None:
            raise NotFoundError("No profile yet: upload a resume first")
        return _profile_out(row)

    async def save_profile(self, user: UserRow, base_version: int, profile: CareerProfile) -> ProfileOut:
        """Save an edited profile as a new version, refusing to overwrite a newer one."""
        problems = find_problems(profile)
        if problems:
            raise InvalidInputError("The profile has problems to fix", details={"problems": problems})
        latest = await self._repo.latest_profile(user.id)
        current = latest.version if latest else 0
        if base_version != current:
            raise ConflictError(
                f"Your profile changed since you loaded it (it is now version {current}). Reload and try again.",
                details={"current_version": current},
            )
        row = await self._add_version(user, profile)
        await self._commit()
        return _profile_out(row)

    async def _add_version(self, user: UserRow, profile: CareerProfile) -> CareerProfileRow:
        latest = await self._repo.latest_profile(user.id)
        return await self._repo.add_profile_version(user.id, (latest.version if latest else 0) + 1, profile)

    # ----------------------------------------------------------------- contact details

    async def get_contact(self, user: UserRow) -> ContactOut:
        row = await self._repo.get_contact(user.id)
        if row is None:
            raise NotFoundError("No contact details yet")
        return ContactOut.model_validate(row)

    async def save_contact(self, user: UserRow, contact: ContactIn) -> ContactOut:
        row = await self._repo.save_contact(user.id, ContactDetails(**contact.model_dump()))
        await self._commit()
        return ContactOut.model_validate(row)

    # ----------------------------------------------------------------- helpers

    async def _commit(self) -> None:
        try:
            await self._session.commit()
        except IntegrityError as exc:
            # Two saves raced for the same version number; the other one won.
            await self._session.rollback()
            raise ConflictError("Your profile was changed at the same time elsewhere. Reload and try again.") from exc


def _profile_out(row: CareerProfileRow) -> ProfileOut:
    return ProfileOut(version=row.version, created_at=row.created_at, profile=CareerProfile.model_validate(row.data))
