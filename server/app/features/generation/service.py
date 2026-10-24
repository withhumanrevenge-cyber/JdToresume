"""Generating an application pack for one application, streamed piece by piece.

Two phases:
1. `prepare` (inside the request): checks everything, spends one pack from the user's plan and creates the run.
   Problems here are ordinary JSON errors (402, 404, 409, 422, 429).
2. `stream` (after the response has started): runs the pipeline, saves each piece the moment it's ready, then
   sends it as an event. It uses its own short database sessions, never the request's, and it always closes the
   run and records every AI call, even when a step fails or the browser disconnects. A run that ends without
   the resume gives its pack back.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import anyio
from groq import APIError as GroqAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Database
from app.core.errors import ConflictError, InvalidInputError, NotFoundError
from app.core.sse import sse_event
from app.features.applications.repository import ApplicationRepository
from app.features.billing.service import BillingService
from app.features.generation.pipeline import Piece, stream_pack
from app.features.generation.repository import GenerationRepository
from app.features.profiles.repository import ProfileRepository
from app.features.users.models import UserRow
from app.llm.client import BudgetExceeded, GroqLLM, StepError
from app.llm.ledger import record_llm_calls
from app.llm.router import Mode
from app.llm.schemas import CareerProfile, ContactDetails, JobSpec

logger = logging.getLogger(__name__)

# A run still "running" after this long crashed without closing; don't let it block a new one.
STALE_RUN_AFTER = timedelta(minutes=10)
# The piece a pack is paid for. A run that ends without it (the AI failed, the browser left) gives its pack back,
# even if the match report, cover letter or outreach finished: those are kept, but they aren't the product.
PAID_PIECE = "resume"
_NO_CONTACT = ContactDetails(full_name="", email="", phone=None, city=None, links=[])


class ProfileRequiredError(InvalidInputError):
    code = "profile_required"


@dataclass(frozen=True)
class PreparedRun:
    run_id: uuid.UUID
    user_id: uuid.UUID
    mode: Mode
    job: JobSpec
    profile: CareerProfile
    profile_version: int
    contact: ContactDetails


class GenerationService:
    def __init__(self, session: AsyncSession, database: Database):
        self._session = session
        self._db = database

    # ----------------------------------------------------------------- phase 1: inside the request

    async def prepare(self, user: UserRow, application_id: uuid.UUID, mode: Mode | None) -> PreparedRun:
        """`mode=None` lets the user's plan choose (Deep when they have it, otherwise Quick)."""
        found = await ApplicationRepository(self._session).get_with_job(user.id, application_id)
        if found is None:
            raise NotFoundError("Application not found")
        application, job = found

        profiles = ProfileRepository(self._session)
        profile_row = await profiles.latest_profile(user.id)
        if profile_row is None:
            raise ProfileRequiredError("Upload your resume first: the pack is written from your profile")

        runs = GenerationRepository(self._session)
        latest = await runs.latest_run(application.id)
        if latest is not None and latest.status == "running" and datetime.now(UTC) - latest.started_at < STALE_RUN_AFTER:
            raise ConflictError("A pack is already being generated for this application", details={"run_id": str(latest.id)})

        contact_row = await profiles.get_contact(user.id)
        # Only used to make sure none of it reaches the AI.
        contact = contact_row.to_contact() if contact_row else _NO_CONTACT

        # Spend one pack (402/429 if the plan doesn't allow it), in the same transaction as the run it pays for.
        usage = await BillingService(self._session).reserve_pack(user.id, mode, datetime.now(UTC))
        run = await runs.add_run(application.id, profile_row.version, usage.mode)
        usage.run_id = run.id
        await self._session.commit()
        return PreparedRun(run_id=run.id, user_id=user.id, mode=usage.mode, job=JobSpec.model_validate(job.spec),
                           profile=CareerProfile.model_validate(profile_row.data), profile_version=profile_row.version,
                           contact=contact)

    # ----------------------------------------------------------------- phase 2: the event stream

    async def stream(self, run: PreparedRun, llm: GroqLLM) -> AsyncIterator[str]:
        started = time.perf_counter()
        status, error = "failed", "internal_error"
        resume_delivered = False
        yield sse_event("run", {"run_id": str(run.run_id), "mode": run.mode, "profile_version": run.profile_version})
        try:
            async for piece in stream_pack(llm, run.profile, run.contact, job=run.job, mode=run.mode):
                await self._save_piece(run.run_id, piece)  # saved first, so a dropped connection loses nothing
                resume_delivered = resume_delivered or piece.kind == PAID_PIECE
                yield sse_event(piece.kind, piece.content.model_dump(mode="json"))
            status, error = "succeeded", None
            yield sse_event("done", {"run_id": str(run.run_id), "cost_usd": round(llm.spent_usd, 6),
                                     "duration_ms": int((time.perf_counter() - started) * 1000)})
        except (StepError, BudgetExceeded, GroqAPIError) as exc:
            error = "upstream_error"
            logger.warning("Generation run %s: AI step failed: %s", run.run_id, exc)
            refunded = "" if resume_delivered else " It didn't use up a pack."
            yield sse_event("error", {"code": error, "message": "The AI service failed partway. Finished pieces "
                                      f"are saved; generate again to complete the pack.{refunded}"})
        except (asyncio.CancelledError, GeneratorExit):
            status, error = "cancelled", "client_disconnected"
            raise
        except Exception:
            logger.exception("Generation run %s crashed", run.run_id)
            yield sse_event("error", {"code": "internal_error", "message": "Something went wrong on our side"})
        finally:
            # Shielded: when the browser disconnects, the server keeps cancelling this task, and the run must
            # still be closed, its AI costs recorded and, without a resume, its pack given back.
            with anyio.CancelScope(shield=True):
                await self._finish(run, llm, status=status, error=error, resume_delivered=resume_delivered)

    async def _save_piece(self, run_id: uuid.UUID, piece: Piece) -> None:
        with anyio.CancelScope(shield=True):  # a finished piece is saved whole, even if the browser just left
            async with self._db.sessions() as session:
                await GenerationRepository(session).add_artifact(run_id, piece.kind,
                                                                 piece.content.model_dump(mode="json"))
                await session.commit()

    async def _finish(self, run: PreparedRun, llm: GroqLLM, *, status: str, error: str | None,
                      resume_delivered: bool) -> None:
        """Close the run, give its pack back if the resume never arrived, and record its AI calls.
        Never raises: it runs during cleanup."""
        try:
            async with self._db.sessions() as session:
                await GenerationRepository(session).finish_run(run.run_id, status=status, error=error,
                                                               cost_usd=round(llm.spent_usd, 6))
                if not resume_delivered:
                    await BillingService(session).release_run(run.run_id)
                await session.commit()
        except Exception:
            logger.exception("Could not close generation run %s (%s)", run.run_id, status)
        await record_llm_calls(self._db, llm.calls, user_id=run.user_id, purpose="generation", run_id=run.run_id)
        logger.info("Generation run %s %s: %d AI calls, $%.4f", run.run_id, status, len(llm.calls), llm.spent_usd)
