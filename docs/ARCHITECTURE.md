# SellerOS Architecture — Phase 2

## Architectural shape

SellerOS is a modular monolith. One FastAPI application and one relational database own a single
transaction boundary, while pure domain kernels keep mapping, scoring, strategy, profitability and
sourcing decisions independent from HTTP, React and persistence.

| Boundary | Responsibility |
| --- | --- |
| `backend/app/core` | Environment settings and stable application errors |
| `backend/app/db` | SQLAlchemy engine/session and UTC-aware database types |
| `backend/app/models` | Canonical persistence model and integrity constraints |
| `backend/app/modules/imports` | Safe workbook kernel, upload adapter and transactional import application service |
| `backend/app/modules/scoring` | Pure, versioned 0–100 market scoring kernel |
| `backend/app/modules/strategies` | Pure, versioned recommendation policy and evidence |
| `backend/app/modules/research` | Pure, versioned product-research classification and screen policy |
| `backend/app/modules/portfolio` | Bounded tenant-scoped dashboard/product read models |
| `backend/app/modules/workspaces` | Local first-use organisation/marketplace bootstrap |
| `backend/app/modules/profitability` | Pure versioned Decimal unit-economics kernel |
| `backend/app/modules/economics` | Scoped cost-profile revisions and economics read application |
| `backend/app/modules/sourcing` | Supplier quotation application plus pure versioned test-buy policy |
| `frontend/src/api` | Typed transport contracts and backend-response normalisation |
| `frontend/src/pages` | Dashboard, imports, products, evidence and planning workflows |
| `frontend/src/features/economics` | Cost, trace, supplier and advisory scenario components |

Routes validate and delegate. Business rules live in services or pure kernels. Repository queries are
bounded, tenant-scoped and deterministic. The architecture deliberately does not introduce
microservices, queues or distributed consistency during the MVP.

## Import transaction

1. The HTTP adapter validates extension, media type and compressed size while streaming to a safe
   server-generated staging key.
2. The workbook kernel validates the OOXML archive, blocks unsafe embedded content, detects the
   worksheet/header and returns a bounded preview using `data_only=True`.
3. A versioned source-schema manifest classifies the Keepa Product Finder v1 header set independently
   from the alias registry. Exact matching is order-independent after normalisation; compatible
   matching requires ASIN plus at least 80% registered-header coverage. The source-schema and actual
   header checksums are stored.
4. A versioned alias registry maps canonical decision fields by normalised header text, never fixed
   positions. Registered-but-not-canonical fields remain preserved evidence. Ambiguity stays
   unresolved until an explicit one-based ordinal decision is stored.
5. Inspection reports every date detected in the worksheet name and original filename. It suggests a
   date only when candidates agree. Confirmation requires the seller to submit `observed_on`;
   upload/processing time is never used as market-evidence time.
6. The database enforces idempotency by organisation + marketplace + SHA-256 checksum.
7. Confirmation revalidates checksum, headers and registry version, assigns the calendar-month period
   and next append-only revision, then creates products, dated snapshots, complete source payloads,
   raw exception attributes, score cards, strategy evidence, row errors and audit metadata in one
   database transaction using bounded snapshot flush chunks.
8. A fatal failure rolls back domain writes and marks the import failed separately. Expected bad rows
   are reported explicitly while valid unique-ASIN rows commit together.
9. Staged workbook content is removed after completion or terminal failure.

Known retryable database failures roll back the transaction and return a stable 503 while retaining
the pending batch and staged workbook. Unknown operational database faults return a stable,
non-retryable 500 but retain the same evidence for operator diagnosis; exception text, SQL parameters
and workbook values are not logged. File-backed SQLite enables foreign keys, WAL and a bounded busy
timeout; PostgreSQL remains the production-compatible concurrency target.

Import states are intentionally small: `pending`, `completed`, `failed`. A completed confirmation and
a repeated checksum are idempotent reads, not new snapshots.

Several different files may represent the same schema and month. They are retained as revision 1,
revision 2 and so on under organisation + marketplace + schema + period. A concurrent revision-number
collision fails retryably rather than overwriting evidence. Product latest pointers compare
`observed_on` first and revision only when observation dates match, so a late upload of an older
month cannot replace newer market evidence.

## Economics and sourcing transactions

1. Cost-profile creation verifies organisation/marketplace/product scope, exact marketplace currency,
   explicit selling-price GST basis, timezone-aware effective dates and complete fee provenance. It
   closes only the prior effective window, inserts a new revision and audit event, then commits once.
2. Economics reads resolve product and marketplace-default profiles independently as of UTC now, then
   apply product precedence. No fields are merged and no missing input is inferred. The pure v2
   profitability kernel removes output GST from tax-inclusive price evidence and returns a
   formula/checksum/input trace on demand.
3. Supplier-offer creation verifies the scoped product, marketplace currency, quotation/validity
   dates and increasing additional tiers, then stores the supplier-name-at-quote, base MOQ tier,
   quotation and audit event atomically.
