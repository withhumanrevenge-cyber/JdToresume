# Work left

The backlog, in priority order, written so an engineer can pick up an item without having been here for the rest.
Read [ARCHITECTURE.md](ARCHITECTURE.md) first, then [CONTRIBUTING.md](../../CONTRIBUTING.md) for how changes land.

**Priorities:**
- **P0:** needed before a closed beta with real users.
- **P1:** beta quality.
- **P2:** public launch and growth (ROADMAP Phase 2).

**Sizes:** S ≈ 1–2 days, M ≈ 3–5 days, L ≈ 1–2 weeks.

Every item is a pull request (or a short series) into the protected `main`, with tests. Prompt, schema or model changes also need eval results (CLAUDE.md #5).

---

## P0: before a closed beta

### 1. Real sign-in (Better Auth) · L
**Why:** only the development sign-in exists (`POST /v1/dev/sign-in`, any email, no password), so nobody else can use the app.

**Scope:**
- Better Auth in `apps/web` with Google, LinkedIn and email magic link, users kept in our Postgres
  (ARCHITECTURE §12 has the reasoning).
- Better Auth's JWT/JWKS plugin issues short-lived tokens for the API.
- The API already verifies them: run with `AUTH_MODE=jwks`, `AUTH_JWKS_URL`, `AUTH_ISSUER` and `AUTH_AUDIENCE`
  (`server/app/core/auth.py`, `core/config.py`).
- Replace `apps/web/src/lib/session.ts` (localStorage dev token) with the Better Auth session; keep the module's
  interface (`useSession`, `readSession`, `clearSession`) so call sites don't change.
- With the session in a cookie the server can read, signed-in pages no longer have to render browser-only. Revisit
  `experimental.instantInsights` in `apps/web/next.config.ts` and the session gate.

**Acceptance:**
- You can sign up and sign in with Google, and with an email link.
- The API accepts those tokens and rejects expired or foreign ones (tests exist for the verifier; add web-side tests).
- `POST /v1/dev/sign-in` doesn't exist in staging (it's only mounted when `AUTH_MODE=dev`).

**Start here:** `server/app/core/auth.py` (`JwksTokenVerifier`), `apps/web/src/lib/session.ts`,
`apps/web/src/features/auth/`.

### 2. Run the evals on the real models · S (plus an account upgrade)
**Why:** the hard gates (fabrication = 0, ATS parse = 100%) are wired into CI but have never run on real Groq models.
On the free tier (8,000 tokens/minute on gpt-oss-120b) live runs fail with 429s.

**Scope:**
- Get a Developer-tier Groq key with a spend limit.
- Add it as the `GROQ_API_KEY` repository secret (Settings → Secrets and variables → Actions).
- Run `python -m evals.run_eval --smoke --fail-on-gates` locally, then the full dataset.
- Record the results in a PR.
- Compare Deep (120b) against Quick (20b). If Quick doesn't hold the gates, the free tier runs on 120b
  (PRD §7 note).

**Acceptance:** an eval report with both gates passing for the models in use, linked from `docs/phase0/`.

**Start here:** `evals/run_eval.py`, `evals/datasets/v0/`, `.github/workflows/evals.yml`.

### 3. Deploy a staging environment · L
**Why:** CD publishes the API image (`ghcr.io/<owner>/jdtoresume-api`), but nothing runs it.

