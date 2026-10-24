"""FastAPI dependency that gives a route its LLM client.

One shared Groq HTTP client lives on `app.state` (created at startup, see main.py). Each request gets its own
`GroqLLM`, so its spend cap and call ledger cover just that request. Routes declare `llm: LLMDep`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.errors import ServiceUnavailableError
from app.llm.client import GroqLLM


def get_llm(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> GroqLLM:
    groq_client = getattr(request.app.state, "groq", None)
    if groq_client is None:
        raise ServiceUnavailableError("The AI service isn't configured on this server (GROQ_API_KEY is missing)")
    return GroqLLM(budget_usd=settings.llm_run_budget_usd, client=groq_client, semaphore=request.app.state.llm_slots)


LLMDep = Annotated[GroqLLM, Depends(get_llm)]
