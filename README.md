# SellerOS — Amazon Seller Analytics Platform

SellerOS is a SaaS-ready Amazon seller operating system. It will convert dynamic monthly Keepa exports and seller-entered business data into explainable portfolio, sourcing, pricing and cash-flow decisions.

## Phase 0 scope

This repository now contains a modular monolith foundation for backlog stories SOS-001 and SOS-002:

- FastAPI backend with versioned `/api/v1` routes.
- SQLAlchemy 2.x canonical domain model.
- Alembic migration setup.
- Environment-backed settings.
- React + TypeScript + Vite frontend shell.
- Backend and frontend tests and quality tooling.

The original `app.py` prototype remains for reference while Phase 1 migrates useful Keepa import and dashboard behaviour into the modular architecture.

## Prerequisites

- Python 3.12+
- Node.js 22+
- npm 10+

## Configuration

Copy the sample environment file and adjust values as needed:

```bash
cp .env.example .env
```

SQLite is the default local database:

```env
DATABASE_URL=sqlite:///./selleros.db
```

Optional local PostgreSQL is available:

```bash
docker compose up -d postgres
```

Then set `DATABASE_URL` to a PostgreSQL SQLAlchemy URL.

## Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/api/v1/health
```

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

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

## Database migrations

Create/update the SQLite database:

```bash
cd backend
alembic upgrade head
```

Create a future migration after model changes:

```bash
cd backend
alembic revision --autogenerate -m "describe change"
```

## Canonical domain model

See `docs/ARCHITECTURE.md` for the Phase 0 architecture, prototype limitations and domain model principles.

## Product reference research

See [`docs/competitive/README.md`](docs/competitive/README.md) for current Helium 10, Amazon Seller
Central and Jungle Scout walkthroughs, a feature matrix, and the resulting SellerOS backend/frontend
reference blueprint. This research is reference material; `docs/IMPLEMENTATION_BACKLOG.md` remains
the delivery contract.
