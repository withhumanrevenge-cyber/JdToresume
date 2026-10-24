"""What the download endpoints accept and the "What the ATS sees" endpoint returns."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.features.rendering.ats_roundtrip import AtsCheck

DocumentKind = Literal["resume", "cover_letter"]  # the artifact kinds that become files
FileFormat = Literal["pdf", "docx"]
FileName = Literal["resume.pdf", "resume.docx", "cover-letter.pdf", "cover-letter.docx"]

FILES: dict[str, tuple[DocumentKind, FileFormat]] = {
    "resume.pdf": ("resume", "pdf"),
    "resume.docx": ("resume", "docx"),
    "cover-letter.pdf": ("cover_letter", "pdf"),
    "cover-letter.docx": ("cover_letter", "docx"),
}


class AtsView(BaseModel):
    document: DocumentKind
    format: FileFormat
    file_name: str = Field(description="The name the file downloads under")
    pages: int | None = Field(description="Page count of the PDF; None for a .docx (Word decides the pages)")
    text: str = Field(description="The plain text a parser reads from the file, in reading order")
    check: AtsCheck
