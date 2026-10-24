"""Text helpers shared by the linters, the ATS round-trip check, the eval graders and (later) the UI."""

from __future__ import annotations

import re
from functools import lru_cache


def normalize_key(value: str) -> str:
    """Comparison key for user-entered names: lowercase, separators collapsed. Display text keeps its casing."""
    return re.sub(r"[\s._\-/]+", " ", value.lower()).strip()


@lru_cache(maxsize=4096)
def _term_pattern(term: str) -> re.Pattern[str]:
    """Word-boundary aware: 'Java' never matches inside 'JavaScript', 'C' not inside 'C++'.

    Case-insensitive, except short terms (<= 3 chars: 'Go', 'R', 'C#', 'AWS') which are case-sensitive so that
    'Go' doesn't match 'go-live'. Spaces and hyphens are interchangeable ('real-time' = 'real time'), and a term
    ending in a letter also matches its plural ('API' -> 'APIs'), which is as far as lemmatization goes without NLP.
    """
    stripped = term.strip()
    parts = [re.escape(p) for p in re.split(r"[\s-]+", stripped) if p]
    body = r"[\s-]+".join(parts)
    plural = r"(?:e?s)?" if stripped[-1:].isalpha() else ""
    flags = 0 if len(stripped) <= 3 else re.IGNORECASE
    return re.compile(rf"(?<![^\W_]){body}{plural}(?![^\W_]|[+#])", flags)


def term_present(term: str, text: str) -> bool:
    """The one keyword matcher for the linters, the ATS check, the eval graders and the UI coverage numbers."""
    return bool(term.strip()) and _term_pattern(term).search(text) is not None
