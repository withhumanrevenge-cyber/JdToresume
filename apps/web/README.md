# apps/web: the Tailor web app

Next.js 16 (App Router, Turbopack, Cache Components), TypeScript, Tailwind v4, shadcn/ui (Radix), TanStack Query.
Standards: `.claude/skills/frontend-standards`, `ui-ux-pro-max`. Design tokens and rules:
`docs/design-system/tailor/MASTER.md` plus `pages/app.md` (what this app does differently).

## Run it

From the repo root, with the API on port 8000 (see the root `CLAUDE.md`):

```bash
corepack pnpm install
corepack pnpm dev:web
```

Open http://localhost:3000 and sign in with any email (development sign-in: the API's `POST /v1/dev/sign-in`,
which only exists with `AUTH_MODE=dev`). Settings: `.env.example` (copy to `.env.local`).

Checks: `corepack pnpm --filter web typecheck`, `... lint`, `... test`, `... build`.
After any API change: `.venv/Scripts/python.exe -m app.cli.openapi packages/api-types/openapi.json`, then
`corepack pnpm api-types`, so the types the app is checked against match the API.

## Layout

```
src/
  app/                      routes
    sign-in/                development sign-in
    (app)/                  signed-in pages: session gate + header (layout.tsx), error boundary
      applications/         list · new (job intake) · [id] (generate, match, resume, cover letter, outreach)
      profile/              resume upload, contact details, what we read
      account/              plan and usage, data export, delete account
  features/<feature>/       api.ts (TanStack Query hooks) + components/
    auth/                   dev sign-in, session gate
    applications/           list, job intake, the application screen
    generate/               the generate stream (generation-runs.ts, lib/sse.ts), mode choice, progress
    pack/                   match report, resume (PDF preview, ATS check, downloads), cover letter, outreach
    profile/ billing/ account/
  components/               app shell, page header, query error; ui/ = shadcn primitives (adjusted for 40 px+ targets
                            and the contrast fixes in pages/app.md)
  lib/                      api client (typed by @tailor/api-types), session, file downloads, formatting, placeholders
```

## Decisions worth knowing

- **Types come from the API.** `@tailor/api-types` is generated from FastAPI's OpenAPI schema; nothing is hand-typed.
- **Signed-in pages render in the browser.** The dev session lives in localStorage, so the server can't render them.
  That's why `next.config.ts` makes instant-navigation checks opt-in. Better Auth (cookies) changes this.
- **The generate stream outlives the page.** It's read with `fetch` (EventSource can't send the token) and kept in
  `features/generate/generation-runs.ts`, so going to another page doesn't cancel the run on the server.
- **What you preview is what you download.** The resume preview is the rendered PDF from the API, and the ATS panel
  shows the measured round-trip check, never a made-up score.
- **Contact details never reach the AI.** Text the AI wrote has placeholders; `lib/placeholders.ts` fills them in for
  display and copying, the same way the server does for files.
