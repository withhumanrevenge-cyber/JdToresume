"""The generate endpoint: write the application pack and stream each piece as it finishes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.sse import SSE_HEADERS, with_keepalive
from app.features.generation.dependencies import GenerationServiceDep
from app.features.users.dependencies import CurrentUser
from app.llm.dependencies import LLMDep
from app.llm.router import Mode

router = APIRouter(prefix="/applications", tags=["applications"])

_STREAM_DESCRIPTION = """Server-Sent Events, in this order:

- `run`: the run has started (`run_id`, `mode`, `profile_version`)
- `match_report`: requirement-by-requirement fit, gaps and questions
- `resume`, `cover_letter`, `outreach`: in whichever order they finish
- `done` (`cost_usd`, `duration_ms`) or `error` (`code`, `message`)

Lines starting with `:` are keep-alive comments; ignore them."""


@router.post(
    "/{application_id}/generate",
    summary="Write the application pack, streaming each piece as it finishes",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": _STREAM_DESCRIPTION}},
)
async def generate(
    user: CurrentUser,
    generation: GenerationServiceDep,
    llm: LLMDep,
    application_id: uuid.UUID,
    mode: Annotated[Mode | None, Query(description="deep (best quality) or quick (faster). Leave it out to use "
                                                     "the best mode your plan has left")] = None,
) -> StreamingResponse:
    run = await generation.prepare(user, application_id, mode)  # errors here (incl. 402/429) are normal JSON
    return StreamingResponse(with_keepalive(generation.stream(run, llm)), media_type="text/event-stream",
                             headers=SSE_HEADERS)
