# Contributing

How to set up, how changes reach `main`, and the conventions the code follows. The architecture is in
[docs/engineering/ARCHITECTURE.md](docs/engineering/ARCHITECTURE.md); the backlog is in
[docs/engineering/WORK_LEFT.md](docs/engineering/WORK_LEFT.md).

## Setup

You need:
- **Python 3.14** (pinned in `.python-version`) and [uv](https://docs.astral.sh/uv/).
- **Docker**, for PostgreSQL 17.
- **Node 24**; pnpm comes through corepack, at the version pinned in `package.json`.
- **A Groq API key**, only for things that call the AI; tests never do.

```bash
uv sync
```

```bash
docker compose up -d db
```

```bash
uv run python -m alembic upgrade head
```

```bash
corepack pnpm install
```

Copy `.env.example` to `.env` (gitignored) and set `GROQ_API_KEY` if you'll generate packs. Copy
`apps/web/.env.example` to `apps/web/.env.local` if the API isn't on `http://localhost:8000`.

**Windows with Application Control:** uv's venv launcher may be blocked. Create the venv with `py -m venv .venv`,
install with `uv sync --python .venv/Scripts/python.exe`, and run Python as `.venv/Scripts/python.exe -m …` instead
of `uv run python -m …` (see CLAUDE.md).

## Everyday commands

| What | Command |
|------|---------|
| API with reload, docs at http://localhost:8000/docs | `uv run python -m uvicorn app.main:app --reload --port 8000` |
| Web app at http://localhost:3000 | `corepack pnpm dev:web` |
| Backend tests (needs the database running) | `uv run python -m pytest -q` |
| Python lint (what CI runs) | `uvx ruff@0.17.2 check --select F,E9 --line-length 120 server evals` |
| Web checks | `corepack pnpm --filter web typecheck`, `… lint`, `… test`, `… build` |
| New migration | `uv run python -m alembic revision --autogenerate -m "what changed"`, then review it |
| Migrations match the models | `uv run python -m alembic check` |
| Regenerate the web app's API types | `uv run python -m app.cli.openapi packages/api-types/openapi.json`, then `corepack pnpm api-types` |
| A dev sign-in token for curl | `uv run python -m app.cli.dev_token --email you@example.com` |
| Give a user a plan or Deep credits | `uv run python -m app.cli.grant --email you@example.com --plan sprint` |
| Eval cost estimate (no API calls) | `uv run python -m evals.run_eval --estimate` |
| Eval smoke run with hard gates (Developer-tier key) | `uv run python -m evals.run_eval --smoke --fail-on-gates` |
| Build the API image | `docker build -f server/Dockerfile -t tailor-api .` |

## How changes reach `main`

`main` is protected. Nobody pushes to it directly, including admins in normal work.

1. **Branch** from an up-to-date `main`: `feat/<short-name>`, `fix/<short-name>` or `chore/<short-name>`.
2. **Commit** in small, readable steps. Messages say what changed and why, in the imperative ("Add the scan
   endpoint"), not "updates".
3. **Open a pull request** and fill in the template's checklist.
4. **CI must pass:** four required checks run on every pull request.
   - **backend:** ruff; migrations apply and `alembic check` is clean; every pytest suite against a real Postgres
     (database tests fail rather than skip in CI).
   - **web:** typecheck, lint, Vitest, production build.
   - **api-contract:** `packages/api-types` must match what the API generates. If it fails, run the two
     "regenerate" commands above and commit.
   - **api-image:** the API image builds, refuses dev sign-in in production, serves `/health` and renders a PDF.

   Changes to prompts, schemas, model routing or the eval harness also run the **Evals** workflow (live gates run
   when the `GROQ_API_KEY` secret is set).
5. **One approving review** is required. A new push dismisses earlier approvals, and every review conversation
   must be resolved.
6. **Merge** with "Squash and merge" once the branch is up to date with `main`, then delete the branch.
7. **CD** runs on the merge: the API image is published to `ghcr.io/<owner>/jdtoresume-api` (tags `sha-<commit>`
   and `latest`).

**The rules on `main`:**
- Pull requests only.
- The four CI checks pass on the latest commit, and the branch is up to date.
- One approval; stale approvals are dismissed and conversations must be resolved.
- No force pushes, no deletion.

Repository admins can bypass the rules for an emergency; say why in the PR.

## Conventions

**Backend:**
- **Feature layout:** `router → service → repository`, with `schemas.py` for the API and `models.py` for tables
  (classes named `…Row`). Routers parse and respond; services hold the rules and commit; repositories only query.
- **Errors:** raise the domain errors in `server/app/core/errors.py`, never `HTTPException`. Every error reaches the
  client as `{code, message, details}`.
- **Signed-in routes** take `user: CurrentUser` and filter every query by that user. Never read the token or the
  `users` table yourself.
- **AI calls** go only through `GroqLLM.run_step()` in `server/app/llm/client.py`. Contact details never go in a
  prompt. Check Groq's docs and the installed SDK for parameters; don't write SDK calls from memory.
- **Database changes** come with an Alembic migration in the same PR. New tables that hold personal data must be
  added to the account export (`features/data_export/service.py`); a test fails until you decide.
- **Tests:** behaviour tests through the API with a real database and the fake Groq (`server/tests/fakes.py`).
  Tests never call the real AI or the network.

**Web:**
- **Feature folders:** `src/features/<feature>/api.ts` (TanStack Query hooks) plus `components/`. Pages in
  `src/app/` stay thin.
- **API calls** go through the typed client in `src/lib/api/client.ts`. Never hand-write API types; regenerate them.
- **Design:** tokens and rules in `docs/design-system/tailor/`. Use semantic colour tokens, never raw hex. Controls
  are at least 40 px. Status is written out, not only coloured.
- **Next.js 16** differs from older versions: read the guide in `node_modules/next/dist/docs/` before using an API
  you haven't used here.

**Product rules** (CLAUDE.md non-negotiables): never fabricate; contact details never reach the AI; "ATS-safe" is
measured, never claimed; no server-side scraping of LinkedIn, Indeed, Naukri or other client-only sites; prompt,
schema or model changes ship with eval results (fabrication 0, ATS parse 100%).

## Secrets

- Local secrets live only in `.env` (gitignored). `.env.example` documents the variables with no values.
- CI uses the `GROQ_API_KEY` repository secret (optional) and the automatic `GITHUB_TOKEN`.
- Never commit keys, tokens, real users' data (`concierge/` is gitignored) or production database dumps. If a secret
  is committed by mistake, rotate it first, then remove it.
