# Tailor (working name): AI job-application copilot

A user uploads their resume once. For any job (URL, pasted text, screenshot, or the browser extension), Tailor produces in seconds a tailored, truthful, ATS-safe resume (PDF/DOCX), a cover letter, and outreach messages (recruiter email, LinkedIn note, referral ask, follow-up).

## Start here
- `docs/PRD.md`: what we're building, for whom, and the scope per phase
- `docs/ARCHITECTURE.md`: pipeline, data model, API, infra, decision log (§17)
- `docs/COSTS.md`: LLM cost per pack, infra by stage, pricing, unit economics, startup budget (numbers reproduced by `docs/models/unit_economics.py`)
- `docs/MARKET.md`: competitors, market size, virality odds, pricing benchmarks, legal and ToS risks (full cited research in `docs/research/`)
- `docs/ROADMAP.md`: phases from validation to launch to scale; GTM; risks
- `docs/adr/`: architecture decision records (add one when you change a §17 decision)

## Non-negotiables
1. **Never fabricate.** Every generated bullet or skill cites `source_fact_ids` and passes the Verifier. Gaps get asked about or surfaced, never invented.
2. **Contact details never go to the LLM.** Use placeholders, restored at render time.
3. **"ATS-safe" is measured** (round-trip check on every render), never claimed with made-up scores.
4. **No server-side scraping** of LinkedIn, Indeed, Naukri or other client-only domains (`jd-ingestion` skill).
5. **Prompt, schema or model changes ship with eval results.** Fabrication = 0 and ATS parse = 100% are hard gates.

## Stack
Next.js (App Router, TS, Tailwind, shadcn/ui, TanStack Query) · Chrome MV3 extension (WXT) · FastAPI (async, Pydantic v2, SQLAlchemy 2 async, Alembic) · PostgreSQL (RDS) · Valkey · S3 · SQS · Typst (PDF) + python-docx · Groq API (gpt-oss-120b Deep, gpt-oss-20b Quick, qwen3.8-27b preview for vision; ADR-0001) · AWS ECS Fargate (ARM) · Vercel · Terraform · GitHub Actions · Sentry · Langfuse · PostHog.

## Repo layout
`apps/web`, `apps/extension`, `packages/{ui,api-types}`, `server/` (app/core, app/llm, app/features/*, app/cli, migrations, tests), `templates/` (Typst + fonts), `evals/`, `infra/terraform/`, `.github/workflows/`, `docs/`. The annotated tree with build status is in `README.md`. Every unbuilt folder has a README saying what lands there and when. Read it before adding code.

## How we work with Claude Code
- **Subagents** (`.claude/agents/`): `architect` (plan first, read-only) → `engineer` (implement + tests) → `reviewer` (gate, read-only). `prompt-engineer` owns prompts and evals. `resume-auditor` critiques generated output like a recruiter plus an ATS.
- **Skills** (`.claude/skills/`):
  - Engineering: `backend-standards`, `frontend-standards`, `database-standards`, `aws-standards`, `architecture-standards`, `performance-memory-optimization`, `code-review-standards`.
  - Product domain: `llm-pipeline-standards`, `resume-tailoring`, `ats-compliance`, `jd-ingestion`.
  - Design and brand: `ui-ux-pro-max`, `ui-styling`, `design-system`, `brand`, `design`, `banner-design`, `slides`.
- LLM code goes through `server/app/llm/client.py` (the `groq` SDK). Check Groq's docs and the installed SDK for parameters; never write SDK calls from memory. The `claude-api` skill doesn't apply (the provider is Groq).
- `SUPER/` (local only, gitignored: its redistribution licensing is unclear) holds the original, unmodified skill collection these were adapted from. The live copies are under `.claude/`.
- Changes reach `main` only through pull requests with green CI (backend, web, api-contract, api-image) and one review: see `CONTRIBUTING.md`. The engineering handover docs are in `docs/engineering/` (as-built architecture, work done, work left).

## Commands
- **Windows Application Control blocks uv's venv launcher.** Create the venv with `py -m venv .venv`, then install with `uv sync --python .venv/Scripts/python.exe`. Run everything as `.venv/Scripts/python.exe ...`; never use `uv run`.
- Database (local): `docker compose up -d db` (Postgres 17 on port 5433), then `.venv/Scripts/python.exe -m alembic upgrade head`
- Tests: `.venv/Scripts/python.exe -m pytest -q` (database tests use `tailor_test` and skip if Docker isn't running)
- API (local): `.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000`, docs at http://localhost:8000/docs. Settings: `.env.example`
- Dev sign-in token (local only): `.venv/Scripts/python.exe -m app.cli.dev_token --email you@example.com`, then send `Authorization: Bearer <token>`
- Give a user a plan or Deep credits (no payment provider yet): `.venv/Scripts/python.exe -m app.cli.grant --email you@example.com --plan sprint` (or `--deep-credits 10`)
- Protected routes take `user: CurrentUser` (`app.features.users.dependencies`). Never read the token or `users` table yourself
- Eval cost estimate (no API calls): `.venv/Scripts/python.exe -m evals.run_eval --estimate`
- Eval bake-off (needs `GROQ_API_KEY`, Developer tier): `.venv/Scripts/python.exe -m evals.run_eval --smoke`
- Unit economics: `.venv/Scripts/python.exe docs/models/unit_economics.py`
- Web app (needs the API on :8000): `corepack pnpm install`, then `corepack pnpm dev:web`, open http://localhost:3000. Checks: `corepack pnpm --filter web typecheck` / `lint` / `test` / `build`
- After an API change, regenerate the web app's types: `.venv/Scripts/python.exe -m app.cli.openapi packages/api-types/openapi.json`, then `corepack pnpm api-types`
- Later: `docker compose up` (local stack)
