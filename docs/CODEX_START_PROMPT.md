# Historical Codex Start Prompt — SellerOS Phase 0

> **Archived:** Phase 0 is complete. This file is retained as implementation history and must not be
> treated as the current task. AI agents must begin with `AGENTS.md` and `docs/STATUS.md`.

Copy the prompt below into Codex while the repository `DataScience-beginner/Amazon-seller-analytics-platform` is selected.

---

You are the technical specialist responsible for implementing SellerOS, an Amazon Seller Operating System that will become a multi-tenant SaaS product.

## Business context

SellerOS must help an Amazon seller convert monthly Keepa Excel exports and seller-entered business data into decisions about:

- which products to test, grow, monitor, clear or avoid;
- true profitability and break-even price;
- sourcing quantities and working capital;
- reorder timing;
- product lifecycle and markdown strategy;
- quarterly, half-yearly and annual cash-flow planning.

The business objective is to maximise cash conversion and annual contribution profit while reducing dead inventory, price erosion and avoidable working-capital risk.

Keepa Excel exports are dynamic. Columns may be missing, renamed or newly added. The system must map known fields through aliases, preserve unknown fields and never depend on fixed column positions.

## Read first

Before editing code, read these repository documents completely:

1. `docs/PRODUCT_VISION.md`
2. `docs/IMPLEMENTATION_BACKLOG.md`
3. `docs/ENGINEERING_GUARDRAILS.md`

Treat those documents as the product and engineering contract.

## Current task

Implement **Phase 0 only**, specifically stories **SOS-001** and **SOS-002** from `docs/IMPLEMENTATION_BACKLOG.md`.

Do not attempt to implement all future epics in this task.

## Required outcomes

### 1. Inspect and preserve useful prototype behaviour

- Inspect the current repository and identify useful behaviour in the existing prototype.
- Preserve the business concepts where appropriate, but do not keep a monolithic single-file architecture.
- Document any prototype limitations discovered.

### 2. Create a modular monolith

Use this technical direction unless the repository already contains a demonstrably better compatible structure:

- Backend: Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2.
- Frontend: React, TypeScript, Vite.
- Local database: SQLite.
- Production-ready database compatibility: PostgreSQL.
- Tests: pytest for backend, Vitest for frontend.
- Linting/type quality: Ruff plus a Python type checker; ESLint plus TypeScript strict mode.

Suggested high-level folders:

```text
backend/
  app/
    api/
    core/
    domain/
    models/
    repositories/
    services/
  alembic/
  tests/
frontend/
  src/
    api/
    components/
    features/
    pages/
    types/
docs/
```

The exact folder structure may be improved, but explain material deviations.

### 3. Define the canonical data model

Implement initial database models and migrations for:

- Organisation
- User
- Marketplace
- ImportBatch
- ImportColumn
- ImportRowError
- Product
- ProductSnapshot
- RawAttribute
- ScoreResult
- StrategyRecommendation
- CostProfile
- Supplier
- SupplierOffer
- InventoryPosition
- ForecastScenario
- PricingPlan
- AuditEvent

Important rules:

- Product identity must be unique by organisation, marketplace and ASIN.
- ProductSnapshot must be immutable by design/convention.
- Unknown Keepa values must be preservable through RawAttribute or an equivalent JSON-capable design.
- Seller-entered business data must be separated from imported market data.
- Money fields must use Decimal-compatible database types and explicit currency codes.
- Timestamps must be timezone-aware UTC.
- Add practical indexes and constraints.

It is acceptable for some future-facing entities to begin as minimal schemas, but relationships, ownership and intended purpose must be correct.

### 4. Application foundation

Implement:

- environment-based configuration;
- `.env.example` with placeholders only;
- database session management;
- Alembic migration setup;
- `/api/v1/health` or equivalent health endpoint;
- structured application startup;
- basic exception handling with safe error responses;
- CORS configuration through environment settings;
- a minimal responsive frontend shell with navigation placeholders for Dashboard, Products, Planning and Imports;
- API client foundation in the frontend;
- clear loading/error handling for the health check.

### 5. Developer experience

Provide:

- root README with exact mobile/browser-friendly setup instructions;
- backend and frontend start commands;
- database migration commands;
- test, lint and type-check commands;
- Docker Compose for local PostgreSQL if reasonable, while preserving SQLite as the simplest local default;
- sample configuration without secrets;
- a CI workflow that runs the agreed quality checks.

### 6. Testing

At minimum, add tests that verify:

- the health endpoint;
- database models can be migrated/created;
- the product uniqueness constraint;
- seller-entered cost data is structurally separate from snapshots;
- the frontend production build succeeds;
- one basic frontend shell test.

Use synthetic fixtures only. Do not commit or embed the user's Keepa workbook or private product data.

## Guardrails

- Do not introduce microservices.
- Do not implement authentication, billing, Keepa API, SP-API or AI in this task.
- Do not add an opaque scoring formula yet.
- Do not put business logic in React components or FastAPI route handlers.
- Do not use floating point for money.
- Do not hard-code organisation IDs, currencies or marketplace assumptions.
- Do not delete useful prototype files without explaining the migration path.
- Do not commit database files, uploads, secrets, node modules, virtual environments or workbook data.
- Do not claim tests passed unless you actually ran them.

## Work method

1. Inspect the repository and report the current state.
2. Write a concise implementation plan.
3. Implement SOS-001 and SOS-002 in focused steps.
4. Run formatting, linting, type checks, tests and production builds.
5. Fix failures that are caused by the implementation.
6. Update documentation.
7. Commit all intended changes with focused commit messages.
8. At the end, report:
   - files/architecture created;
   - migrations/models added;
   - commands run and their results;
   - any assumptions;
   - remaining work for Phase 1;
   - commit SHA(s).

## Definition of success

The task is successful when a new developer can clone the repository, configure it from `.env.example`, create the database, start backend and frontend, open the responsive shell, call the health endpoint, run all quality checks and understand the canonical SellerOS domain model.

---
