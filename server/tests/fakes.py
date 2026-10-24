"""Test doubles for outside services. Tests never call the real Groq API."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import groq
import httpx


def _completion(payload: dict[str, Any], *, finish: str = "stop", prompt: int = 1000, cached: int = 0,
                completion: int = 500) -> SimpleNamespace:
    """An object shaped like a Groq chat-completion response."""
    usage = SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion,
                            prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
                            completion_tokens_details=SimpleNamespace(reasoning_tokens=200))
    message = SimpleNamespace(content=json.dumps(payload))
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish, message=message)], usage=usage)


class FakeGroq:
    """Stands in for `AsyncGroq`. Answers each request by the name of the requested output schema
    (e.g. "CareerProfile") and records every request so tests can inspect what would have been sent."""

    def __init__(self, answers: dict[str, list[dict[str, Any]]], finish: str = "stop"):
        self.answers, self.finish = answers, finish
        self.requests: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(kwargs)
        name = kwargs["response_format"]["json_schema"]["name"]
        queue = self.answers[name]
        payload = queue.pop(0) if len(queue) > 1 else queue[0]
        return _completion(payload, finish=self.finish, cached=600)


class FailingGroq(FakeGroq):
    """Fails every request for one output schema with a (non-retryable) Groq error; can slow another one down."""

    def __init__(self, answers, *, fail: str | None = None, slow: str | None = None, fail_after: float = 0):
        super().__init__(answers)
        self._fail, self._slow, self._fail_after = fail, slow, fail_after

    async def _create(self, **kwargs):
        name = kwargs["response_format"]["json_schema"]["name"]
        if name == self._slow:
            await asyncio.sleep(30)
        if name == self._fail:
            await asyncio.sleep(self._fail_after)  # lets the other parallel steps finish first, when a test needs that
            response = httpx.Response(400, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"))
            raise groq.BadRequestError("boom", response=response, body={"error": {"code": "context_length_exceeded"}})
        return await super()._create(**kwargs)
