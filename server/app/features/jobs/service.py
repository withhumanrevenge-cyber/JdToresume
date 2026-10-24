"""Business rules for job postings: add one from pasted text or a link, and read one back."""

from __future__ import annotations

import hashlib
import logging
import uuid
from urllib.parse import urlsplit

from groq import APIError as GroqAPIError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Database, release_connection
from app.core.errors import InvalidInputError, NotFoundError, UpstreamError
from app.features.jobs.ingestion.fetch import FetchError, SafeFetcher
from app.features.jobs.ingestion.raw import RawJob
from app.features.jobs.ingestion.reader import read_job_from_url
from app.features.jobs.models import JobRow
from app.features.jobs.policy import client_only_site
from app.features.jobs.repository import JobRepository
from app.features.jobs.schemas import JobOut
from app.features.jobs.urls import InvalidJobUrl, canonicalize, url_hash
from app.features.users.models import UserRow
from app.llm.client import BudgetExceeded, GroqLLM, StepError
from app.llm.ledger import record_llm_calls
from app.llm.router import step_config
from app.llm.schemas import JobSpec

logger = logging.getLogger(__name__)

MIN_TEXT_CHARS = 150  # anything shorter isn't a job description we can tailor to


class ClientOnlySourceError(InvalidInputError):
    code = "client_only_source"


class JobNotReadableError(InvalidInputError):
    code = "job_not_readable"


class JobService:
    def __init__(self, session: AsyncSession, database: Database):
        self._session = session
        self._db = database  # for the cost ledger, which writes in its own session
        self._repo = JobRepository(session)

    async def add_from_text(self, user: UserRow, text: str, llm: GroqLLM) -> JobOut:
        """A private job from pasted text. Pasting the same text again reuses it (no second AI call)."""
        text = text.strip()
        if len(text) < MIN_TEXT_CHARS:
            raise InvalidInputError("That's too short to be a job description. Paste the full posting.")
        content_hash = _content_hash(text)
        existing = await self._repo.find_private(user.id, content_hash)
        if existing is not None:
            return _job_out(existing, reused=True)

        await release_connection(self._session)  # no DB connection is held during the AI call
        raw = RawJob(text=text, source="text")
        spec = await self._extract(user, llm, raw.text)
        row = await self._repo.add(owner_id=user.id, raw=raw, content_hash=content_hash, spec=spec)
        await self._session.commit()
        return _job_out(row, reused=False)

    async def add_from_url(self, user: UserRow, url: str, llm: GroqLLM, fetcher: SafeFetcher) -> JobOut:
        """A shared job from a public link. A link anyone already added is reused for everyone."""
        try:
            canonical = canonicalize(url)
        except InvalidJobUrl as exc:
            raise InvalidInputError(str(exc)) from exc
        site = client_only_site(urlsplit(canonical).hostname or "")
        if site is not None:  # checked before any network call, every time
            raise ClientOnlySourceError(
                f"We don't read {site} pages from our servers. Open the job, copy its description and paste the text "
                "instead. (The browser extension will do this for you in one click.)",
                details={"site": site},
            )

        key = url_hash(canonical)
        existing = await self._repo.find_shared(key)
        if existing is not None:
            return _job_out(existing, reused=True)

        await release_connection(self._session)
        try:
            raw = await read_job_from_url(fetcher, canonical)
        except FetchError as exc:
            raise JobNotReadableError(str(exc)) from exc
        spec = await self._extract(user, llm, raw.text)

        try:
            row = await self._repo.add(owner_id=None, raw=raw, content_hash=_content_hash(raw.text), spec=spec,
                                       canonical_url=canonical, url_hash=key)
            await self._session.commit()
        except IntegrityError:
            # Someone added the same link while we were reading it; theirs is just as good.
            await self._session.rollback()
            winner = await self._repo.find_shared(key)
            if winner is None:
                raise
            return _job_out(winner, reused=True)
        logger.info("Job added from %s (%s): %s", raw.source, raw.ats_vendor or "web page", spec.title)
        return _job_out(row, reused=False)

    async def get(self, user: UserRow, job_id: uuid.UUID) -> JobOut:
        row = await self._repo.get(job_id)
        # Someone else's private job looks exactly like a missing one: no hint that it exists.
        if row is None or not row.is_visible_to(user.id):
            raise NotFoundError("Job not found")
        return _job_out(row, reused=True)

    async def _extract(self, user: UserRow, llm: GroqLLM, text: str) -> JobSpec:
        try:
            spec = await llm.run_step("jd_extract", output=JobSpec, cfg=step_config("jd_extract"),
                                      blocks=[("job_description", text)])
        except (StepError, BudgetExceeded, GroqAPIError) as exc:
            logger.warning("Job extraction failed: %s", exc)
            raise UpstreamError("The AI service couldn't read this job right now. Please try again.") from exc
        finally:
            await record_llm_calls(self._db, llm.calls, user_id=user.id, purpose="job_extract")
        if not spec.title.strip():
            raise UpstreamError("The AI service couldn't find a job title in this posting. Please try again.")
        return spec


def _content_hash(text: str) -> str:
    """Same posting, same hash, whatever the spacing or capitalisation."""
    return hashlib.sha256(" ".join(text.lower().split()).encode("utf-8")).hexdigest()


def _job_out(row: JobRow, *, reused: bool) -> JobOut:
    return JobOut(id=row.id, source=row.source, ats_vendor=row.ats_vendor, url=row.canonical_url, title=row.title,
                  company=row.company, created_at=row.created_at, spec=JobSpec.model_validate(row.spec), reused=reused)
