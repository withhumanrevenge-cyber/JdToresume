"""Server-Sent Events: the streaming format the web app reads with fetch() (frontend-standards).

Each event is an `event:` line, a `data:` line holding JSON, and a blank line:

    event: resume
    data: {"resume": {...}, "revised": false, ...}

`with_keepalive` adds a comment line (": keep-alive") whenever nothing was sent for a while, so proxies and the
load balancer don't close a stream that is just waiting on the AI (backend-standards §7).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import anyio

KEEPALIVE = ": keep-alive\n\n"
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}  # never cache or buffer a live stream


def sse_event(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"


async def with_keepalive(events: AsyncIterator[str], interval_seconds: float = 15.0) -> AsyncIterator[str]:
    """Pass `events` through unchanged, inserting a keep-alive comment after every quiet `interval_seconds`."""
    upcoming = asyncio.ensure_future(anext(events))
    try:
        while True:
            done, _ = await asyncio.wait({upcoming}, timeout=interval_seconds)
            if not done:
                yield KEEPALIVE
                continue
            try:
                item = upcoming.result()
            except StopAsyncIteration:
                return
            yield item
            upcoming = asyncio.ensure_future(anext(events))
    finally:
        # The browser went away (or we finished): stop the inner stream and wait for its cleanup. Shielded,
        # because the server keeps cancelling a disconnected request, which would cut that cleanup short.
        with anyio.CancelScope(shield=True):
            if not upcoming.done():
                upcoming.cancel()
            try:
                await upcoming
            except (asyncio.CancelledError, StopAsyncIteration, Exception):
                pass
            aclose = getattr(events, "aclose", None)
            if aclose is not None:
                await aclose()
