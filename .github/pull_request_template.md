## What and why

<!-- One or two sentences: what this changes and why. Link the item in docs/engineering/WORK_LEFT.md if there is one. -->

## How it was checked

<!-- Tests added or changed, and anything you ran by hand (e.g. "generated a pack in the web app"). -->

## Checklist

- [ ] Tests cover the change (`.venv/Scripts/python.exe -m pytest -q`, `corepack pnpm --filter web test`)
- [ ] API changed? Types regenerated and committed (`python -m app.cli.openapi packages/api-types/openapi.json`, `pnpm api-types`)
- [ ] Database changed? A migration is included and `alembic check` is clean
- [ ] Prompt, schema or model changed? Eval results are in this PR: fabrication 0, ATS parse 100% (CLAUDE.md #5)
- [ ] No contact details reach the LLM, nothing is invented, no server-side scraping of client-only sites (CLAUDE.md #1, #2, #4)
- [ ] Docs updated if behaviour changed (`docs/engineering/`, READMEs)
