"""Account data export (DPDP / GDPR right of access): one JSON file with everything we store about the user.

`EXPORTED_TABLES` lists every table the export reads. A test compares it with the database schema, so a new table
can't be added without deciding whether its rows belong in the export.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.data_export.repository import ExportRepository
from app.features.data_export.schemas import (
    AccountExport, ExportedAccount, ExportedAiCall, ExportedApplication, ExportedJob, ExportedPlan,
    ExportedProfileVersion, ExportedRun, ExportedScan, ExportedUsage,
)
from app.features.users.models import UserRow

logger = logging.getLogger(__name__)

EXPORTED_TABLES = frozenset({
    "users", "contact_details", "career_profiles", "jobs", "applications", "generation_runs", "artifacts",
    "entitlements", "usage_ledger", "llm_calls", "scans",
})
NOT_PERSONAL_TABLES: frozenset[str] = frozenset()  # tables that hold nothing about a person (none yet)


class ExportService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def export(self, user: UserRow) -> AccountExport:
        data = ExportRepository(self._session, user.id)
        contact = await data.contact()
        entitlement = await data.entitlement()

        pieces: defaultdict[uuid.UUID, dict[str, Any]] = defaultdict(dict)  # run id -> kind -> content
        for artifact in await data.artifacts():
            pieces[artifact.run_id][artifact.kind] = artifact.content
        runs: defaultdict[uuid.UUID, list[ExportedRun]] = defaultdict(list)  # application id -> its runs
        for run in await data.runs():
            runs[run.application_id].append(ExportedRun(
                id=run.id, mode=run.mode, status=run.status, profile_version=run.profile_version,
                started_at=run.started_at, finished_at=run.finished_at, pieces=pieces[run.id],
            ))

        logger.info("Account export for user %s", user.id)  # a real audit log arrives with ARCHITECTURE §12
        return AccountExport(
            exported_at=datetime.now(UTC),
            account=ExportedAccount(id=user.id, email=user.email, created_at=user.created_at),
            contact_details=contact.to_contact() if contact else None,
            profile_versions=[ExportedProfileVersion(version=p.version, created_at=p.created_at, profile=p.data)
                              for p in await data.profile_versions()],
            jobs=[ExportedJob(
                id=job.id, title=job.title, company=job.company, url=job.canonical_url,
                added_by_you=job.owner_user_id == user.id, created_at=job.created_at, spec=job.spec,
                text=job.raw_text if job.owner_user_id == user.id else None,
            ) for job in await data.jobs()],
            applications=[ExportedApplication(id=a.id, job_id=a.job_id, status=a.status, created_at=a.created_at,
                                              runs=runs[a.id]) for a in await data.applications()],
            plan=ExportedPlan(plan=entitlement.plan, plan_expires_at=entitlement.plan_expires_at,
                              deep_credits=entitlement.deep_credits) if entitlement else None,
            usage=[ExportedUsage(created_at=u.created_at, mode=u.mode, paid_with=u.paid_with, run_id=u.run_id,
                                 refunded_at=u.refunded_at) for u in await data.usage()],
            scans=[ExportedScan(created_at=s.created_at, job_id=s.job_id, profile_version=s.profile_version,
                                result=s.result) for s in await data.scans()],
            ai_calls=[ExportedAiCall(created_at=c.created_at, purpose=c.purpose, step=c.step, model=c.model)
                      for c in await data.ai_calls()],
        )
