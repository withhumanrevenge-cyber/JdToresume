"""Model routing and the single price table. Feature code never hardcodes a model ID.

Prices: GroqCloud list prices, Oct 2026 ($ per 1M tokens). Cached input = 50% off on gpt-oss (automatic prefix caching).
qwen/qwen3.8-27b is a *preview* model on Groq (can be withdrawn at short notice); it is the only vision-capable option.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Mode = Literal["deep", "quick"]
Effort = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class Price:
    input: float
    cached_input: float
    output: float

    def cost(self, prompt_tokens: int, cached_tokens: int, completion_tokens: int) -> float:
        uncached = max(prompt_tokens - cached_tokens, 0)
        return (uncached * self.input + cached_tokens * self.cached_input + completion_tokens * self.output) / 1e6


GPT_OSS_120B = "openai/gpt-oss-120b"
GPT_OSS_20B = "openai/gpt-oss-20b"
QWEN_38_27B = "qwen/qwen3.8-27b"

PRICES: dict[str, Price] = {
    GPT_OSS_120B: Price(input=0.15, cached_input=0.075, output=0.60),
    GPT_OSS_20B: Price(input=0.075, cached_input=0.0375, output=0.30),
    QWEN_38_27B: Price(input=0.80, cached_input=0.80, output=4.00),
}


@dataclass(frozen=True)
class StepConfig:
    model: str
    effort: Effort
    max_completion_tokens: int


# Reasoning tokens count as output on gpt-oss, so max_completion_tokens must leave room for them.
_DEEP: dict[str, StepConfig] = {
    "resume_parse":  StepConfig(GPT_OSS_120B, "low", 16000),
    "jd_extract":    StepConfig(GPT_OSS_120B, "low", 6000),
    "match_plan":    StepConfig(GPT_OSS_120B, "medium", 8000),
    "resume_tailor": StepConfig(GPT_OSS_120B, "medium", 12000),
    "verify":        StepConfig(GPT_OSS_120B, "medium", 6000),
    "revise":        StepConfig(GPT_OSS_120B, "medium", 12000),
    "cover_letter":  StepConfig(GPT_OSS_120B, "medium", 6000),
    "outreach":      StepConfig(GPT_OSS_120B, "low", 4000),
}
_QUICK: dict[str, StepConfig] = {
    step: StepConfig(GPT_OSS_20B, "low" if step in ("resume_parse", "jd_extract", "outreach") else "medium",
                     cfg.max_completion_tokens)
    for step, cfg in _DEEP.items()
}
ROUTES: dict[Mode, dict[str, StepConfig]] = {"deep": _DEEP, "quick": _QUICK}


def step_config(step: str, mode: Mode = "deep", model_override: str | None = None) -> StepConfig:
    """Config for a step. `model_override` runs every step on one model (used by the eval bake-off)."""
    cfg = ROUTES[mode][step]
    if model_override:
        if model_override not in PRICES:
            raise ValueError(f"Unknown model {model_override!r}; add it to PRICES first")
        return StepConfig(model_override, cfg.effort, cfg.max_completion_tokens)
    return cfg
