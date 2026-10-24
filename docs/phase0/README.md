# Phase 0: status and how to run it

The Phase 0 exit criteria are in [ROADMAP.md](../ROADMAP.md). The LLM provider is Groq ([ADR-0001](../adr/ADR-0001-llm-provider-groq.md)).

## What's built

| Piece | Where | State |
|-------|-------|-------|
| Step contracts (strict schemas for Groq) | `server/app/llm/schemas.py` | Done; tested |
| Groq client (strict JSON, reasoning params, PII guard, budget, cost ledger) | `server/app/llm/client.py`, `router.py`, `pii.py` | Done; tested offline with a fake client. **Not yet run against the real API** |
| Prompts: global policy + 8 steps (versions = content hashes) | `server/app/llm/prompts/` | v1 written; untested on real models |
| Deterministic linters (references, provenance, numbers, new skills with implications, banned phrases, length) | `server/app/llm/style/` | Done; tested |
| Pipeline DAG (extract → match → tailor ∥ letter ∥ outreach → lint + verify → revise) | `server/app/features/generation/pipeline.py` | Done; tested offline |
| Resume onboarding (local text extraction + contact redaction → profile) | `server/app/features/profiles/parse.py` | Done (PDF, TXT, MD; DOCX in Phase 1) |
| Typst renderer (classic, modern) + fit-to-page + ATS round-trip check | `server/app/features/rendering/`, `templates/` | Done; ~5 ms per render, 39 tests |
| Eval harness: dataset, deterministic grader, ATS grader, pairwise judge, bake-off runner, cost estimate | `evals/` | Done; tested offline end to end |
| Concierge CLI for real pilot users | `server/app/cli/concierge.py` | Done; needs a key |
| Interview guide, concierge playbook | `docs/phase0/` | Done |

## Run it (Windows, from the repo root)

```bash
.venv/Scripts/python.exe -m pytest -q
```

```bash
.venv/Scripts/python.exe -m evals.run_eval --estimate
```

With a Groq **Developer-tier** key in `GROQ_API_KEY` (environment variable, or a line `GROQ_API_KEY=...` in a gitignored `.env` at the repo root) (base limits of 8K tokens/min can't fit one pipeline request):

```bash
.venv/Scripts/python.exe -m evals.run_eval --smoke
```

```bash
.venv/Scripts/python.exe -m evals.run_eval --models openai/gpt-oss-120b openai/gpt-oss-20b qwen/qwen3.8-27b --budget 4
```

Estimated cost: the smoke run is ~$0.09; the full 3-model bake-off with the judge is ~$1.70. Allow up to 2× for long reasoning; `--budget` stops new work past the cap.

Reports go to `evals/reports/<timestamp>/` (`report.md`, `results.json`, plus one JSON and one PDF per pack, for human review).

## Next steps, in order
1. Set a Groq Developer key and run `--smoke`, then the full bake-off. Fix whatever the first real run breaks (truncation limits, prompt misreads).
2. Replace the token budgets in `docs/COSTS.md` §1.2 and `docs/models/unit_economics.py` with real ledger medians.
3. Start the interviews (`interview-guide.md`) and recruit concierge users (`concierge-playbook.md`). Every hand fix becomes an eval case.
4. Blind recruiter review: originals vs. tailored PDFs from the bake-off.
5. Decide Quick and Deep models (ROADMAP decision gates).

## Known gaps (Phase 1 backlog)
- **Fonts:** no proportional sans is embedded in Typst. Vendor Inter / Source Sans 3 and Noto Sans (non-Latin names) into `templates/fonts/`.
- **Inputs:** DOCX resumes and scanned PDFs (OCR). The screenshot JD path (qwen3.8-27b vision step) isn't built.
- **Outputs:** DOCX export and a file-name helper (`First-Last-Resume-Company.pdf` exists only in the concierge CLI).
- **ATS check limits:** must-have coverage checks term presence, not bullet backing. The reverse-chronological check ignores overlapping roles.
- **Judge bias:** the pairwise judge (gpt-oss-120b) is also a contestant. Human recruiter review is the ground truth.
