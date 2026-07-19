# SellerOS — Amazon Seller Analytics Platform

SellerOS is a SaaS-oriented Amazon seller operating system. The Phase 1 vertical slice converts dynamic
Keepa `.xlsx` exports into immutable product history, explainable market scores, advisory strategy
recommendations and a responsive portfolio experience.

## What works now

Phase 1 implements backlog stories SOS-101 through SOS-303:

- safe `.xlsx` staging, workbook inspection and preview;
- versioned alias mapping with explicit ambiguity handling;
- organisation + marketplace + ASIN matching and checksum idempotency;
- transactional immutable snapshots with row-level errors and unknown-field preservation;
- deterministic Demand, Competition, Price Stability, Data Confidence and Overall Opportunity scores;
- deterministic, versioned strategy recommendations with structured evidence;
- tenant-scoped dashboard, server-filtered product portfolio and product evidence/history pages;
- responsive first-use workspace setup and import workflow.

Seller costs, profitability, sourcing, inventory planning, authentication, billing, Keepa API,
Amazon SP-API and AI execution remain later-phase work. The system is AI-readable and auditable, but
its calculations do not depend on AI.

## Prerequisites

- Python 3.12+
- Node.js 22+
- npm 10+

## First-time setup

Copy the local configuration. The sample contains no credentials:

```bash
cp .env.example .env
```

SQLite is the default local database. Install and migrate the backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload
```

In a second terminal, install and start the frontend:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. On first use, create a local organisation/marketplace, open Imports,
upload a Keepa `.xlsx`, review the detected mapping, then confirm it. Local uploads and databases are
ignored by Git. Never commit seller workbooks or imported business data.

Health and interactive API documentation:

- `http://localhost:8000/api/v1/health`
- `http://localhost:8000/docs`

## Core API surface

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Application and database health |
| `GET`, `POST` | `/api/v1/workspaces` | Local-only first-use workspace selection/bootstrap |
| `GET`, `POST` | `/api/v1/imports` | List or upload tenant-scoped imports |
| `GET` | `/api/v1/imports/{id}` | Mapping preview, status and summary |
| `PUT` | `/api/v1/imports/{id}/mapping` | Store one-based source-column decisions |
| `POST` | `/api/v1/imports/{id}/confirm` | Transactionally create snapshots, scores and recommendations |
| `GET` | `/api/v1/dashboard` | Tenant-scoped executive portfolio |
| `GET` | `/api/v1/products` | Search, filter, sort and paginate products |
| `GET` | `/api/v1/products/{id}` | Latest evidence plus snapshot/strategy history |

Import-history, import-detail/action and portfolio endpoints require explicit `organisation_id` and
`marketplace_id` scope.
Authentication is intentionally not implemented yet, so this build must not be exposed publicly.

## Configuration

`.env.example` documents the database, CORS, upload location, archive/worksheet limits and local
workspace-bootstrap switch. `ALLOW_UNAUTHENTICATED_WORKSPACE_BOOTSTRAP` must be `false` in any shared
environment.

Optional PostgreSQL for local compatibility testing:

```bash
docker compose up -d postgres
```

Then set `DATABASE_URL` to the PostgreSQL SQLAlchemy URL and run `alembic upgrade head`.

## Quality checks

Backend:

```bash
cd backend
ruff format --check .
ruff check .
mypy app tests
pytest
```

Frontend:

```bash
cd frontend
npm run lint
npm run format
npm run typecheck
npm test
npm run build
```

## Migrations

Apply all migrations:

```bash
cd backend
alembic upgrade head
```

Create a reviewed migration after an intentional model change:

```bash
alembic revision --autogenerate -m "describe change"
```

Always inspect generated SQL and run the upgrade/downgrade test before committing it.

## Project contracts

- [Current implementation status](docs/STATUS.md)
- [Architecture and invariants](docs/ARCHITECTURE.md)
- [Phase 1 API and decision contracts](docs/PHASE1_CONTRACTS.md)
- [Product backlog](docs/IMPLEMENTATION_BACKLOG.md)
- [Engineering guardrails](docs/ENGINEERING_GUARDRAILS.md)
- [Competitive reference research](docs/competitive/README.md)
- [AI-agent operating contract](AGENTS.md)

The root `app.py` is a read-only legacy prototype reference. It is not the supported application
entry point; run `backend/app/main.py` through Uvicorn.
