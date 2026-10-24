"""Download file names: `Jordan-Rivera-Resume-Figma.pdf`, the way recruiters expect to find them in a folder.

Names keep the person's own letters (`José-García-Resume-Figma.pdf`). The Content-Disposition header carries both
that UTF-8 name (RFC 6266 `filename*`) and a plain-ASCII fallback (`Jose-Garcia-Resume-Figma.pdf`) for older
clients.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal
from urllib.parse import quote

DocumentLabel = Literal["Resume", "Cover-Letter"]

MAX_PART = 40  # characters per part, so a long company name can't produce an unwieldy file name


def download_name(full_name: str, document: DocumentLabel, company: str | None, extension: str) -> str:
    """'Jordan Rivera', 'Resume', 'Figma, Inc.', 'pdf' -> 'Jordan-Rivera-Resume-Figma-Inc.pdf'."""
    parts = (_slug(full_name, limit=MAX_PART), document, _slug(company or "", limit=MAX_PART))
    return "-".join(part for part in parts if part) + f".{extension}"


def content_disposition(filename: str) -> str:
    """`attachment` with the UTF-8 name plus an ASCII fallback; nothing in it can break out of the header."""
    stem, _, extension = filename.rpartition(".")
    fallback = _slug(stem, ascii_only=True) or "document"
    return f"attachment; filename=\"{fallback}.{extension}\"; filename*=UTF-8''{quote(filename, safe='')}"


def _slug(text: str, *, ascii_only: bool = False, limit: int | None = None) -> str:
    """Letters and digits joined by single hyphens. Apostrophes vanish ("O'Neil" -> "ONeil")."""
    text = re.sub(r"['’]", "", unicodedata.normalize("NFKD" if ascii_only else "NFKC", text))
    if ascii_only:
        text = text.encode("ascii", "ignore").decode()
    words = [word for word in re.split(r"[\W_]+", text) if word]
    return "-".join(words)[:limit].strip("-")
