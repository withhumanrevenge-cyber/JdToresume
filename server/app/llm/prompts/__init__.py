"""Prompt files, loaded once. Versions are content hashes, so a prompt edit can never ship with a stale version."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

from app.llm.style.linters import banned_phrases

PROMPT_DIR = Path(__file__).parent


@lru_cache(maxsize=1)
def global_policy() -> str:
    text = (PROMPT_DIR / "_global_policy.md").read_text(encoding="utf-8")
    hard = ", ".join(f'"{phrase}"' for phrase, soft in banned_phrases() if not soft)
    return text.replace("{{BANNED_PHRASES}}", hard).strip()


@lru_cache(maxsize=None)
def step_prompt(step: str) -> str:
    return (PROMPT_DIR / f"{step}.md").read_text(encoding="utf-8").strip()


def prompt_version(step: str) -> str:
    digest = hashlib.sha256((global_policy() + "\n" + step_prompt(step)).encode("utf-8")).hexdigest()[:10]
    return f"{step}@{digest}"
