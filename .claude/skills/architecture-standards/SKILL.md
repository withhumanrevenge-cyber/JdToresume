---
name: architecture-standards
description: Architecture standards, clean architecture, SOLID, YAGNI, KISS, DRY, feature boundaries, and dependency injection guidelines.
---

# Architecture Standards

This skill provides guidelines and checklists for enforcing clean architecture, domain boundaries, design patterns, and SOLID principles.

## Core Architectural Principles

### 1. SOLID
- **Single Responsibility Principle (SRP)**: Each class, module, or function must have one and only one reason to change.
- **Open/Closed Principle (OCP)**: Code entities should be open for extension, but closed for modification. Use interfaces and strategy patterns.
- **Liskov Substitution Principle (LSP)**: Subtypes must be substitutable for their base types without breaking application correctness.
- **Interface Segregation Principle (ISP)**: Prefer many client-specific interfaces over one general-purpose interface.
- **Dependency Inversion Principle (DIP)**: High-level modules must not depend on low-level modules. Both must depend on abstractions (interfaces).

### 2. Pragmatic Design Rules
- **YAGNI (You Aren't Gonna Need It)**: Do not implement functionality until it is explicitly required. Avoid building speculative abstractions.
- **KISS (Keep It Simple, Stupid)**: Choose the simplest solution that satisfies current requirements.
- **DRY (Don't Repeat Yourself)**: Eliminate duplicate domain logic, but avoid premature abstractions across unrelated domain boundaries.
- **Composition over Inheritance**: Favor object composition and delegation over class hierarchy inheritance.

---

## Clean Architecture & Modular Layout

Organize application components using feature-based modularity:

```
src/
├── features/
│   ├── authentication/
│   │   ├── domain/         # Entities, Interface definitions, Value objects
│   │   ├── application/    # Use cases, DTOs, Service interfaces
│   │   ├── infrastructure/ # Repository implementations, Database models, External APIs
│   │   └── presentation/   # Controllers, FastAPI endpoints, React components
│   └── billing/
│       └── ...
└── core/                   # Cross-cutting concerns (logging, configuration, security)
```

> **Tailor at MVP size:** each feature uses `router → service → repository → schemas` (see `backend-standards`). The full domain/application/infrastructure/presentation split above is **not** the default. Introduce it per feature only when that feature grows real domain rules that need isolating (the generation orchestrator is the likeliest candidate). Over-layering a 3-person codebase is a YAGNI violation.

### Key Architectural Patterns
- **Repository Pattern**: Decouple domain logic from data persistence access logic.
- **Dependency Injection**: Inject dependencies through constructor/parameter initialization (e.g. FastAPI `Depends()`, TS class constructors).
- **Unit of Work**: Coordinate writes across multiple repositories in a single atomic transaction.
- **DTO Separation**: Never expose ORM database models directly to API endpoints or frontend UI components. Use strict DTO mappings.
