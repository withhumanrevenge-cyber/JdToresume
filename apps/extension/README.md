# apps/extension: Chrome MV3 extension (Phase 2)

Built with WXT. Reads **only the visible job panel, only on an explicit click** (`.claude/skills/jd-ingestion` §2).
Launch set: Greenhouse, Lever, Workday, Ashby. LinkedIn / Indeed / Naukri only after counsel review, each behind a
remote per-site kill switch.

**Scaffold:** delete this README, then from `apps/` run `pnpm dlx wxt@latest init extension` (React + TS template).

Planned layout:
```
entrypoints/
  content/            per-site page readers (one module per ATS / job site) -> extension payload
  sidepanel/          match report + Generate button (UI from packages/ui)
  background.ts       auth token, API calls, kill-switch flags
```
