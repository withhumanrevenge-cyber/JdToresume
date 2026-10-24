---
name: database-standards
description: PostgreSQL, pgvector, Redis, query optimization, indexing, EXPLAIN ANALYZE, cursor pagination, and connection pooling guidelines.
---

# Database & Storage Standards

This skill provides standards for PostgreSQL, pgvector index optimization, Redis caching pipelines, and relational schema management.

## PostgreSQL Standards

### 1. Query Execution & Analysis
- Run `EXPLAIN (ANALYZE, BUFFERS)` on complex queries before putting them into production.
- Eliminate sequential scans (`Seq Scan`) on large tables by adding targeted composite or partial indexes.

### 2. Indexing Best Practices
- Add indexes on foreign keys, filtering columns, and ordering columns.
- Use composite indexes matching query predicate order (`WHERE tenant_id = X AND status = Y ORDER BY created_at`).
- Use partial indexes when filtering on low-cardinality flags (e.g. `CREATE INDEX idx_pending_jobs ON jobs (created_at) WHERE status = 'PENDING'`).

### 3. Keyset / Cursor Pagination
- Always paginate using indexed keysets:

```sql
-- Good: Keyset Cursor Pagination
SELECT id, title, created_at
FROM articles
WHERE created_at < $last_seen_timestamp
ORDER BY created_at DESC
LIMIT 20;
```

### 4. Table Partitioning & Connection Pooling
- Partition high-volume tables (e.g. logs, events, metrics) by range or list (e.g. monthly time-based partitioning).
- Always use PgBouncer / AWS RDS Proxy connection pooling. Never allow direct ephemeral connection creation per request thread.

---

## JSONB Documents (Tailor)

Career profiles, JobSpecs and generated artifacts are JSONB documents validated by Pydantic schemas:
- **Versioned, append-only:** an edit inserts a new row (`version + 1`). Never update a document in place: generation runs pin the version they used.
- **List endpoints never select the document column.** Project the metadata columns only (title, kind, version, created_at).
- Add a GIN index only when a query filters *inside* the JSON. Promote frequently filtered fields (`company`, `title`, `ats_vendor`) to real columns instead.
- Store a `schema_version` inside each document so old rows can be migrated lazily on read.

## Vector Database Standards (pgvector)

> **Tailor: deferred until Phase 4 (job recommendations).** One user's career profile fits in the prompt whole, so there's no retrieval need yet. Don't add embeddings without an ADR.

- **Vector Types**: Store embeddings using `vector(1536)` (or matching model dimensions).
- **Index Types**:
  - Use **HNSW** (`hnsw`) for high query performance and accuracy on large datasets (`m = 16, ef_construction = 64`).
  - Use **IVFFlat** for memory-constrained deployments (ensure lists count is tuned: `lists = rows / 1000` for up to 1M rows).
- **Distance Metrics**: Use cosine distance (`vector_cosine_ops`), L2 distance (`vector_l2_ops`), or inner product (`vector_ip_ops`) matching model training embeddings.

---

## Redis Standards

- **Key Design**: Standardize key prefixes with namespaces (`app:tenant_id:feature:entity_id`).
- **TTL**: Always set explicit Time-To-Live (TTL) on cached items.
- **Pipelines**: Batch Redis operations with pipelines when issuing multiple commands in a single request thread.