4. Test-buy creation loads the same scoped product/offer, latest immutable snapshot and latest
   Data Confidence evidence. The pure policy returns three scenarios; their aggregate outcome,
   source snapshot/score identifiers, structured evidence, append-only recommendation and audit event
   commit together. No order-side effect exists.

## Data invariants

- Product identity is unique by organisation, marketplace and ASIN.
- A completed import creates at most one snapshot per product.
- A confirmed import has a seller-confirmed `observed_on`, first-of-month `period_month`, positive
  revision and source-schema identity. Those fields are assigned together.
- Each new snapshot preserves every source cell as ordered ordinal/header/value evidence, including
  blanks and registered fields not currently mapped to canonical decision fields.
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
- Cost-profile revisions are organisation/marketplace scoped, effective-dated and linked to the
  revision they supersede. A database check prevents a default/product scope-key mismatch. ORM
  updates are limited to one UTC closure of the prior effective window; profiles and audit events
  cannot be deleted or otherwise updated.
- Supplier quotations, their supplier-name snapshots, tiers and persisted test-buy recommendations
  are append-only through the ORM. A tier can only be inserted with its new parent offer. Required
  investment and all seller money use `Decimal`/`Numeric` with currency codes.
- Imported snapshots never update cost profiles, supplier quotations, budgets or inventory.
- Upload and processing timestamps are never used to order market evidence. Legacy snapshots without
  an observation date remain unchanged and are excluded from current portfolio, economics and
  sourcing decisions.

## Decision safety

The scoring and strategy packages are pure and configuration-driven. Missing or invalid market data
reduces Data Confidence. Overall Opportunity is confidence-adjusted. Low confidence blocks aggressive
recommendations. Import-only data cannot produce Growth, Cash Cow, Premium Margin or Clearance Watch
because those require seller economics or inventory evidence that Phase 1 does not invent.

The profitability kernel calculates only from an explicit effective cost profile, compatible
observed selling-price currency and explicit tax basis. Purchase cost is GST-exclusive. For a
GST-inclusive selling price, v2 separates net revenue and output GST before contribution and margin;
fees and allowances retain their documented gross-price basis. Incomplete fees or unknown legacy tax
basis produce partial outputs instead of assumed values.
The sourcing kernel consumes an immutable quotation, seller-confirmed budget and persisted market
evidence. Low confidence caps quantities; missing evidence, expired offers and hard-constraint
failures block all scenarios.

The research kernel converts current confirmed market evidence into an explainable shortlist without
changing persisted scores or strategy outputs. Its JSON policy is schema-validated and checksummed.
Brand values classify evidence only; they never prove trademark, category or resale authorisation.
The strongest result is `priority_research`, not `buy`. Supplier cost, Amazon fees, availability and
permission remain explicit downstream gates.

The portfolio dashboard performs a bounded aggregate over latest confirmed snapshots before showing
product recommendations. Evidence coverage and distributions are calculated within organisation and
marketplace scope. A fail-closed 70% monthly-demand-and-price threshold prevents partial Keepa
coverage from being presented as category revenue.

Every UI decision uses Observed, Calculated, Estimated, Recommended or User confirmed labels.
Recommendations are advisory; Phase 2 never purchases, reorders, reprices or marks down inventory.

## Multi-tenancy and deployment boundary

Database uniqueness and every portfolio, import, economics and sourcing read or mutation boundary
carry organisation and marketplace scope. Phase 2 has no authentication or request principal, so opaque IDs alone are not a
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

## Known Phase 2 limits

- Imports run in the request process. Flushes are write-bounded, but confirmation still materialises
  all workbook rows and retains one atomic ORM unit of work. Wide/high-row imports therefore need a
  memory-bounded background-job boundary before production; SQLite WAL only improves local
  concurrency, not this memory profile.
- One bundled Keepa alias registry, scoring formula and strategy policy are active.
- Economics configuration checksums cover versioned parameter/rounding resources; formula versions,
  traces and fixed examples govern code semantics. A canonical formula manifest should be added
  before any future financial action-authority expansion.
- Authentication, rate limits, malware scanning service, object storage, backups and restore drills
  are required before production.
- Amazon fees and selling-price tax basis are seller-entered evidence; no fee API, tax-return engine
  or FX conversion policy exists. Missing fees or tax basis intentionally leave dependent outputs
  unavailable.
- No seller/workspace timezone is modeled yet. Quotation calendar-date validation uses UTC and the UI
  labels it; dataset future-date validation also uses the UTC calendar date. Effective timestamps
  always carry an explicit offset.
- Keepa monthly sold is labelled Estimated and is not treated as observed order history.
- Inventory, reorder, lifecycle, markdown and portfolio cash-flow workflows remain later phases.
- Supplier attachments and purchase-order execution are out of scope; test-buy results are advisory.
- No Keepa API, Amazon SP-API, billing or AI runtime is present.
