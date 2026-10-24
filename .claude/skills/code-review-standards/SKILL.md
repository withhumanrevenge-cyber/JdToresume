---
name: code-review-standards
description: Comprehensive code review standards and verification checklists for bugs, architecture, performance, memory efficiency, security, and test coverage.
---

# Code Review & Quality Standards

This skill provides a systematic code review framework for inspecting pull requests, proposed changes, and completed features.

## Review Process Workflow

Review every implementation systematically across 8 critical dimensions before merge approval:

```
1. Architecture & Design
2. Correctness & Bugs
3. Performance & Memory
4. Security & Safety
5. Test Coverage
6. Scalability & AWS Governance
7. Readability & Maintainability
8. Product-Specific (PII, truthfulness, scraping policy, LLM cost, claims)
```

---

## Code Review Checklist

### 1. Architecture & Design Compliance
- [ ] Does the change strictly follow clean architecture and feature boundaries?
- [ ] Are domain entities decoupled from DB models and HTTP DTOs?
- [ ] Is Dependency Injection used instead of concrete instantiation?
- [ ] Are SOLID, YAGNI, and KISS principles respected (no over-engineering)?

### 2. Correctness & Edge Cases
- [ ] Are input validations complete (Pydantic / Zod)?
- [ ] Are exception paths handled gracefully with standardized HTTP error responses?
- [ ] Are edge cases tested (null inputs, empty lists, timeout scenarios)?

### 3. Performance & Memory Efficiency
- [ ] Is memory prioritized (streaming used for large files/datasets)?
- [ ] Is cursor pagination used instead of offset pagination?
- [ ] Are SQL queries projected (no `SELECT *`) with explicit column selection?
- [ ] Are N+1 queries eliminated (`joinedload`, `selectinload`, or batch loaders)?
- [ ] Are heavy loops or batch operations handled concurrently or offloaded to workers?
- [ ] Are DOM lists virtualized and heavy client bundles lazy loaded?

### 4. Security & Safety
- [ ] Are there hardcoded secrets, tokens, or AWS credentials anywhere in the code?
- [ ] Is authorization/authentication enforced at the route and service levels?
- [ ] Are presigned S3 URLs short-lived with scoped permissions?
- [ ] Is user input sanitized to prevent SQL injection, XSS, and command injection?

### 5. Test Coverage
- [ ] Are unit tests provided for domain services and business logic?
- [ ] Are integration tests provided for database queries and API endpoints?
- [ ] Do tests mock external network boundaries (AWS, Groq via a fake `AsyncGroq` client, Stripe/Razorpay, the fetcher)?
- [ ] For prompt, schema or model changes: is the eval smoke-set before/after table attached (fabrication = 0, ATS parse = 100%)?

### 6. Scalability & AWS Governance
- [ ] Are database transactions scoped as tightly as possible?
- [ ] Are background jobs idempotent and retryable?
- [ ] Are token limits and budgeting enforced for LLM calls?

### 7. Readability & Code Cleanliness
- [ ] Is the code clear, well-typed (Python type hints, TS interfaces), and self-documenting?
- [ ] Are useless comments or dead code blocks removed?

### 8. Product-Specific (Tailor): any failure here is a blocker
- [ ] **PII:** no contact details (name, email, phone, address) in LLM requests, logs, traces, analytics events or URLs.
- [ ] **Truthfulness:** every generated bullet or skill carries `source_fact_ids`, the Verifier step runs, and no code path ships unverified output.
- [ ] **Untrusted input:** JD, web-page and upload text is delimited as data, never interpolated into system prompts, and outputs are schema-constrained.
- [ ] **Scraping policy:** no server-side fetch of client-only domains (`jd-ingestion` skill). Fetcher calls keep the SSRF guard.
- [ ] **Cost:** no new LLM call, higher effort or larger prompt without a cost note against `docs/COSTS.md`. The cached prefix stays byte-stable.
- [ ] **Metering:** generation endpoints check entitlements *before* calling the LLM, and usage is recorded atomically with the run.
- [ ] **Claims:** UI and email copy follows `ats-compliance` §5 (no "guaranteed", no universal ATS score).
