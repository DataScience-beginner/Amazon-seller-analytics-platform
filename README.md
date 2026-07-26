# SellerOS — Amazon Seller Analytics Platform

SellerOS is a SaaS-oriented Amazon seller operating system. The Phase 2 vertical slice converts dynamic
Keepa `.xlsx` exports and explicit seller-owned cost/supplier inputs into immutable product history,
explainable market scores, traceable unit economics and advisory sourcing scenarios.

## What works now

Phase 1 stories SOS-101 through SOS-303 and Phase 2 stories SOS-401 through SOS-502 are implemented:

- safe `.xlsx` staging, workbook inspection and preview;
- registered Keepa Product Finder v1 source-model detection for all 173 headers;
- seller-confirmed observation dates, monthly dataset revisions and chronology-safe latest evidence;
- versioned alias mapping with explicit ambiguity handling;
- organisation + marketplace + ASIN matching and checksum idempotency;
- transactional immutable snapshots with complete source-cell payloads, row-level errors and
  unknown-field preservation;
- deterministic Demand, Competition, Price Stability, Data Confidence and Overall Opportunity scores;
- deterministic, versioned strategy recommendations with structured evidence;
- tenant-scoped dashboard, server-filtered product portfolio and product evidence/history pages;
- responsive first-use workspace setup and import workflow;
- effective-dated product and marketplace-default cost-profile revisions with audit history;
- explicit GST-inclusive/exclusive selling-price basis with Decimal-only net revenue, output GST,
  landed cost, Amazon fees, contribution, margin, ROI and price thresholds;
- explicit fee source/date/status and formula/input/configuration trace;
- immutable supplier quotations with supplier-name-at-quote, MOQ, lead time, validity and
  quantity-price tiers;
- persisted conservative, expected and aggressive test-buy scenarios with source evidence,
  confidence, budget, supplier constraints and an honest Recommended/Blocked aggregate outcome.

Inventory/reorder planning, lifecycle pricing, cash-flow forecasting, authentication, billing,
Keepa API, Amazon SP-API and AI execution remain later-phase work. SellerOS calculations are
deterministic and AI-readable; AI does not set assumptions or execute purchasing actions.

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

Open `http://localhost:5173`. On first use, create a local organisation/marketplace, open Imports and
upload a Keepa `.xlsx`. Review the registered source-model result and mapping exceptions, confirm the
date represented by the workbook, then create that monthly dataset. The observed date is separate
from upload and processing time. Open Planning from a product to enter costs, compare supplier
quotations and request advisory test-buy scenarios. Local uploads, databases and workbooks are
ignored by Git. Never commit seller workbooks or imported business data.

The frontend uses same-origin `/api` requests. During local development, Vite proxies those requests
to `http://127.0.0.1:8000`; this also avoids private-port CORS redirects in GitHub Codespaces. Set
`VITE_API_BASE_URL` only when the frontend and API are intentionally hosted on separate origins.

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
| `POST` | `/api/v1/imports/{id}/confirm` | Confirm observation date and transactionally create a monthly dataset |
| `GET` | `/api/v1/dashboard` | Tenant-scoped executive portfolio |
| `GET` | `/api/v1/products` | Search, filter, sort and paginate products |
| `GET` | `/api/v1/products/{id}` | Latest evidence plus snapshot/strategy history |
| `POST` | `/api/v1/cost-profiles` | Create a seller-owned effective-dated cost revision |
| `GET` | `/api/v1/products/{id}/economics` | Read traced costs and unit economics |
| `GET` | `/api/v1/products/{id}/supplier-offers` | List bounded supplier quotations |
| `POST` | `/api/v1/supplier-offers` | Record an immutable quotation and price tiers |
| `POST` | `/api/v1/products/{id}/test-buy-scenarios` | Persist three advisory sourcing scenarios |

Import-history, import-detail/action, portfolio, economics and sourcing endpoints require explicit
`organisation_id` and `marketplace_id` scope.
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

## Railway founder preview

The root multi-stage Dockerfile builds the frontend and backend into one same-origin Railway image.
It runs migrations before startup, binds to Railway's assigned port, normalises Railway PostgreSQL
URLs for psycopg 3, serves React route fallbacks and requires a fail-closed preview username/password
in production. Follow [the exact Railway setup](docs/RAILWAY_DEPLOYMENT.md). This access lock is for a
controlled founder preview; final user authentication and tenant authorisation remain required before
public SaaS use.

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
- [Phase 2 economics and sourcing contracts](docs/PHASE2_CONTRACTS.md)
- [Keepa Product Finder dataset model v1](docs/KEEPA_DATASET_MODEL_V1.md)
- [Product backlog](docs/IMPLEMENTATION_BACKLOG.md)
- [Engineering guardrails](docs/ENGINEERING_GUARDRAILS.md)
- [Competitive reference research](docs/competitive/README.md)
- [AI-agent operating contract](AGENTS.md)

The root `app.py` is a read-only legacy prototype reference. It is not the supported application
entry point; run `backend/app/main.py` through Uvicorn.
