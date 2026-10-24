# ADR-0001: LLM provider is Groq (GroqCloud), not Claude

- **Status:** Accepted, 2026-10-19 (founder decision)
- **Supersedes:** the Claude Opus 5.5 / Haiku 5.5 model plan in ARCHITECTURE §4 and COSTS §1–2 (original version)

## Decision
All pipeline steps run on GroqCloud through the official `groq` Python SDK (`AsyncGroq`), wrapped by `server/app/llm/client.py`.

| Role | Model (Oct 2026) | Price $/1M (in / cached in / out) | Notes |
|------|------------------|-----------------------------------|-------|
| Deep (paid) | `openai/gpt-oss-120b` | 0.15 / 0.075 / 0.60 | Production model. Strict structured outputs, automatic prefix caching, `reasoning_effort` low/medium/high |
| Quick (free tier, scans) | `openai/gpt-oss-20b` | 0.075 / 0.0375 / 0.30 | Production model. Same features, about 2× faster |
| Vision (screenshots) + bake-off candidate | `qwen/qwen3.8-27b` | 0.80 / – / 4.00 | **Preview** (can be withdrawn at short notice). The only self-serve vision model: 3 images per request, 2,048 tokens each |

The final split is decided by the Phase 0 bake-off (`evals/run_eval.py`). Hard gates: fabrication = 0, ATS parse = 100%.

## Why
- **Cost:** a full application pack costs **~$0.017 (Deep) / ~$0.008 (Quick)**, against ~$0.47 on Claude Opus 5.5. The free tier and India pricing work without rationing (COSTS §2).
- **Speed:** Groq's LPU inference keeps the whole pack in the "instant" range, even without token streaming.
- **Open-weight models:** gpt-oss is also served by other hosts, so there's a realistic overflow or fallback path that doesn't require rewriting prompts.

## Consequences (designed in)
1. **No streaming with structured outputs** on Groq. The UI streams *step-level* events (match report → resume → letters) instead of tokens (ARCHITECTURE §4.3).
2. **No native PDF input.** Uploaded resumes go through local text extraction (pdfminer.six / pypdf, python-docx) before the parse step. Scanned PDFs need OCR (Phase 1).
3. **Vision depends on a preview model.** Screenshots go to `qwen/qwen3.8-27b`, with local OCR as the fallback if it's withdrawn (Phase 1 ingestion work).
4. **Rate limits:** base limits for gpt-oss are 30 RPM, 8K TPM and 200K TPD, which can't fit a single pipeline request (~15–20K tokens with the completion budget). **A Developer (pay-as-you-go) key is required** even for evals. Production needs a limit increase ahead of launch.
5. **Data:** Groq doesn't retain inference inputs by default, but may log them for up to 30 days for abuse or reliability investigations unless that's opted out. **Enable Zero Data Retention in Data Controls for production.** That disables Batch, which is fine: production is synchronous, and evals use synthetic data on a separate key or project. Data is stored in the US (GCP); SCCs apply for EU transfers.
6. **Quality risk:** open models may write blander prose or fabricate more than frontier models. That's mitigated by the deterministic linters, the verifier and revise loop, and the eval gates, and it's measured, not assumed.
7. **Model churn:** Groq's catalog changes fast (Kimi K2 and the Llama 4 models are gone as of Oct 2026). Model IDs live only in `server/app/llm/router.py`, and every model change goes through the eval gate.

## Alternatives considered
- **Claude (Opus 5.5 Deep / Haiku 5.5 Quick):** the strongest writing and the most API features (PDF input, streaming with structured outputs), but ~28× the per-pack cost of gpt-oss-120b. Kept as the reference row in `docs/models/unit_economics.py`.
- **Other gpt-oss hosts:** possible overflow providers later. They aren't integrated now (YAGNI).
