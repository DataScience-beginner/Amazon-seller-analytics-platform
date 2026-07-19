# SellerOS Phase 0 Architecture

## Current state inspected

The repository began as a single-file FastAPI prototype in `app.py`. Useful prototype behaviours to preserve in later phases are:

- Keepa workbook upload and parsing through OpenPyXL.
- Alias-based mapping for known Keepa headers.
- Preservation of raw/unknown row values.
- ASIN-centred product records and monthly snapshots.
- A dashboard, product opportunity view, product detail view and first-cut planning page.

Prototype limitations discovered:

- All backend, HTML and CSS are in one file.
- Database tables are created directly with SQLite statements and no migrations.
- Product identity is only ASIN, not organisation + marketplace + ASIN.
- Imported market data and seller-entered business data live on the same product row.
- Money uses floating point values in the prototype.
- No automated tests, API versioning, structured configuration or frontend build pipeline existed.
- The sample Keepa export is private seller data and should not be committed in future changes.

## Modular monolith foundation

Phase 0 introduces a modular monolith rather than microservices:

- `backend/app/api` contains versioned FastAPI routes.
- `backend/app/core` contains environment-backed settings.
- `backend/app/db` contains SQLAlchemy engine/session setup and shared metadata.
- `backend/app/models` contains the initial canonical data model.
- `backend/alembic` contains migrations.
- `backend/tests` contains backend tests.
- `frontend/src/api` contains the API client foundation.
- `frontend/src/components` contains reusable React components.
- `frontend/src/pages` and `frontend/src/features` are reserved for Phase 1 workflows.

## Domain model principles

- Product identity is unique by organisation, marketplace and ASIN.
- Product snapshots store imported market metrics and reject ORM updates and deletes, making them
  immutable evidence records. Corrections must create a new snapshot.
- Raw Keepa attributes preserve unknown/dynamic columns without coupling the domain to vendor header names.
- Seller-entered costs, supplier offers, inventory and pricing plans are separate from market snapshots.
- Monetary fields use Decimal-compatible `Numeric` columns and explicit ISO currency codes.
- Timestamps are modelled as timezone-aware UTC values.
