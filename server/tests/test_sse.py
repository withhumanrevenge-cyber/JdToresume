"""Part 6: the Server-Sent Events helpers."""

from __future__ import annotations

import asyncio

import pytest

from app.core.sse import KEEPALIVE, sse_event, with_keepalive

pytestmark = pytest.mark.anyio


def test_event_format():
    assert sse_event("resume", {"title": "Engineer", "n": 1}) == 'event: resume\ndata: {"title":"Engineer","n":1}\n\n'
    assert sse_event("note", {"text": "café"}).endswith('{"text":"café"}\n\n')  # readable, not \u-escaped


async def test_keepalive_comments_fill_quiet_gaps():
    async def slow():
        yield "first"
        await asyncio.sleep(0.2)
        yield "second"

    received = [item async for item in with_keepalive(slow(), interval_seconds=0.05)]

    assert received[0] == "first" and received[-1] == "second"
    assert KEEPALIVE in received[1:-1]


async def test_stopping_early_lets_the_inner_stream_clean_up():
    cleaned_up = asyncio.Event()

    async def endless():
        try:
            while True:
                yield "piece"
                await asyncio.sleep(0.01)
        finally:
            cleaned_up.set()  # in the real stream: close the run, record AI costs

    stream = with_keepalive(endless(), interval_seconds=1)
    assert await anext(stream) == "piece"
    await stream.aclose()  # what the server does when the browser disconnects

    assert cleaned_up.is_set()
