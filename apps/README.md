# apps/

User-facing clients. Each talks only to the FastAPI API (`server/`), never to Groq or the database directly.

| Folder | What | Phase |
|--------|------|-------|
| `web/` | Next.js web app + PWA (onboarding, job intake, generation, editor, tracker, billing) | 1 |
| `extension/` | Chrome MV3 extension: "Tailor this job" on job pages | 2 |
