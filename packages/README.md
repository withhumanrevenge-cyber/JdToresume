# packages/

Shared TypeScript packages used by `apps/web` and `apps/extension` (pnpm workspace, Phase 1).

| Folder | What |
|--------|------|
| `ui/` | Shared React components (shadcn/ui-based) and design tokens, once the extension needs them (the web app keeps its own in `apps/web/src/components/ui` until then) |
| `api-types/` | TypeScript types generated from the FastAPI OpenAPI schema; never hand-written |
