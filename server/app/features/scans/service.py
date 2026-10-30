"""The free match scan (PRD §4): the user's current profile against one job, before they spend a pack.

It runs the same match step the pipeline starts with (Quick model: fast and cheap), then measures how many of the
job's keywords and must-have evidence terms already appear in the profile, with the same matcher as the ATS check.
Nothing is generated and no pack is spent.

- Scanning the same job again with the same profile version returns the saved result: no AI call, and it doesn't
  count towards the daily limit.
- Fair use: at most SCANS_PER_DAY scans that call the AI per UTC day (billing/plans.py).
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import UTC, datetime, timedelta

from groq import APIError as GroqAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Database, release_connection
from app.core.errors import NotFoundError, TooManyRequestsError, UpstreamError
from app.features.billing.plans import SCANS_PER_DAY
from app.features.generation.service import ProfileRequiredError
from app.features.jobs.models import JobRow
from app.features.jobs.repository import JobRepository
from app.features.profiles.repository import ProfileRepository
from app.features.rendering.ats_roundtrip import keyword_coverage, must_have_coverage
from app.features.scans.models import ScanRow
from app.features.scans.repository import ScanRepository
from app.features.scans.schemas import ScanOut, ScanResult
from app.features.users.models import UserRow
from app.llm.client import BudgetExceeded, GroqLLM, StepError
from app.llm.ledger import record_llm_calls
from app.llm.pii import redact_profile
from app.llm.router import Mode, step_config
from app.llm.schemas import CareerProfile, ContactDetails, JobSpec, MatchReport

logger = logging.getLogger(__name__)

SCAN_MODE: Mode = "quick"
_NO_CONTACT = ContactDetails(full_name="", email="", phone=None, city=None, links=[])


class ScanLimitError(TooManyRequestsError):
    code = "scan_limit"


class NotScannedError(NotFoundError):
    code = "not_scanned"


class ScanService:
    def __init__(self, session: AsyncSession, database: Database):
        self._session = session
        self._db = database
        self._scans = ScanRepository(session)
        self._profiles = ProfileRepository(session)

    async def scan(self, user: UserRow, job_id: uuid.UUID, llm: GroqLLM, now: datetime) -> tuple[ScanOut, bool]:
        """Scan the job against the current profile. Returns (scan, created); created is False for a saved repeat."""
        job = await self._job(user, job_id)
        profile_row = await self._profiles.latest_profile(user.id)
        if profile_row is None:
            raise ProfileRequiredError("Upload your resume first: the scan compares it with the job")

        today = _day_start(now)
        used = await self._scans.count_since(user.id, today)
        saved = await self._scans.latest(user.id, job.id, profile_row.version)
        if saved is not None:
            return _out(saved, profile_row.version, used), False
        if used >= SCANS_PER_DAY:
            tomorrow = today + timedelta(days=1)
            raise ScanLimitError(
                f"You've used today's {SCANS_PER_DAY} free scans. They come back at midnight UTC",
                details={"retry_at": tomorrow.isoformat()},
                headers={"Retry-After": str(max(math.ceil((tomorrow - now).total_seconds()), 1))},
            )

        contact_row = await self._profiles.get_contact(user.id)
        contact = contact_row.to_contact() if contact_row else _NO_CONTACT  # only used to keep it out of the AI
        profile = CareerProfile.model_validate(profile_row.data)
        spec = JobSpec.model_validate(job.spec)
        await release_connection(self._session)  # no database connection is held during the AI call

        report = await self._match(user, llm, profile, contact, spec)
        result = scan_result(report, profile, spec)
        row = await self._scans.add(user.id, job.id, profile_row.version, SCAN_MODE, result.model_dump(mode="json"))
        await self._session.commit()
        return _out(row, profile_row.version, used + 1), True

    async def latest(self, user: UserRow, job_id: uuid.UUID, now: datetime) -> ScanOut:
        """My newest scan of this job, marked stale when the profile has changed since."""
        job = await self._job(user, job_id)
        row = await self._scans.latest(user.id, job.id)
        if row is None:
            raise NotScannedError("This job hasn't been scanned yet")
        profile_row = await self._profiles.latest_profile(user.id)
        current = profile_row.version if profile_row else row.profile_version
        return _out(row, current, await self._scans.count_since(user.id, _day_start(now)))

    async def _job(self, user: UserRow, job_id: uuid.UUID) -> JobRow:
        job = await JobRepository(self._session).get(job_id)
        if job is None or not job.is_visible_to(user.id):
            raise NotFoundError("Job not found")
        return job

    async def _match(self, user: UserRow, llm: GroqLLM, profile: CareerProfile, contact: ContactDetails,
                     spec: JobSpec) -> MatchReport:
        try:
            return await llm.run_step(
                "match_plan", output=MatchReport, cfg=step_config("match_plan", SCAN_MODE),
                prefix_blocks=[("career_profile", redact_profile(profile, contact))],
                blocks=[("job_spec", spec)], contact=contact,
            )
        except (StepError, BudgetExceeded, GroqAPIError) as exc:
            logger.warning("Match scan failed: %s", exc)
            raise UpstreamError("The AI service couldn't scan this job right now. Please try again.") from exc
        finally:
            await record_llm_calls(self._db, llm.calls, user_id=user.id, purpose="scan")


def profile_text(profile: CareerProfile) -> str:
    """Everything a resume could truthfully say, as one text: titles, companies, facts and their skills, skills,
    education. Company names count ("logistics" in "Brightline Logistics" is evidence of the domain)."""
    parts = [profile.headline, *profile.languages]
    parts += [f"{role.title} {role.company}" for role in profile.experience]
    parts += [project.name for project in profile.projects]
    parts += [f"{school.degree} {school.field or ''}" for school in profile.education]
    parts += [cert.name for cert in profile.certifications]
    parts += [skill.name for skill in profile.skills]
    for fact in profile.all_facts().values():
        parts += [fact.text, *fact.skills]
    return " ".join(part for part in parts if part)


def scan_result(report: MatchReport, profile: CareerProfile, spec: JobSpec) -> ScanResult:
    text = profile_text(profile)
    coverage, missing = keyword_coverage(text, spec)
    return ScanResult(
        match_report=report,
        keyword_coverage=coverage,
        keywords_found=[k.term for k in spec.keywords if k.term not in missing],
        keywords_missing=missing,
        must_have_coverage=must_have_coverage(text, spec),
    )


def _day_start(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def _out(row: ScanRow, current_profile_version: int, used_today: int) -> ScanOut:
    return ScanOut(
        **row.result,
        id=row.id,
        job_id=row.job_id,
        profile_version=row.profile_version,
        created_at=row.created_at,
        stale=row.profile_version != current_profile_version,
        scans_left_today=max(SCANS_PER_DAY - used_today, 0),
    )
