---
name: performance-memory-optimization
description: Guidelines for memory optimization, cursor pagination, streaming, virtualization, batch processing, Redis pipelines, and payload minimization.
---

# Performance & Memory Optimization Standards

This skill provides guidelines and patterns for minimizing memory footprints, preventing N+1 queries, optimizing data pipelines, and maintaining high API and UI throughput.

## Rule #1: Optimize Memory Before CPU

Memory pressure leads to GC pauses, high AWS infrastructure costs, and out-of-memory crashes. Always evaluate memory allocation before optimizing CPU usage.

---

## Data Pipeline & Database Performance

### 1. Cursor Pagination (Never Offset)
- **Problem**: `OFFSET 100000` forces the database to scan and discard 100,000 rows before returning results.
- **Standard**: Always use cursor pagination (keyset pagination) based on indexed fields (e.g. `WHERE id > last_seen_id ORDER BY id ASC LIMIT 50`).

### 2. Selective Column Projection
- Never write `SELECT *`.
- Select only the explicit columns required by the service DTO.
- For list endpoints, exclude heavy text, JSON, or binary fields.

### 3. N+1 Query Prevention
- Always audit queries for N+1 issues when traversing relationships.
- In SQLAlchemy / ORM, use explicit `joinedload()` or `selectinload()`.
- Use batch data loaders for GraphQL or nested REST relationships.

### 4. Batch Operations & Bulk Writes
- Batch DB inserts and updates in chunks (e.g. 500-1000 items per batch).
- Batch external API requests with `asyncio.gather` bounded by semaphores (`asyncio.Semaphore(10)`).
- Use Redis pipelines (`redis.pipeline()`) for multi-key Redis reads/writes.

### 5. Streaming Large Payloads
- Use chunked streaming (`StreamingResponse`) for large file exports, logs, or reports instead of loading full buffers into RAM.
- Use generator functions (`yield`) to process dataset rows iteratively.

---

## LLM Pipeline Performance (Tailor)

LLM calls take most of the wall-clock time and most of the cost, so optimize them first:
- **Perceived latency:** stream every writing step and render artifacts as they arrive (target: the first useful pixel within 5 s).
- **Critical path:** JobSpec → Match Analyst → (Tailor ∥ Cover Letter ∥ Outreach). Anything not needed for the resume PDF runs in parallel, after the shared prompt cache has been written.
- **Don't call the LLM for deterministic work:** keyword coverage, fit-to-page, date parsing, banned-phrase checks and the ATS round-trip are code.
- **Cache at three levels:** shared JobSpecs (DB), the prompt-cache prefix (API), and renders (S3, re-creatable).
- **Output tokens cost 5× input tokens:** keep output schemas lean (IDs instead of repeated text), and set `effort` per step instead of one global value.
- **Rendering:** Typst compiles in-process in about 100 ms. Never spawn a headless browser for PDFs.

## Frontend & Memory Performance

### 1. UI Virtualization
- Virtualize any list expected to exceed 50 items (e.g. `react-window` or `@tanstack/react-virtual`).
- Render only visible DOM nodes.

### 2. Client Memory Management
- Purge inactive page cache state upon route transitions when data is no longer needed.
- Cancel pending network subscriptions and clear timers on component unmount.
- Keep bundle size small: use dynamic imports (`next/dynamic`) for heavy libraries (e.g., chart renderers, markdown editors).
