"""The only module that talks to Groq. Feature code calls `GroqLLM.run_step()` and gets a validated Pydantic object.

Cross-cutting concerns live here: strict structured outputs, model-specific reasoning params, PII guard,
budget guard, cost ledger, retries. See .claude/skills/llm-pipeline-standards.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, TypeVar

from groq import AsyncGroq, BadRequestError
from pydantic import BaseModel, ValidationError

from app.llm.pii import assert_no_contact_pii
from app.llm.prompts import global_policy, prompt_version, step_prompt
from app.llm.router import PRICES, StepConfig
from app.llm.schemas import ContactDetails, strict_json_schema

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
Block = tuple[str, str | BaseModel | list[Any] | dict[str, Any]]

# Groq occasionally rejects its own generation as not matching the strict schema (HTTP 400, code
# "json_validate_failed"). It's intermittent, so one fresh attempt almost always succeeds.
SCHEMA_RETRIES = 1


def _is_schema_mismatch(exc: BadRequestError) -> bool:
    error = exc.body.get("error", {}) if isinstance(exc.body, dict) else {}
    return error.get("code") == "json_validate_failed" or "expected schema" in str(error.get("message", ""))


class StepError(RuntimeError):
    def __init__(self, step: str, model: str, message: str):
        super().__init__(f"{step} on {model}: {message}")
        self.step, self.model = step, model


class StepTruncated(StepError):
    """Hit max_completion_tokens (often reasoning ran long). Never parse partial JSON as success."""


class StepInvalidOutput(StepError):
    """Output failed schema validation (should not happen in strict mode, but models can emit nothing)."""


class BudgetExceeded(RuntimeError):
    pass


class LLMCall(BaseModel):
    step: str
    model: str
    prompt_version: str
    prompt_tokens: int
    cached_tokens: int
    completion_tokens: int
    reasoning_tokens: int | None
    cost_usd: float
    latency_ms: int
    finish_reason: str | None


def to_data(value: str | BaseModel | list[Any] | dict[str, Any]) -> str:
    """Serialize a data block deterministically (sorted keys, compact) so cached prefixes stay byte-stable."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    elif isinstance(value, list):
        value = [v.model_dump(mode="json") if isinstance(v, BaseModel) else v for v in value]
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def render_blocks(blocks: list[Block]) -> str:
    return "\n\n".join(f"<{tag}>\n{to_data(value)}\n</{tag}>" for tag, value in blocks)


class GroqLLM:
    def __init__(
        self,
        *,
        budget_usd: float = 1.0,
        max_concurrency: int = 4,
        client: AsyncGroq | None = None,
        semaphore: asyncio.Semaphore | None = None,
    ):
        """One instance per run (its ledger and budget are per run); share `client` and `semaphore` across runs."""
        self._client = client or AsyncGroq(max_retries=4, timeout=180)
        self._sem = semaphore or asyncio.Semaphore(max_concurrency)
        self.budget_usd = budget_usd
        self.spent_usd = 0.0
        self.calls: list[LLMCall] = []

    def build_messages(self, step: str, prefix_blocks: list[Block], blocks: list[Block]) -> list[dict[str, str]]:
        # Stable content first (system policy, then the career profile) so Groq's automatic prefix cache hits
        # across steps; step instructions and volatile data come after.
        parts = [render_blocks(prefix_blocks)] if prefix_blocks else []
        parts += [step_prompt(step), render_blocks(blocks)]
        return [
            {"role": "system", "content": global_policy()},
            {"role": "user", "content": "\n\n".join(p for p in parts if p)},
        ]

    async def run_step(
        self,
        step: str,
        *,
        output: type[T],
        cfg: StepConfig,
        blocks: list[Block],
        prefix_blocks: list[Block] | None = None,
        contact: ContactDetails | None = None,
    ) -> T:
        if self.spent_usd >= self.budget_usd:
            raise BudgetExceeded(f"spent ${self.spent_usd:.4f} of ${self.budget_usd:.2f} before {step}")
        messages = self.build_messages(step, prefix_blocks or [], blocks)
        if contact is not None:
            assert_no_contact_pii(messages[1]["content"], contact)

        kwargs: dict[str, Any] = {
            "model": cfg.model,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": output.__name__, "strict": True, "schema": strict_json_schema(output)},
            },
            "max_completion_tokens": cfg.max_completion_tokens,
            "reasoning_effort": cfg.effort,
        }
        if cfg.model.startswith("openai/gpt-oss"):
            kwargs["include_reasoning"] = False  # still billed as output; we just don't download it
        elif cfg.model.startswith("qwen/"):
            kwargs["reasoning_format"] = "hidden"  # "raw" is rejected together with JSON output

        async with self._sem:
            started = time.perf_counter()
            for attempt in range(SCHEMA_RETRIES + 1):
                try:
                    response = await self._client.chat.completions.create(**kwargs)
                    break
                except BadRequestError as exc:
                    if attempt == SCHEMA_RETRIES or not _is_schema_mismatch(exc):
                        raise
                    logger.warning("%s on %s: output didn't match the schema, retrying once", step, cfg.model)
            latency_ms = int((time.perf_counter() - started) * 1000)

        choice = response.choices[0]
        usage = response.usage
        cached = (usage.prompt_tokens_details.cached_tokens or 0) if usage and usage.prompt_tokens_details else 0
        reasoning = usage.completion_tokens_details.reasoning_tokens if usage and usage.completion_tokens_details else None
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        cost = PRICES[cfg.model].cost(prompt_tokens, cached, completion_tokens)
        self.spent_usd += cost
        self.calls.append(LLMCall(
            step=step, model=cfg.model, prompt_version=prompt_version(step), prompt_tokens=prompt_tokens,
            cached_tokens=cached, completion_tokens=completion_tokens, reasoning_tokens=reasoning,
            cost_usd=round(cost, 6), latency_ms=latency_ms, finish_reason=choice.finish_reason,
        ))

        if choice.finish_reason == "length":
            raise StepTruncated(step, cfg.model, f"hit max_completion_tokens={cfg.max_completion_tokens}")
        content = choice.message.content
        if not content:
            raise StepInvalidOutput(step, cfg.model, f"empty content (finish_reason={choice.finish_reason})")
        try:
            return output.model_validate_json(content)
        except ValidationError as exc:
            raise StepInvalidOutput(step, cfg.model, str(exc)[:500]) from exc
