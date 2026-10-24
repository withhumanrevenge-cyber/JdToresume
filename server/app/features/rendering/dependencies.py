"""FastAPI dependency for the document (download) service."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.core.db import SessionDep
from app.features.rendering.service import DocumentService


def get_document_service(session: SessionDep) -> DocumentService:
    return DocumentService(session)


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
