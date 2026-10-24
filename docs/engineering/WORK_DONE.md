# Work done

Everything built so far, in the order it was built, with the decisions that matter and the limits that are known.
For how the pieces fit together, see [ARCHITECTURE.md](ARCHITECTURE.md). For what's next, see
[WORK_LEFT.md](WORK_LEFT.md).

**Snapshot:**
- **Backend:** 20 API operations, 10 tables, 4 migrations; 241 automated tests (236 backend, 5 eval harness).
- **Web app:** 7 routes; unit tests, typecheck, lint and production build.
- **CI/CD:** four required CI checks on `main`, an eval workflow, and image publishing to GitHub Container Registry.

## Phase 0: planning and validation tooling

| Deliverable | Where |
|-------------|-------|
| Product spec: personas, MVP scope, pricing, success metrics | [docs/PRD.md](../PRD.md) |
| Market: competitors, market size, virality odds by market, legal and ToS risks, with cited research | [docs/MARKET.md](../MARKET.md), [docs/research/](../research/) |
| System design: pipeline, data model, API, AWS infrastructure, security, decision log | [docs/ARCHITECTURE.md](../ARCHITECTURE.md) |
| AI provider decision: Groq, gpt-oss-120b (Deep) and gpt-oss-20b (Quick) | [docs/adr/ADR-0001-llm-provider-groq.md](../adr/ADR-0001-llm-provider-groq.md) |
| Costs: AI cost per pack, infrastructure by stage, pricing, unit economics, startup budget | [docs/COSTS.md](../COSTS.md), [docs/models/unit_economics.py](../models/unit_economics.py) |
| Roadmap: validation, MVP, launch, scale; go-to-market | [docs/ROADMAP.md](../ROADMAP.md) |
| Phase 0 guides (concierge pilot, eval plan) | [docs/phase0/](../phase0/) |
| Eval harness: 12 synthetic resume × job cases with fabrication traps; deterministic, ATS and LLM-judge graders; model bake-off; cost estimate | `evals/` |
| Concierge CLI for pilot users (data stays in a gitignored folder) | `server/app/cli/concierge.py` |
| Claude Code subagents and skills adapted to this product | `.claude/` |

## Part 1: API foundation

- **What:** `create_app()` with settings from the environment, logging, the error format, request ids and health checks.
- **Files:** `server/app/main.py`, `core/config.py`, `core/logging.py`, `core/errors.py`, `core/middleware.py`, `api/health.py`
- **Decisions:**
  - One error shape everywhere: `{code, message, details}`. Validation errors list fields, never the submitted values (they may be personal).
  - Logs redact emails and phone numbers and carry the request id. Writes go through a queue, so a stalled log sink can't freeze the event loop (found and fixed with a test).
  - Request ids are handled in plain ASGI middleware, so streaming responses aren't buffered.
- **Tests:** `test_api_foundation.py`

## Part 2: database

- **What:** PostgreSQL 17 in Docker (port 5433), async SQLAlchemy, Alembic, and a readiness check (`/health/ready` answers 503 when the database is down).
- **Files:** `docker-compose.yml`, `infra/local/postgres-init.sql`, `core/db.py`, `server/migrations/`, `alembic.ini`
- **Decisions:**
  - A constraint naming convention, so migrations stay stable.
  - Services decide when to commit; repositories never do.
  - `release_connection()` is called before slow outside work (AI calls), so a connection isn't held while waiting.
- **Tests:** `test_database.py`. The suite rebuilds the schema from the real migrations every run, so migrations are tested too.

## Part 3: sign-in tokens and users

- **What:** token verification in two modes, automatic account creation, `GET /v1/me` and `DELETE /v1/me`.
  - **dev:** HS256 tokens from `python -m app.cli.dev_token`.
  - **jwks:** tokens signed by the sign-in provider, checked against its published keys (EdDSA/ES256/RS256).
- **Files:** `core/auth.py`, `features/users/*`, `cli/dev_token.py`
- **Decisions:**
  - The settings refuse dev mode in staging and production.
  - A user is created on their first request, and two simultaneous first requests are handled safely.
  - One account per email, whatever its capitalisation.
  - Deleting an account cascades to everything.
- **Tests:** `test_auth.py`, `test_users.py`

## Part 4: resume upload and the career profile

