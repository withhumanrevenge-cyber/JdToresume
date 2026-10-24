---
name: frontend-standards
description: Next.js App Router, React Server Components, Client Components, Shadcn/UI, TailwindCSS, hook-driven architecture, and React Query standards.
---

# Frontend Standards (Next.js & React)

This skill provides guidelines and patterns for building scalable, high-performance web interfaces with Next.js App Router, TypeScript, TailwindCSS, and Shadcn/UI.

## Core Component Philosophy

- **Presentational Components**: Components should be focused strictly on layout and rendering.
- **Hook-Driven Architecture**: Extract all business logic, data fetching, and state management into custom React hooks or service functions.
- **Avoid Prop Drilling**: Use React Context or TanStack Query cache state instead of passing props down deep component trees.

---

## Server Components vs Client Components

### Default Rule: Prefer React Server Components (RSC)
- Server Components render on the server, producing zero client JS bundle overhead.
- Use RSC for data fetching, page layouts, static content, and server-side rendering.

### When to use Client Components (`"use client"`)
- Event listeners (`onClick`, `onChange`, `onSubmit`).
- State and lifecycle hooks (`useState`, `useEffect`, `useReducer`).
- Browser-only APIs (`window`, `localStorage`, `geolocation`).
- Custom interactive hooks.

---

## UI Performance & Loading UX

### 1. Skeleton Loading & Suspense
- Wrap async Server Components and data boundaries with `<Suspense fallback={<SkeletonLoader />}>`.
- Never show blank white screens during data fetching. Provide layout-preserving skeletons.

### 2. Error Boundaries
- Implement localized `error.tsx` pages and React Error Boundaries around independent page widgets so a single component failure does not crash the entire application.

### 3. Server State with TanStack React Query
- Use TanStack Query (`useQuery`, `useMutation`) for client-side data fetching, caching, automatic retry, and optimistic updates.
- Invalidate and evict query keys properly when navigating away from transient pages or mutating resources.

### 4. Code Splitting & Dynamic Imports
- Lazy load heavy client libraries or dialogs with `next/dynamic`:

```tsx
import dynamic from 'next/dynamic';

const DynamicChart = dynamic(() => import('@/features/analytics/components/Chart'), {
  loading: () => <SkeletonChart />,
  ssr: false,
});
```

---

## Tailor-Specific Patterns

### Streaming generation UI
- Consume `POST /v1/applications/{id}/generate` with `fetch()` and a `ReadableStream` reader, not `EventSource` (it can't send the `Authorization` header). Wrap it in one hook, `useGenerationStream(applicationId)`, that exposes `{ matchReport, resume, atsCheck, coverLetter, outreach, status, error }`.
- Render each artifact as soon as its event arrives, and show the requirement checklist filling in. Never show a single spinner for 25 s.
- On disconnect, reconnect with the `run_id`. The server replays finished artifacts.

### Resume preview & diff editor
- The preview is the **real rendered PDF** (pdf.js, lazy-loaded with `next/dynamic`), so what the user sees is what they download. Debounce re-renders on edit (~400 ms).
- The diff view shows base vs. tailored per bullet, with the reason ("targets: Kafka, event-driven") and accept/reject controls. Each accept or reject is a small PATCH, applied optimistically with TanStack Query.
- A "What the ATS sees" tab shows the extracted plain text from the `AtsCheck`.

### Job intake surfaces
- One `JobIntake` component accepts a URL, pasted text or 1–3 images (drag-drop, paste-from-clipboard, camera on mobile).
- **PWA Web Share Target** (Android Chrome): the manifest's `share_target` posts the shared URL or text to `/share`, which pre-fills `JobIntake`. iOS has no share target for PWAs, so offer screenshot upload there.
- The Chrome extension (`apps/extension`, WXT) reuses UI primitives from a shared package (`packages/ui`) and talks to the same API with the user's token. It must not duplicate API types: generate them from the FastAPI OpenAPI schema (`openapi-typescript`).

### Paywall & metering UX
- Show remaining free packs and scans before the user starts a run, never as a surprise error halfway through.
- Free users see the full match report and the ATS check. The paywall sits at download, cover letter or outreach (see `docs/PRD.md` pricing).

## Feature Folder Layout

Structure frontend features cleanly:

```
src/features/dashboard/
├── api/          # Query hooks and fetchers
├── components/   # Presentational & interactive components
├── hooks/        # Feature custom hooks
├── types/        # Feature TypeScript types/interfaces
└── utils/        # Feature helper utilities
```
