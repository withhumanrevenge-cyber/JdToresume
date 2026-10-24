"""Download endpoints: the resume and cover letter as PDF or DOCX, and "What the ATS sees" for either."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.features.rendering.dependencies import DocumentServiceDep
from app.features.rendering.document import TemplateName
from app.features.rendering.filenames import content_disposition
from app.features.rendering.schemas import FILES, AtsView, DocumentKind, FileFormat, FileName
from app.features.rendering.service import MEDIA_TYPES
from app.features.users.dependencies import CurrentUser

router = APIRouter(prefix="/applications", tags=["documents"])

TemplateQuery = Annotated[TemplateName, Query(description="Resume layout (the cover letter has one layout)")]

_DOWNLOAD_DESCRIPTION = """The file, named like `Jordan-Rivera-Resume-Figma.pdf`.

Every file is read back the way an ATS would before it is sent. `X-ATS-Check: passed` or `failed` carries the
result; `GET /v1/applications/{id}/ats-check` shows the extracted text and the reasons."""


@router.get(
    "/{application_id}/files/{file_name}",
    summary="Download the resume or cover letter as PDF or DOCX",
    response_class=Response,
    responses={200: {"content": {media_type: {} for media_type in MEDIA_TYPES.values()},
                     "description": _DOWNLOAD_DESCRIPTION}},
)
async def download(user: CurrentUser, documents: DocumentServiceDep, application_id: uuid.UUID, file_name: FileName,
                   template: TemplateQuery = "classic") -> Response:
    document, fmt = FILES[file_name]
    rendered = await documents.render(user, application_id, document, fmt, template)
    return Response(
        rendered.content,
        media_type=rendered.media_type,
        headers={
            "Content-Disposition": content_disposition(rendered.file_name),
            "X-ATS-Check": "passed" if rendered.check.parse_ok else "failed",
            "Cache-Control": "private, no-store",  # personal data: never kept by shared or browser caches
        },
    )


@router.get(
    "/{application_id}/ats-check",
    response_model=AtsView,
    summary="What the ATS sees: the text a parser reads from the file, and the round-trip check",
)
async def ats_check(
    user: CurrentUser,
    documents: DocumentServiceDep,
    application_id: uuid.UUID,
    document: Annotated[DocumentKind, Query()] = "resume",
    fmt: Annotated[FileFormat, Query(alias="format")] = "pdf",
    template: TemplateQuery = "classic",
) -> AtsView:
    rendered = await documents.render(user, application_id, document, fmt, template)
    return AtsView(document=document, format=fmt, file_name=rendered.file_name, pages=rendered.pages,
                   text=rendered.text, check=rendered.check)