- **What:**
  - Upload a resume (PDF, TXT, MD up to 5 MB). The text is extracted locally, then parsed by the AI into a `CareerProfile`: atomic facts with ids, metrics, skills and dates.
  - Contact details are detected and stored separately.
  - The profile is versioned and editable with optimistic locking (`base_version`, 409 on conflict).
- **Files:** `features/profiles/*` (`parse.py`, `consistency.py`), `llm/schemas.py`, `llm/prompts/resume_parse.md`
- **Decisions:**
  - Contact details never reach the AI: the profile is redacted to placeholders, and every outgoing request is checked.
  - Confirmed contact details aren't overwritten by a new upload.
  - Year-only dates stay "YYYY" (the parser is told not to invent a month, and `parse.py` removes a January the resume doesn't show).
- **Tests:** `test_profiles.py`, plus the PII and parser tests in `test_llm_core.py`

## Part 5: jobs from text and links

- **What:** `POST /v1/jobs` from pasted text or a link. Links are read from public ATS feeds (Greenhouse, Lever, Ashby), then embedded schema.org data, then page text.
- **Files:** `features/jobs/*`, including `ingestion/{ats,fetch,html,reader,raw}.py`, `urls.py`, `policy.py`
- **Decisions:**
  - LinkedIn, Indeed, Naukri, Glassdoor, Monster, foundit, Instahyre and Wellfound are never fetched; the user pastes the text instead.
  - The fetcher is SSRF-safe: public addresses only, redirects checked by hand, 10 s / 3 MB limits, robots.txt respected.
  - A job read from a public link is shared: stored once and reused by every user (a unique index handles races).
  - Pasted jobs are private to the user.
- **Tests:** `test_job_reading.py`, `test_jobs_api.py`. They run offline against recorded pages and a mock network.
- **Verified live:** a Figma job (Greenhouse) and a Spotify job (Lever) were read correctly.

## Part 6: applications and streaming generation

- **What:**
  - Applications: start, list with keyset pages, and read one with its latest pack.
  - `POST /v1/applications/{id}/generate` streams the pack over Server-Sent Events. The match plan runs first; then the resume (tailor → lint + verify → revise once if needed), cover letter and outreach run in parallel.
  - Every piece is saved before it's sent, and every AI call is recorded in the `llm_calls` cost ledger.
- **Files:** `features/applications/*`, `features/generation/*`, `core/sse.py`, `llm/client.py`, `llm/ledger.py`, `llm/style/`
- **Decisions:**
  - One orchestrator (`stream_pack`) serves both the API and the eval harness.
  - A second Generate while one is running is refused with 409 (unless the running one is over 10 minutes old).
  - Clean-up is shielded from cancellation: a disconnect still closes the run and records its cost (a regression test proves this fails without the shield).
  - A keep-alive comment is sent every 15 s.
  - The AI's spend is capped per request.
- **Tests:** `test_generation.py`, `test_sse.py`, `test_llm_core.py`

## Part 7: documents and the ATS check

- **What:**
  - The resume and cover letter as PDF (Typst; classic and modern templates; fitted to the page limit) and Word.
  - Every file is read back the way an ATS would before it's sent.
  - `GET …/ats-check` returns "What the ATS sees": the extracted text and the check.
  - Download names look like `Jordan-Rivera-Resume-Figma.pdf`.
- **Files:** `features/rendering/*` (`document.py`, `typst_renderer.py`, `docx_renderer.py`, `cover_letter.py`, `ats_roundtrip.py`, `filenames.py`), `templates/*.typ`
- **Decisions:**
  - The AI only references profile entries by id; titles, companies and dates come from the profile.
  - Rendering is deterministic (system fonts ignored).
  - The Word file carries the same bullets as the PDF.
  - A failed ATS check never blocks the download; it's reported in a header and logged.
  - Files are rendered on request, not stored.
- **Tests:** `test_rendering.py`, `test_documents.py`. They include ATS-hostile Word files (contact details in a table, or in the page header) to prove the check catches them.

## Part 8: plans, metering and account export

- **What:**
  - Plans as code: Free, Sprint pass, Pro monthly, Pro quarter.
  - Per-user entitlements and a usage ledger; one pack is spent before every generate.
  - `GET /v1/me/plan`, the grant CLI, and `GET /v1/me/export` (everything about the user as JSON).
- **Files:** `features/billing/*`, `features/data_export/*`, `cli/grant.py`, migration `5d2e9b7c41a3`
- **Decisions:**
  - Free: 3 Quick packs per calendar month (UTC) plus 1 Deep pack at sign-up.
  - Paid: up to 100 packs in any 7 days (fair use).
  - A row lock stops two simultaneous presses spending the same pack (tested both ways).
  - A pack is refunded when the run ends without the resume.
  - Deleting an application never refunds packs.
  - The export excludes our internal cost figures, and a test fails if a new table isn't classified for the export.
- **Tests:** `test_account.py`

## Web app

- **What:** a Next.js 16 app covering the whole loop:
  - development sign-in;
  - profile (upload with drag and drop, contact details with field-level validation, a read-only view of what was parsed);
  - applications list and adding a job by link or pasted text (with a "paste the description instead" recovery for blocked sites);
  - live generation with per-step progress and screen-reader announcements;
  - match report, resume (real PDF preview, measured ATS summary, "What the ATS sees", Classic/Modern switch, PDF and Word downloads), cover letter and outreach with copy buttons;
  - account (plan and usage, data export, delete with confirmation).
- **Files:** `apps/web/` (structure in its README), `packages/api-types/`
- **Design:**
  - The system came from the `ui-ux-pro-max` skill: flat style, professional blue, Plus Jakarta Sans. Contrast was measured for every text pair (≥ 4.5:1) and input border (≥ 3:1) in light and dark mode.
  - Controls are 40–44 px, status is always written out, and reduced motion is respected.
  - Overrides are documented in `docs/design-system/tailor/pages/app.md`.
- **Backend additions for it:**
  - `POST /v1/dev/sign-in` (dev only).
  - Typed `pieces` in the application detail; a stored piece that no longer matches the schema is left out, never a 500.
  - `python -m app.cli.openapi`, which writes the schema the TypeScript types are generated from.
- **Verified in a browser against the real backend and real Groq:**
  - sign-in and sign-out, and contact validation;
  - resume upload and parse, and the job read from pasted text;
  - the LinkedIn refusal path;
  - a generation where outreach and the cover letter arrived but the resume hit the free tier's limit, shown honestly with the pack given back;
  - downloads and the account page;
  - no sideways scrolling at 375 px.
- **Tests:** Vitest unit tests for the stream parser, file names, placeholders and safe redirects.

## Repository, CI and CD

- **pnpm workspace:** `apps/*`, `packages/*`.
- **CI** (`.github/workflows/ci.yml`, four required checks):
  - **backend:** ruff, migrations apply and match the models, all pytest suites against real Postgres; database tests must not skip.
  - **web:** typecheck, lint, tests, build.
  - **api-contract:** the generated types must be current.
  - **api-image:** the Docker image builds, refuses dev sign-in in production, serves `/health` and renders a PDF.
- **Evals** (`evals.yml`): runs on prompt and harness changes, with hard gates when a Groq key secret is set. `run_eval --fail-on-gates` makes the gates fail CI.
- **CD** (`cd.yml`): the API image goes to `ghcr.io/<owner>/jdtoresume-api` on every merge to `main` and on `v*` tags, with provenance and an SBOM.
- **Repo plumbing:** Dependabot (uv, npm, GitHub Actions, Docker), a PR template, `.gitattributes` (LF everywhere), `.dockerignore`, and `server/Dockerfile` (non-root; defaults to production, so it fails closed without real auth settings).
- **`main` is protected:** pull requests only, all four checks green, one approval, no force pushes.

## Known limits

- **AI provider tier.** On Groq's free tier (8,000 tokens per minute on gpt-oss-120b), a Deep generation can fail
  partway with 429s. Use a Developer-tier key.
- **Evals haven't run on the real models.** The hard gates (fabrication 0, ATS parse 100%) are wired into CI, but
  the live smoke eval needs a Developer-tier key in the `GROQ_API_KEY` secret.
- **Profiles parsed before the year-only-date fix** keep their invented "Jan" until the resume is uploaded again.
- **The API image is about 1 GB** uncompressed (Typst and the PDF libraries); not optimised yet.
- **Single process.** Generation runs inside the API process; a deploy restart cuts running streams (pieces already
  finished are saved, and a run left "running" stops blocking new runs after 10 minutes, but its pack isn't refunded).
- **No license file.** The repository is public but has no LICENSE, so by default others may read it but not reuse it.
