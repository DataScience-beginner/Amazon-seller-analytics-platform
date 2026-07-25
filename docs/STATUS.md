# SellerOS Delivery Status

Last verified implementation target: Phase 2, stories SOS-401 through SOS-502, plus the
decision-first SOS-304 product-research refinement.

| Story | Status | Implemented evidence |
| --- | --- | --- |
| SOS-001 | Complete | Modular FastAPI/React foundation, migrations and CI |
| SOS-002 | Complete | Canonical tenant-aware domain model and data-separation tests |
| SOS-101 | Complete | Bounded `.xlsx` staging, OOXML safety validation, checksum/status and safe errors |
| SOS-102 | Complete | Versioned aliases, normalisation, ambiguity decisions, preview and unknown preservation |
| SOS-103 | Complete | Explicit observed date, versioned 173-column Keepa dataset identity, lossless source payloads, monthly revisions, transactional immutable snapshots and chronology-safe latest evidence |
| SOS-201 | Complete | Five versioned 0–100 scores with persisted inputs, reasons and config checksum |
| SOS-202 | Complete | Eight deterministic strategies, confidence gate, evidence and history |
| SOS-301 | Complete | Tenant-scoped KPI dashboard, opportunities, risks, quality and first-use state |
| SOS-302 | Complete | Server search/filter/sort/pagination with URL-preserved frontend filters |
| SOS-303 | Complete | Product metrics, score reasons, recommendation evidence and 24-snapshot history |
| SOS-304 | Complete | Versioned research screens, brand-evidence classification, critical metrics, explainable shortlist and current-page charts |
| SOS-305 | Complete | Dataset readiness, evidence coverage, category/subcategory, brand and selling-price distribution charts, single-category navigation and fail-closed revenue |
| SOS-306 | Complete | Tabbed subcategory Keepa table and versioned configurable reverse target-sourcing-cost estimator |
| SOS-307 | Complete | Explicit completed-import selector propagated through overview, category, products and sourcing estimates |
| SOS-308 | Complete | Versioned transparent subcategory research ranking, server sorting, single-seller risk cap, safe thumbnails and validated imported/slugged marketplace Amazon links |
| SOS-401 | Complete | Append-only product/default cost revisions, explicit GST basis, fee provenance and audit history |
| SOS-402 | Complete | Versioned Decimal v2 economics with net-revenue/output-GST trace, eight required metrics and fail-closed partial states |
| SOS-501 | Complete | Immutable scoped quotations with supplier-name evidence, MOQ/lead time/validity and sealed price tiers |
| SOS-502 | Complete | Three persisted advisory scenarios with source IDs, evidence, aggregate outcome and demand/confidence/lead-time/budget gates |

“Complete” means implemented against the repository acceptance criteria with synthetic automated
coverage. It does not mean production SaaS readiness.

Local frontend development uses a same-origin `/api` contract with Vite proxying to the backend on
`127.0.0.1:8000`. This keeps GitHub Codespaces private-port authentication outside browser API calls.

The repository includes a Railway founder-preview image that builds and serves the React SPA from
FastAPI, migrates a separate PostgreSQL service, binds to Railway's assigned port and fails closed
without an interim whole-application preview login. This does not change the production boundary:
user identity and enforced request-principal tenant authorisation remain required before customer or
public SaaS access.

## Dated Keepa dataset evidence

The registered `keepa.product_finder` v1.0.0 source model contains 173 headers. The reference export
is classified as 21 canonical decision fields plus 152 registered fields preserved as source
evidence. Inspection may suggest an observation date from an ISO date in the worksheet name or
filename only when all detected candidates agree. Confirmation still requires an explicit
seller-confirmed date.

Completed imports are keyed to a calendar month and append-only revision. Every snapshot stores all
source cells by ordinal/header/value. Portfolio, economics and sourcing choose evidence by confirmed
observation date; upload and processing timestamps are operational metadata only. Historical
snapshots created before this contract remain explicitly `legacy_unconfirmed`, are not rewritten,
and are excluded from current decisions until new dated evidence is imported.

## Current quality gate

The required gate is:

```text
backend:  ruff format --check . && ruff check . && mypy app tests && pytest
frontend: npm run lint && npm run format && npm run typecheck && npm test && npm run build
```

Do not replace this section with claimed results. Record exact executed results in the commit/PR or
delivery report.

## Next authorised phase

Phase 3 begins at SOS-601 (inventory positions, stock cover, reorder and lifecycle/pricing plans).
Before public release, identity and tenant authorisation must also be scheduled. Phase 3 must use
new seller-confirmed inventory evidence and must not reinterpret historical import, cost or sourcing
outputs in place. Production import hardening must move confirmation to a memory-bounded background
job; the current request-process importer bounds flush size but retains the full atomic workbook unit
of work in memory.
