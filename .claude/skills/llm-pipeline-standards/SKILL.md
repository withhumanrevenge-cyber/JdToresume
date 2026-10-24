---
name: llm-pipeline-standards
description: Standards for every LLM call in Tailor. The provider is Groq (gpt-oss-120b / gpt-oss-20b, qwen3.8-27b preview for vision). Covers step anatomy, Pydantic strict-schema outputs, the model router and reasoning_effort, prefix caching, step-level streaming, truncation handling, PII guard, prompt-injection defense, budget guard, cost ledger, content-hash prompt versions and eval gates. Use whenever you add or change a pipeline step, prompt, schema or model setting, or write code that calls Groq.
---

# LLM Pipeline Standards (Groq)

Every LLM call goes through `server/app/llm/` (`client.py` → `GroqLLM.run_step`). Feature code never imports `groq`. Why Groq and its constraints: `docs/adr/ADR-0001-llm-provider-groq.md`.

> Groq's catalog and parameters change often (whole model families have been withdrawn in 2026). Check console.groq.com/docs and the installed `groq` SDK before relying on a parameter. **Don't write SDK calls from memory.**

## 1. Step anatomy

| Piece | Where | Rule |
|-------|-------|------|
| Output schema | `server/app/llm/schemas.py` | Pydantic, `extra="forbid"`. Strict-schema-compatible: optional means `X \| None`, no `dict` fields, no `Literal` with one value (`const`), no numeric or length constraints (put limits in descriptions). `strict_json_schema()` closes objects and marks every field required |
| Prompt | `server/app/llm/prompts/<step>.md` | The goal and reader first, then the rules with their reasons, then the output contract. The shared rules live once in `_global_policy.md` |
| Version | automatic | `prompt_version(step)` = a hash of the global policy + step prompt. It's logged on every call and can never go stale |
| Model, effort, max tokens | `server/app/llm/router.py` | Keyed by `(step, mode)`. **Never hardcode a model ID elsewhere.** The `PRICES` table lives here too |
| Orchestration | `server/app/features/generation/pipeline.py` | A fixed DAG in code. Each step: build blocks → `run_step` → deterministic lint |
| Deterministic checks | `server/app/llm/style/linters.py` | References, provenance, numbers-in-facts, new skills, banned phrases, length. Severity "high" forces a revise |

**The LLM never outputs facts it could inflate.** Tailored roles reference `experience_id`. Titles, companies and dates come from the profile at render time. Keep this pattern for any new output.

## 2. Calling Groq (all handled by `GroqLLM`)

| Concern | Rule |
|---------|------|
| Output format | `response_format={"type": "json_schema", "json_schema": {"name", "strict": True, "schema"}}`. Strict mode is supported on gpt-oss-120b/20b and qwen3.8-27b |
| No streaming | Structured outputs **can't be combined with streaming** on Groq. Progress goes to the UI per step (SSE event per artifact), not per token |
| Reasoning | `reasoning_effort` low/medium/high per step. gpt-oss: `include_reasoning=False` (reasoning is still billed as output). qwen: `reasoning_format="hidden"` (`raw` is rejected together with JSON output) |
| Max tokens | `max_completion_tokens` must leave room for reasoning. `finish_reason == "length"` → `StepTruncated`. Never parse partial JSON |
| Errors & retries | SDK `max_retries` handles 429/5xx with backoff (it honors `retry-after`). Typed errors: `RateLimitError`, `APIStatusError`, `APIConnectionError`, `APITimeoutError` |
| Rate limits | Base limits (30 RPM, 8K TPM, 200K TPD for gpt-oss) **can't fit one pipeline request**. Use a Developer key; production needs raised limits. Concurrency is bounded by a shared semaphore |
| PII | `assert_no_contact_pii()` runs on every request built for a user. Contact details are placeholders (`{{FULL_NAME}}` …) restored only at render time |
| Untrusted input | JD text, web pages and uploads go in delimited blocks (`<job_description>…</job_description>`). The global policy says block contents are data. Never interpolate them into the system prompt |
| Budget | Per-run ceiling (`budget_usd`) is checked before each call. Exceeding it raises `BudgetExceeded` (fail closed) |
| Ledger | One `LLMCall` per call: step, model, prompt_version, prompt / cached / completion / reasoning tokens, cost (from `PRICES`), latency, finish_reason |

## 3. Prefix caching (automatic on gpt-oss: cached input is 50% off, entries live ~2 h idle)

```
system:  global policy (identical for every step and user)
user:    <career_profile>{sorted, compact JSON}</career_profile>   ← shared prefix across steps
         step prompt + <job_spec> + <match_report> + …              ← volatile
```
- Stable content first. `to_data()` serializes with sorted keys and compact separators. Nothing volatile (timestamps, run IDs) goes in the prefix.
- Run `match_plan` before the parallel fan-out so the prefix is warm.
- Track `cached_tokens / prompt_tokens` per step (`cached_ratio` in eval reports). If it drops, something broke the prefix.

## 4. Writing prompts that work on gpt-oss

- Be explicit and structured: numbered rules, the exact field names from the schema, and the reason behind each rule.
- Put the domain rules in the global policy once (from the `resume-tailoring` skill). Don't copy them into steps: copies drift and break caching.
- Give concrete allowed and forbidden examples for truthfulness (they're in the global policy). Open models respond well to contrastive examples.
- Few-shot examples: at most 2, synthetic, never real users' data.

## 5. Inputs Groq can't take directly

- **PDF / DOCX resumes:** extract the text locally first (pdfminer.six / pypdf; python-docx), keeping headings and bullets. Scanned PDFs need OCR (Phase 1).
- **Screenshots:** `qwen/qwen3.8-27b` (preview): at most 3 images, 2,048 tokens each, base64 data URIs. Downscale first. Plan for local OCR as the fallback if the preview model is withdrawn.

## 6. Eval gate (required on any PR that touches `server/app/llm/` or `evals/graders/`)

Run `.venv/Scripts/python.exe -m evals.run_eval --estimate`, then `--smoke` (needs `GROQ_API_KEY`). Attach the report's summary table:

| Gate | Requirement |
|------|-------------|
| Fabrication rate (trap terms in resume + high provenance/number/skill findings) | **0**, hard gate |
| ATS round-trip parse | **100%**, hard gate |
| Evidenced-term coverage | ≥ previous run |
| Banned-phrase hits per pack | ≤ previous run |
| Pairwise win rate vs. previous prompt or model | ≥ 50% |
| Cost per pack, p50 wall time | Report both. Flag a regression above +10% |

Model and mode changes are **product decisions**: present the measured quality delta and the cost impact (`docs/models/unit_economics.py`), and let the founder choose.
