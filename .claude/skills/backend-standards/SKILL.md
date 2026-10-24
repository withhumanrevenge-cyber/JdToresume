---
name: backend-standards
description: FastAPI backend standards, async programming, Pydantic validation, dependency injection, service layers, DTO separation, and background tasks.
---

# Backend Standards (FastAPI & Python)

This skill provides standards, structure, and best practices for building async FastAPI backends.

## Architectural Layers

Every backend feature must be separated into clean layers:

1. **Router Layer (`routers/`)**: Handles HTTP requests, path/query parameters, status codes, and delegates to service layer. No database logic here.
2. **Service Layer (`services/`)**: Implements core business logic, orchestrates transactions, calls repositories and external APIs.
3. **Repository Layer (`repositories/`)**: Handles direct database operations, query construction, and data persistence.
4. **Schemas / DTOs (`schemas/`)**: Pydantic models for request body validation and response serialization.
5. **Database Models (`models/`)**: SQLAlchemy / ORM entities.

---

## FastAPI Best Practices

### 1. Async-First Architecture
- Define path operations with `async def`.
- Ensure all IO calls (database queries, HTTP clients, Redis calls) use non-blocking `await`.
- Use `httpx.AsyncClient` for outbound HTTP requests (never blocking `requests`).

### 2. Pydantic Validation & DTOs
- Use Pydantic v2 schemas for all inputs and outputs.
- Never pass database ORM models directly in API responses.
- Explicitly define `response_model` on routers.

```python
# Good: Separate DTOs
class UserCreateDTO(BaseModel):
    email: EmailStr
    name: str

class UserResponseDTO(BaseModel):
    id: UUID
    email: EmailStr
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### 3. Dependency Injection
- Use FastAPI `Depends()` for database sessions, services, and authentication contexts.

```python
@router.get("/users/{user_id}", response_model=UserResponseDTO)
async def get_user(
    user_id: UUID,
    service: UserService = Depends(get_user_service),
):
    return await service.get_user_by_id(user_id)
```

### 4. Exception Handling & OpenAPI Specs
- Raise custom domain exceptions in services (e.g. `UserNotFoundException`).
- Handle domain exceptions globally with custom FastAPI exception handlers to return standard JSON error schemas (`{ "code": "...", "message": "...", "details": ... }`).
- Fully document status codes (`200`, `201`, `400`, `401`, `404`, `422`, `500`) for OpenAPI clarity.

### 5. Background Tasks & Offloading
- Offload long-running operations (>500ms) to background workers using SQS / Celery / Redis tasks.
- For lightweight async tasks, use FastAPI `BackgroundTasks`.

### 6. Text Normalization
- Store user-entered text with the casing the user typed: it's display data.
- Compare, dedupe and constrain on `lower(...)`. On the Python side of any such comparison, use one shared helper (`server/app/core/text.py::normalize_key()`) so the DB and the app agree byte-for-byte on whitespace and casing.
- Any table with a user-entered natural key (e.g. `users.email`) needs `CREATE UNIQUE INDEX ... (lower(col))`. A check-then-insert without that index is a race, not a lookup.
- Add a separate `*_normalized` column only for normalization lossier than lower + whitespace-collapse (e.g. company names with legal suffixes stripped, `Acme Pvt. Ltd.` → `acme`, used to group jobs by company).
- Enum-like values (`application_status`, `artifact_kind`, `job_source`, `plan`) are catalogue codes, not user text: fixed casing, validated against an enum, never normalized.

### 7. Streaming endpoints (SSE)
- The generation endpoint (`POST /v1/applications/{id}/generate`) streams Server-Sent Events: `event: <artifact_kind>` + `data: <json>`. Send a heartbeat comment every 15 s so proxies and the ALB don't drop idle streams (ALB idle timeout ≥ 120 s).
- **Never hold a DB session open across an LLM call.** Open short sessions to checkpoint each step's output, then release them.
- Every streamed run is resumable: the client reconnects with `run_id`, the server replays finished artifacts from Postgres and then continues.

### 8. LLM calls
- Feature code never imports `groq`. Call `GroqLLM.run_step(...)` from `server/app/llm/`, following the `llm-pipeline-standards` skill (schemas, router, caching, PII placeholders, budget guard, cost ledger).
- Treat LLM steps like any slow external dependency: timeouts, typed errors, idempotent retries, and mock them at the boundary in tests.

### 9. Privacy by default
- Contact details live only in `contact_details`. Services that build LLM requests receive the placeholder-redacted profile, never the raw contact row.
- Log through `structlog` with the redaction processor (email and phone patterns). Never log request bodies of upload, profile or generation endpoints.
