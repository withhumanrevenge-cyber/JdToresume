"""Turning a generated pack into files: the resume and cover letter as PDF or DOCX, each read back the way an ATS
would read it before it is handed over.

Files are rendered on request, not stored. Rendering is deterministic and takes well under a second, so there is
nothing to keep in sync yet; the `renders` table and S3 cache (ARCHITECTURE §9) arrive with editable artifacts.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import release_connection
from app.core.errors import InvalidInputError, NotFoundError
from app.features.applications.repository import ApplicationRepository
from app.features.generation.repository import GenerationRepository
from app.features.profiles.repository import ProfileRepository
from app.features.rendering.ats_roundtrip import AtsCheck, check_text, extract, extract_docx
from app.features.rendering.cover_letter import build_cover_letter_document
from app.features.rendering.docx_renderer import cover_letter_docx, resume_docx
from app.features.rendering.document import (
    RenderOptions, TemplateName, build_resume_document, default_page_limit,
)
from app.features.rendering.filenames import download_name
from app.features.rendering.schemas import DocumentKind, FileFormat
from app.features.rendering.typst_renderer import count_pages, render_cover_letter_pdf, render_fit
from app.features.users.models import UserRow
from app.llm.schemas import CareerProfile, ContactDetails, CoverLetter, JobSpec, MatchReport, TailoredResume

logger = logging.getLogger(__name__)

MEDIA_TYPES: dict[FileFormat, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_LABELS: dict[DocumentKind, str] = {"resume": "resume", "cover_letter": "cover letter"}


class NotGeneratedError(NotFoundError):
    code = "not_generated"


class ContactRequiredError(InvalidInputError):
    code = "contact_required"


@dataclass(frozen=True)
class RenderedFile:
    content: bytes
    media_type: str
    file_name: str
    pages: int | None
    text: str  # what the ATS sees
    check: AtsCheck


@dataclass(frozen=True)
class _Inputs:
    """Everything a render needs, read from the database up front so rendering itself never touches it."""

    piece: dict[str, Any]  # the saved artifact content
    profile: CareerProfile  # the version the pack was written from
    contact: ContactDetails
    job: JobSpec
    relevance: dict[str, int]  # fact id -> relevance score, for fit-to-page


class DocumentService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def render(self, user: UserRow, application_id: uuid.UUID, document: DocumentKind, fmt: FileFormat,
                     template: TemplateName) -> RenderedFile:
        inputs = await self._inputs(user, application_id, document)
        await release_connection(self._session)  # don't hold a database connection while rendering
        today = datetime.now(UTC).date()
        if document == "resume":
            rendered = await asyncio.to_thread(_render_resume, inputs, fmt, template, today)
        else:
            rendered = await asyncio.to_thread(_render_cover_letter, inputs, fmt, today)
        if not rendered.check.parse_ok:
            # Still delivered (it's the user's document), but a failing check usually means a template bug.
            logger.warning("ATS check failed for the %s %s of application %s: %s", document, fmt, application_id,
                           rendered.check.issues)
        return rendered

    async def _inputs(self, user: UserRow, application_id: uuid.UUID, document: DocumentKind) -> _Inputs:
        found = await ApplicationRepository(self._session).get_with_job(user.id, application_id)
        if found is None:
            raise NotFoundError("Application not found")
        _, job = found

        runs = GenerationRepository(self._session)
        latest = await runs.latest_artifact(application_id, document)
        if latest is None:
            raise NotGeneratedError(f"There is no {_LABELS[document]} yet: generate the pack first")
        run, artifact = latest

        profiles = ProfileRepository(self._session)
        contact_row = await profiles.get_contact(user.id)
        if contact_row is None or not contact_row.full_name.strip() or not contact_row.email.strip():
            raise ContactRequiredError("Add your name and email first: they go at the top of the document")
        profile_row = await profiles.profile_version(user.id, run.profile_version)
        if profile_row is None:
            raise NotGeneratedError("The profile this pack was written from is gone: generate the pack again")

        match = await runs.artifact(run.id, "match_report")
        relevance = ({fr.fact_id: fr.score for fr in MatchReport.model_validate(match.content).fact_relevance}
                     if match else {})
        return _Inputs(piece=artifact.content, profile=CareerProfile.model_validate(profile_row.data),
                       contact=contact_row.to_contact(), job=JobSpec.model_validate(job.spec), relevance=relevance)


# --------------------------------------------------------------------------- rendering (no database, runs in a thread)

def _render_resume(inputs: _Inputs, fmt: FileFormat, template: TemplateName, today: date) -> RenderedFile:
    resume = TailoredResume.model_validate(inputs.piece["resume"])
    options = RenderOptions.for_profile(inputs.profile, template=template)
    limit = default_page_limit(inputs.profile, this_year=today.year)
    # The PDF decides what fits; the .docx then carries exactly the same bullets.
    pdf, fitted = render_fit(resume, inputs.profile, inputs.contact, options, limit, inputs.relevance)
    document = build_resume_document(fitted, inputs.profile, inputs.contact, options)
    data = pdf if fmt == "pdf" else resume_docx(document)
    name = download_name(inputs.contact.full_name, "Resume", inputs.job.company, fmt)
    return _checked(data, fmt, name, inputs, expected_sections=[s["kind"] for s in document["sections"]])


def _render_cover_letter(inputs: _Inputs, fmt: FileFormat, today: date) -> RenderedFile:
    letter = CoverLetter.model_validate(inputs.piece["letter"])
    document = build_cover_letter_document(letter, inputs.contact, inputs.job,
                                           region=inputs.profile.preferences.region, today=today)
    data = render_cover_letter_pdf(document) if fmt == "pdf" else cover_letter_docx(document)
    name = download_name(inputs.contact.full_name, "Cover-Letter", inputs.job.company, fmt)
    return _checked(data, fmt, name, inputs, expected_sections=[])


def _checked(data: bytes, fmt: FileFormat, file_name: str, inputs: _Inputs, *,
             expected_sections: list[str]) -> RenderedFile:
    """Read the finished file back the way an ATS would. Every render goes through here."""
    extracted = extract(data) if fmt == "pdf" else extract_docx(data)
    return RenderedFile(
        content=data,
        media_type=MEDIA_TYPES[fmt],
        file_name=file_name,
        pages=count_pages(data) if fmt == "pdf" else None,
        text=extracted.primary,
        check=check_text(extracted, inputs.contact, expected_sections, inputs.job),
    )
