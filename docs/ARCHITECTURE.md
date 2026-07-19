# SellerOS Architecture — Phase 1

## Architectural shape

SellerOS is a modular monolith. One FastAPI application and one relational database own a single
transaction boundary, while pure domain kernels keep mapping, scoring and strategy decisions
independent from HTTP, React and persistence.

| Boundary | Responsibility |
| --- | --- |
| `backend/app/core` | Environment settings and stable application errors |
| `backend/app/db` | SQLAlchemy engine/session and UTC-aware database types |
| `backend/app/models` | Canonical persistence model and integrity constraints |
| `backend/app/modules/imports` | Safe workbook kernel, upload adapter and transactional import application service |
| `backend/app/modules/scoring` | Pure, versioned 0–100 market scoring kernel |
| `backend/app/modules/strategies` | Pure, versioned recommendation policy and evidence |
| `backend/app/modules/portfolio` | Bounded tenant-scoped dashboard/product read models |
| `backend/app/modules/workspaces` | Local first-use organisation/marketplace bootstrap |
| `frontend/src/api` | Typed transport contracts and backend-response normalisation |
| `frontend/src/pages` | Dashboard, imports, products, evidence and placeholder planning workflows |

Routes validate and delegate. Business rules live in services or pure kernels. Repository queries are
bounded, tenant-scoped and deterministic. The architecture deliberately does not introduce
microservices, queues or distributed consistency during the MVP.

## Import transaction

1. The HTTP adapter validates extension, media type and compressed size while streaming to a safe
   server-generated staging key.
2. The workbook kernel validates the OOXML archive, blocks unsafe embedded content, detects the
   worksheet/header and returns a bounded preview using `data_only=True`.
3. A versioned alias registry maps by normalised header text, never fixed positions. Ambiguity stays
   unresolved until an explicit one-based ordinal decision is stored.
4. The database enforces idempotency by organisation + marketplace + SHA-256 checksum.
5. Confirmation revalidates checksum, headers and registry version, then creates products,
   snapshots, raw attributes, score cards, strategy evidence, row errors and audit metadata in one
   database transaction.
6. A fatal failure rolls back domain writes and marks the import failed separately. Expected bad rows
   are reported explicitly while valid unique-ASIN rows commit together.
7. Staged workbook content is removed after completion or terminal failure.

Import states are intentionally small: `pending`, `completed`, `failed`. A completed confirmation and
a repeated checksum are idempotent reads, not new snapshots.

## Data invariants

- Product identity is unique by organisation, marketplace and ASIN.
- A completed import creates at most one snapshot per product.
- ProductSnapshot scalar columns and persisted raw/score/recommendation evidence cannot be updated or
  deleted through the ORM. Corrections create new versioned evidence.
- Unknown values and malformed mapped values are stored by source ordinal/header in RawAttribute;
  duplicate headers do not overwrite each other.
- Imported market facts remain on ProductSnapshot/RawAttribute. Seller-owned costs, suppliers,
  inventory and pricing stay in separate entities.
- Money uses SQL `Numeric`/Python `Decimal` and an explicit ISO currency code.
- `UTCDateTime` rejects naive writes and restores timezone-aware UTC values on SQLite as well as
  PostgreSQL.
- SQLite foreign-key enforcement is enabled on every connection.
- Score and recommendation records retain version, configuration checksum, inputs and evidence.

## Decision safety

The scoring and strategy packages are pure and configuration-driven. Missing or invalid market data
reduces Data Confidence. Overall Opportunity is confidence-adjusted. Low confidence blocks aggressive
recommendations. Import-only data cannot produce Growth, Cash Cow, Premium Margin or Clearance Watch
because those require seller economics or inventory evidence that Phase 1 does not invent.

Every UI decision uses the labels Observed, Calculated or Recommended. Recommendations are advisory;
Phase 1 never purchases, reorders, reprices or marks down inventory.

## Multi-tenancy and deployment boundary

Database uniqueness and every portfolio/import read or mutation boundary carry organisation and
marketplace scope. Phase 1 has no authentication or request principal, so opaque IDs alone are not a
security boundary. The unauthenticated workspace endpoint is disabled by default and enabled only in
the local sample configuration. Public deployment is blocked until identity, authorisation and
enforced tenant context are implemented.

## AI governance

AI agents may navigate documented modules, explain persisted evidence, propose versioned policy
changes and generate tests. They may not alter a stored snapshot, silently change a versioned JSON
policy, fabricate missing seller inputs or execute financial actions. See `AGENTS.md` for the required
read order and change protocol.

## Legacy prototype disposition

The root `app.py` demonstrated useful Keepa upload, alias, raw-field and dashboard concepts. It also
mixed HTML, SQL, parsing and calculations; used floats for business values; had ASIN-only identity;
and created tables without migrations. It remains labelled legacy reference material only. No new
code may import it or copy its architecture.

## Known Phase 1 limits

- Imports run in the request process; the service boundary is designed for a later background job.
- One bundled Keepa alias registry, scoring formula and strategy policy are active.
- Authentication, rate limits, malware scanning service, object storage, backups and restore drills
  are required before production.
- Seller economics and inventory are modelled but not yet editable or used at import time.
- No Keepa API, Amazon SP-API, billing or AI runtime is present.
