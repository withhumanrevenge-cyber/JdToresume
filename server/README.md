# server/: Python backend (FastAPI API + worker + LLM pipeline)

Standards: `.claude/skills/backend-standards`, `llm-pipeline-standards`, `database-standards`.
Layering per feature: `router -> service -> repository -> schemas` (architecture-standards: no deeper layering at MVP size).

```
app/
  main.py        create_app(): settings -> logging -> middleware -> error handlers -> routes
  api/           router.py (collects all routes, /v1 prefix), health.py
  core/          config, logging, errors, request-id middleware, db (engine, sessions, Base), auth (tokens), text helpers
  models.py      imports every feature's table models (for Alembic)
  llm/           Groq client, model router + prices, schemas, prompts/, style/ (linters), ledger.py (cost of every call)
  features/
    profiles/    POST /v1/profile/resume (upload -> parse), GET/PUT /v1/profile (versioned), GET/PUT /v1/profile/contact
    jobs/        POST /v1/jobs (text or link), GET /v1/jobs/{id}; ingestion/ (safe fetcher, ATS feeds, embedded data)
    generation/  stream_pack (the one pipeline), POST /v1/applications/{id}/generate (SSE), runs + artifacts
    rendering/   PDF (Typst, fit-to-page) + DOCX for resume and cover letter, ATS check on every file;
                 GET /v1/applications/{id}/files/{resume|cover-letter}.{pdf|docx}, GET .../ats-check
    applications/ POST/GET /v1/applications, GET /v1/applications/{id} (latest run + pieces)
    billing/     plans (plans.py), entitlements + usage ledger, a pack spent before every generate, GET /v1/me/plan;
                 Razorpay/Stripe webhooks next (they call BillingService.grant_plan / add_deep_credits)
    data_export/ GET /v1/me/export (DPDP/GDPR access): the one place that reads every table holding personal data
    users/       automatic sign-up, GET/DELETE /v1/me, `CurrentUser` dependency
  cli/           admin + Phase 0 tools: concierge, dev_token, grant (plans and Deep credits by email)
migrations/      Alembic: env.py + versions/ (run from the repo root; alembic.ini lives there)
tests/           pytest; fixtures/; LLM and network boundaries are faked
```
Run it: `.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000` (docs at `/docs`).
Still to come in Phase 1: `worker.py` (SQS consumer).