**Scope:**
- **Terraform** in `infra/terraform/` (each module folder's README describes it): network, RDS PostgreSQL, the ECS
  Fargate service (ARM) behind a load balancer, Secrets Manager, S3 (item 10) and SQS (P1).
- **Deploy job:** GitHub OIDC role (no long-lived keys); push the image to ECR (or pull from GHCR); run migrations as
  a one-off task with the same image (`python -m alembic upgrade head`); then roll the service. Staging deploys
  automatically after CD; production behind a manual approval (GitHub environment with required reviewers).
- **Web app:** connect `apps/web` to Vercel (root directory `apps/web`, `NEXT_PUBLIC_API_URL` set to the staging
  API). Set `CORS_ORIGINS` on the API to the web app's origin.
- **Image environment:** the image defaults to `ENVIRONMENT=production` and refuses to start without JWKS auth
  settings. Staging needs `ENVIRONMENT=staging`, `DATABASE_URL`, `GROQ_API_KEY` and the auth variables.

**Acceptance:** a merge to `main` reaches staging without manual steps; `/health/ready` is green; the web app on
Vercel generates a pack against staging.

**Start here:** `infra/terraform/README.md`, `.github/workflows/cd.yml`, `server/Dockerfile`,
docs/ARCHITECTURE.md §13–14.

### 4. Payments · L
**Why:** paid plans exist in code (`server/app/features/billing/plans.py`) but can only be granted by hand
(`python -m app.cli.grant`).

**Scope:**
- Razorpay (India, UPI) and Stripe (or a merchant of record such as Paddle or Dodo Payments; COSTS §3 discusses the
  choice).
- Checkout from the web app's Account page.
- Webhooks at `POST /v1/webhooks/{stripe|razorpay}` with signature verification and idempotency keys. They map a
  purchase to `BillingService.grant_plan(user_id, plan_id, now)` or `add_deep_credits(user_id, 10)`.
- The billing promises in PRD §7: no card-up-front trials, one-click cancel, a reminder before every renewal, a 7-day
  refund on first purchases.
- A `subscriptions` table (provider, provider ids, status, period end) as in docs/ARCHITECTURE.md §9.

**Acceptance:**
- A test-mode purchase grants the plan.
- Replaying the same webhook changes nothing.
- A bad signature is rejected.
- Cancel works in one click.
- The export (`features/data_export`) and its table-coverage test include the new tables.

**Start here:** `server/app/features/billing/service.py`, `apps/web/src/features/account/`.

### 5. Free match scan · M
**Why:** the free hook in the funnel (PRD §4 and §7): check your current resume against a job without generating
anything.

**Scope:**
- `POST /v1/scan` with a job id: run `match_plan` on the user's base profile.
- Return the requirement checklist (shown, partly, gap) and keyword coverage.
- Fair use: 20 a day per user, enforced with a counter like the usage ledger or Valkey.
- A screen in the web app (from the job page, before Generate).
- The PRD also asks for an ATS parse check of the *current* resume file. Uploads aren't stored today, so either keep
  the original upload (item 10, with the retention setting) or run the check at upload time and store the result.

**Acceptance:** a scan result in ≤ 8 s; the 21st scan in a day is refused with a clear message; no pack is spent.

**Start here:** `server/app/features/generation/pipeline.py` (`match_plan` step), `server/app/llm/schemas.py`
(`MatchReport`), `apps/web/src/features/pack/components/match-report.tsx` (reuse the view).

### 6. Review and edit the pack · L
**Why:** the PRD's diff review: per bullet, the original fact against the tailored line, why it changed, and
accept/reject/edit. Today the pack is read-only.

**Scope:**
- **Versioned artifacts.** Add `version`, `parent_id` and `author` (ai or user) to `artifacts`, as in
  docs/ARCHITECTURE.md §9 (migration required).
- **`PATCH /v1/artifacts/{id}`** creates a new version. Edited bullets keep citing `source_fact_ids`, and the
  linters re-run on the edit.
- **UI:** a diff view in the Resume tab. `ResumeOutcome` already carries `verify` violations, lint `findings` and the
  first `draft` when it was revised, so truthfulness flags can be shown.
- **Downloads** render the newest version (today `GenerationRepository.latest_artifact`).

**Acceptance:** accepting or rejecting a bullet changes the downloaded PDF; edits never drop the fact citations;
the ATS check runs on the edited file.

**Start here:** `server/app/features/generation/models.py`, `server/app/features/rendering/service.py`,
`apps/web/src/features/pack/`.

### 7. Profile editing and gap answers · M
**Why:** users need to fix what the parser got wrong and add facts it missed (better facts mean a better pack). The
match report already asks "questions that could close a gap".

**Scope:**
- A profile editor in `apps/web/src/features/profile/` using the existing `PUT /v1/profile` (versioned, 409 on
  conflict: show "someone else changed this").
- Answering a gap question adds a fact with `source: "answer"`.
- Optional: the PRD's 3–5 enrichment questions after upload (facts without numbers are already counted:
  `ResumeImportOut.facts_without_numbers`).

**Acceptance:** an edited profile produces a new version; the next generation uses it; consistency checks
(`features/profiles/consistency.py`) still pass.

### 8. Application tracker · S
**Why:** the PRD's application list with statuses (draft, applied, interview, offer, rejected).

**Scope:**
- `PATCH /v1/applications/{id}` for status, `applied_at` and notes. The `status` column exists, with `draft` as the
  default; add the others.
- Status filters on the list.
- Deleting an application.

**Acceptance:** status changes persist and show in the list; deleting an application doesn't refund packs (already
tested on the billing side).

### 9. Rate limits on AI calls that aren't metered · M
**Why:** reading a job (`jd_extract`) and parsing a resume (`resume_parse`) call the AI without spending a pack. A
script could run up the bill.

**Scope:**
- Per-user and per-IP limits with Valkey (in the stack, not yet deployed; a Postgres counter is fine for a start)
  on `POST /v1/jobs` (text or a link that needs parsing) and `POST /v1/profile/resume`.
- Responses: 429 with `Retry-After` (the `TooManyRequestsError` exists).
- Also limit `POST /v1/dev/sign-in` if it is ever reachable outside a laptop.

**Acceptance:** tests show the limit and the reset; legitimate use (a few jobs a minute) isn't affected.

### 10. Uploads to S3, and more input types · M
**Why:** the PRD accepts resumes as PDF, DOCX or images and jobs as screenshots. Today it's PDF, TXT and MD, and
nothing is stored.

**Scope:**
- Presigned S3 uploads (`POST /v1/uploads`, 5-minute expiry, size and MIME limits).
- A retention setting for raw uploads (delete after parsing by default).
- DOCX resumes: python-docx is already a dependency.
- Image resumes and job screenshots: the `qwen/qwen3.8-27b` preview vision model is in the router and price table
  but unused (jd-ingestion skill §screenshots).

**Acceptance:** a DOCX and a phone screenshot of a job both work end to end; uploads disappear after the retention
period.

### 11. Monitoring · M
**Scope:**
- Sentry in the API and the web app (the web error boundary already logs to the console).
- Langfuse traces for every AI call (`server/app/llm/client.py` is the single place to add it).
- PostHog product events for the PRD §8 metrics (activation, time to PDF, downloads).
- Alerts on error rate, AI spend per hour (the `llm_calls` ledger has it) and readiness.

**Acceptance:** a forced error shows in Sentry with the request id; a generation shows as a trace with each step's
tokens and cost.

---

## P1: beta quality

| Item | Notes |
|------|-------|
| Background worker (SQS) | For resume parsing and bulk renders (docs/ARCHITECTURE.md §3). Keep generation streaming from the API, but make runs survive a deploy: today a restart cuts running streams, and a run left `running` isn't refunded |
| Resume a stream after reload | The web app keeps a run going across page changes, but not across a reload. Add "replay finished pieces and continue" by run id (frontend-standards, "Streaming generation UI") |
| Audit log | Exports and account deletions kept ≥ 1 year, separate from app logs (ARCHITECTURE §12, DPDP rules) |
| Legal pages and consent | Privacy policy, terms, consent at upload, DPDP notice, cookie consent for EU analytics, an age gate (MARKET §6, ROADMAP legal checklist) |
| End-to-end tests | Playwright on the core flow: sign in → upload → add job → generate (fake AI behind a test flag) → download |
| Fonts | Vendor OFL fonts under `templates/fonts/` (Inter or Source Sans 3; Noto for non-Latin names), and test a Devanagari name in the PDF |
| Smaller, ARM image | The API image is ~1 GB; use multi-stage builds and slimmer dependencies, and build `linux/arm64` for Fargate ARM |
| Landing page and PWA | A public page at `/`, a PWA manifest, and the Android share target that pre-fills a job (frontend-standards, "Job intake") |
| Visual QA | Check light mode visually (contrast was measured, not eyeballed) and run a screen-reader pass on the generate flow |
| Python lint | CI runs ruff for errors only (`F`, `E9`); add import sorting and formatting once the existing findings are fixed |
| License | The repository is public without a LICENSE (by default: readable, not reusable). Choose one |

## P2: launch and growth (ROADMAP Phase 2)

| Item | Notes |
|------|-------|
| Chrome extension (WXT) | `apps/extension/README.md`. Reads the job page the user is on (Greenhouse, Lever, Workday, Ashby first; LinkedIn, Indeed and Naukri only after counsel review). Move shared UI to `packages/ui` then |
| Share card and referrals | A match card with no personal data, sized for LinkedIn, Instagram and WhatsApp; the referral program (+3 Quick packs each, +1 Deep for the referrer) with fraud checks. Packs come from the billing ledger |
| Editor copilot and gap interviewer | Agentic steps on top of item 6, each with eval cases |
| "Tailor this job" links | `…/j?u=<job url>` for job-alert channels and creators |
| Free tools for SEO | "ATS resume checker" and "keyword scanner" built on the match scan and the ATS check |

---

## Known issues

- **Profiles parsed before the year-only-date fix** still show an invented "Jan YYYY" until the resume is uploaded again.
- **Free-tier Groq keys** make Deep generations fail partway (429). The app handles it (pieces kept, pack refunded
  when the resume is missing), but use a Developer-tier key.
- **The Windows machine this was built on blocks uv's venv launcher.** CLAUDE.md has the workaround; on macOS and
  Linux, plain `uv sync` and `uv run` work.
- **Running pnpm through corepack.** If `pnpm` isn't on your PATH, call `corepack pnpm …`; the root `package.json`
  pins the version.
