# SellerOS backend and frontend reference blueprint

This document translates the competitive research into a coherent SellerOS product architecture.
It is a reference design, not an instruction to implement every competitor feature. The existing
[product backlog](../IMPLEMENTATION_BACKLOG.md) remains the delivery contract.

## 1. Product stance

SellerOS should operate between market-intelligence tools and Amazon's system of record:

```text
Keepa exports / future APIs        Seller-owned business inputs       Amazon operational data
              |                               |                               |
              +-------------------------------+-------------------------------+
                                              |
                                      SellerOS evidence layer
                                              |
                         deterministic economics, scores and scenarios
                                              |
                               recommendations + action queue
                                              |
                                  seller-confirmed decisions
```

The unifying object is not a tool or chart. It is a product decision scoped by organisation,
marketplace and time:

- market evidence: price, rank, offer, rating, seller and trend observations;
- business evidence: landed costs, supplier terms, inventory, lead time and cash constraints;
- calculated evidence: profit, ROI, stock cover, cash efficiency and confidence;
- recommendation: test, grow, monitor, reorder, mark down, clear or avoid;
- decision: accepted, rejected, deferred or superseded by a user;
- outcome: later sales, inventory, margin and cash evidence used to evaluate the decision.

## 2. Adopted product patterns

The reviewed platforms repeatedly use several effective patterns:

| Pattern                          | SellerOS application                                                                   |
| -------------------------------- | -------------------------------------------------------------------------------------- |
| Marketplace/account context      | Persistent context switcher; never silently mix marketplaces or organisations          |
| Filter-first research            | Server-side filters with clear units, ranges, active-filter chips and saved views      |
| Configurable result tables       | Column chooser, deterministic sorting, pagination and bounded export                   |
| Watchlists/trackers              | Shortlists for products under consideration, separate from products actually stocked   |
| Trend graph plus current summary | Latest values at a glance with selectable, immutable historical evidence               |
| Expandable table rows            | Quick evidence and warnings without forcing a full page transition                     |
| Dedicated detail workspace       | Deeper scores, history, costs, inventory and recommendations for one product           |
| Action-oriented inventory labels | Recommended states tied to formula version, evidence, date and confidence              |
| Connected workflow hand-offs     | Preserve selected products, keywords or assumptions when moving between steps          |
| Alerts and exception queues      | Prioritize products needing attention rather than expecting users to inspect every row |
| Guided setup                     | First-use checklist for marketplace, import, costs and inventory completeness          |
| Progressive disclosure           | Recommendation first; calculation, raw evidence and audit history on demand            |

SellerOS should implement these interaction principles in its own visual language and with
transparent formulas.

## 3. Frontend information architecture

### 3.1 Persistent application frame

Desktop navigation:

1. Dashboard
2. Imports
3. Products
4. Decisions
5. Economics
6. Sourcing
7. Inventory
8. Planning
9. Settings

Only Dashboard, Imports, Products and Planning need to be visible in the early MVP. Navigation
items should appear when a usable workflow exists, not as a catalogue of empty tools.

Persistent context and controls:

- organisation and marketplace selector;
- reporting currency and date/snapshot context;
- data freshness indicator;
- import/job status;
- global product search;
- notifications/action count;
- profile, help and settings menu.

At 360 px, use a compact header and accessible navigation drawer. Tables should become either
horizontally scrollable with pinned identity/action columns or purpose-built product cards; hiding
critical values is not acceptable.

### 3.2 Dashboard

Purpose: answer “what needs my attention and where is cash at risk?”

Recommended sections:

- setup/data-quality banner when required evidence is missing;
- latest import status, coverage and row-error summary;
- tracked products and strategy distribution;
- top opportunities and top risks;
- action queue: test, reorder, markdown, clearance and missing-data actions;
- working capital at risk and cash locked in ageing inventory when business data exists;
- recent recommendation changes and user decisions;
- freshness/source legend.

Every tile must drill into a filtered destination. KPIs need definitions, time windows, currency and
evidence labels. Empty states should lead to the next setup action.

### 3.3 Imports workspace

Purpose: make dynamic Keepa ingestion safe and understandable.

Recommended flow:

1. **Upload** — choose organisation and marketplace, then select a supported workbook.
2. **Validate** — show filename, size, checksum, workbook/sheet detection and structural errors.
3. **Map** — classify source columns as mapped, unknown, missing or ambiguous; allow explicit
   confirmation without guessing.
4. **Preview** — show synthetic/redacted row previews, canonical fields and preserved raw values.
5. **Import** — run transactionally and expose progress using a job-ready status contract.
6. **Summary** — created, matched, skipped and failed counts plus downloadable row errors.

Import history needs status, marketplace, source, alias-registry version, checksum, actor,
timestamps, counts and a link to mapping decisions. Re-uploading the same checksum should explain
the idempotent result rather than showing a generic error.

### 3.4 Product portfolio

Purpose: move from a large evidence set to a manageable shortlist and action.

Core controls:

- search by ASIN, title and brand;
- filter by strategy, lifecycle, score ranges, confidence, category, price, offers, seller count,
  profitability availability and inventory state;
- filter chips with clear reset behavior;
- saved views and sharable URL query parameters;
- deterministic server-side sort and pagination;
- column chooser with units and definitions;
- compare/shortlist selection;
- bounded export with active filter metadata.

Default columns should be intentionally small: identity, latest price, demand, competition,
confidence, overall opportunity, strategy, evidence date and next action. Financial columns should
not display invented zeroes when costs are missing.

Expandable rows can show:

- strongest positive signals;
- warnings and missing data;
- recent trend direction;
- latest recommendation change;
- shortcuts to details, costs and inventory.

### 3.5 Product detail and decision evidence

Purpose: answer “why is the system recommending this, and what would change the decision?”

Suggested tabs:

- **Overview** — current recommendation, confidence, reason codes and next action;
- **Market history** — price, rank, offers, reviews and seller trends by snapshot;
- **Scores** — each component, formula version, inputs, boundaries and missing-data effects;
- **Economics** — cost profile, fee assumptions, contribution, margin, ROI and break-even price;
- **Sourcing** — suppliers, offers, MOQ, lead time and validity;
- **Inventory** — current/inbound/reserved stock, cover, reorder and age;
- **Planning** — conservative/expected/aggressive quantities and cash effects;
- **Audit** — imports, calculations, recommendations and user decisions.

Observed, calculated, estimated, recommended and user-confirmed values must be visually and
semantically distinct. Charts require accessible tabular alternatives and source timestamps.

### 3.6 Decision and exception queue

Purpose: centralize work across products.

Each queue item should contain:

- action type and urgency;
- product/marketplace;
- recommended action and effective window;
- evidence summary and confidence;
- cash/profit impact where calculable;
- owner and due date when assigned;
- accept, defer, reject and inspect actions;
- reason required for high-impact overrides.

Acceptance must not execute a purchase or price change. It records a user-confirmed decision for
the MVP.

### 3.7 Economics and sourcing

Economics needs reusable, effective-dated cost profiles and a traceable calculation sheet. The UI
should support organisation defaults with explicit product overrides, never invisible inheritance.

Sourcing needs:

- supplier table and supplier detail;
- product-to-supplier offers;
- price tiers, MOQ, lead time, quote/validity dates and notes;
- comparison by total landed economics, not unit price alone;
- conservative/expected/aggressive test-buy scenarios;
- no global supplier marketplace in the initial product.

### 3.8 Inventory, lifecycle and pricing

Inventory views should use action states such as In Stock, Reorder Soon, Order Now, Overstock,
Ageing and Data Missing. Unlike opaque labels, every state must link to the exact inputs and rule
version.

Lifecycle and pricing should show:

- current and proposed lifecycle stage;
- stock age and cover;
- demand/price/competition evidence;
- minimum acceptable and target prices;
- launch, normal, accelerate, markdown and clearance scenarios;
- loss-clearance warning before any recommendation below the minimum acceptable price;
- user confirmation and audit history.

### 3.9 Cash-flow planning

Planning should offer conservative, expected and aggressive 3-, 6- and 12-month scenarios with:

- opening cash;
- planned purchasing and committed supplier payments;
- projected sales receipts and Amazon settlement lag;
- operating expenses and tax assumptions;
- monthly opening, inflow, outflow and closing balances;
- lowest cash point and maximum working-capital need;
- cash tied in inventory and normal-versus-clearance recovery;
- assumption versions and scenario comparison.

## 4. Frontend engineering boundaries

Suggested feature folders as workflows arrive:

```text
frontend/src/
  api/
  components/
    data/
    feedback/
    layout/
  features/
    imports/
    products/
    decisions/
    economics/
    sourcing/
    inventory/
    planning/
  pages/
  types/
```

Rules:

- React components display typed API results; they do not calculate scores, profit, reorder or cash
  forecasts.
- URL query parameters own portfolio filters, sorting, pagination and selected saved view.
- Query/loading state should be centralized rather than hand-built independently per component.
- Every page needs loading, empty, success, partial-data and error behavior.
- Money formatting always receives amount and currency; no global currency assumption.
- Date displays always show marketplace/user timezone context while APIs remain UTC.
- API error bodies need stable codes, field details and a correlation identifier.
- Tests should cover the import wizard, filter serialization, decision evidence and critical forms.

## 5. Backend modular-monolith capabilities

The competitors' public workflows imply many internal capabilities, but not their implementation.
SellerOS should keep these capabilities in one deployable backend with explicit module boundaries.

| Module                  | Responsibility                                                          | Important boundaries                                                                |
| ----------------------- | ----------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Identity and tenancy    | Organisations, users, roles, marketplaces and settings                  | No public SaaS launch before organisation isolation is enforced at query boundaries |
| Imports                 | Upload validation, checksums, workbook detection, row errors and status | Uploaded content never executes; transactional completion or explicit failure       |
| Mapping                 | Header normalization, aliases, ambiguity handling and mapping versions  | Never bind canonical fields to fixed positions or silently guess collisions         |
| Catalogue               | Organisation/marketplace/ASIN identity and product metadata             | ASIN alone is not globally unique in SellerOS                                       |
| Market evidence         | Immutable snapshots, raw attributes and observation provenance          | Corrections append evidence; they do not overwrite history                          |
| Scoring                 | Deterministic component scores and confidence                           | Formula versions, inputs and reason codes are stored                                |
| Recommendations         | Strategy/lifecycle/action rules                                         | Advisory, versioned, evidence-backed and separate from user decisions               |
| Costs and profitability | Effective-dated costs, fees and unit economics                          | Decimal arithmetic, explicit currency, rounding rules and source dates              |
| Sourcing                | Suppliers, quotations, tiers, MOQ and lead time                         | Seller-owned private data; no row-level logging                                     |
| Inventory               | Positions, movements, cover, reorder and ageing                         | Imported market data can never overwrite inventory                                  |
| Pricing                 | Minimum, target and lifecycle pricing scenarios                         | No autonomous repricing in the MVP                                                  |
| Forecasting             | Scenario assumptions, monthly cash flows and working capital            | Unsold inventory is not realized cash                                               |
| Decisions               | Accept/reject/defer/override recommendations                            | User action is append-only and auditable                                            |
| Audit                   | Actor, event, entity, before/after references and correlation           | Sensitive payload policy and retention controls                                     |
| Integrations            | Keepa Excel/API, SP-API and future ads adapters                         | External contracts isolated behind interfaces and rate-limit handling               |
| Reporting               | Bounded exports and KPI projections                                     | Definitions/version metadata travel with exports                                    |
| Notifications           | Rules, preferences, suppression and delivery                            | Created only after stable underlying action states exist                            |
| Entitlements            | Plan limits, usage counters and feature access                          | Entitlements cannot alter deterministic financial results                           |

## 6. Recommended backend package direction

The current Phase 0 directories are valid. As workflows grow, organize internally by business
capability rather than by competitor tool name:

```text
backend/app/
  api/v1/
  core/
  modules/
    imports/
    catalogue/
    intelligence/
    scoring/
    recommendations/
    economics/
    sourcing/
    inventory/
    pricing/
    forecasting/
    decisions/
    integrations/
  models/
  audit/
```

Each business module may contain schemas, services and repository interfaces. SQLAlchemy models and
adapter implementations remain infrastructure concerns. Route handlers validate, authorize and
delegate; they do not implement business rules.

This is a suggested evolution, not a Phase 1 restructuring requirement.

## 7. Phase 1 API reference

Exact request/response schemas should be defined during implementation, but these resource
boundaries support the required workflows:

```text
POST   /api/v1/imports
GET    /api/v1/imports
GET    /api/v1/imports/{import_id}
POST   /api/v1/imports/{import_id}/mapping-preview
PUT    /api/v1/imports/{import_id}/mapping
POST   /api/v1/imports/{import_id}/confirm
GET    /api/v1/imports/{import_id}/errors

GET    /api/v1/products
GET    /api/v1/products/{product_id}
GET    /api/v1/products/{product_id}/snapshots
GET    /api/v1/products/{product_id}/scores
GET    /api/v1/products/{product_id}/recommendations

GET    /api/v1/dashboard/summary
GET    /api/v1/dashboard/opportunities
GET    /api/v1/dashboard/risks
```

Design requirements:

- organisation and marketplace scope derived from an authorized context when authentication is
  implemented, never trusted solely from arbitrary client IDs;
- idempotency by organisation plus checksum for imports;
- cursor or bounded offset pagination with deterministic secondary sorting;
- stable filter validation and machine-readable error codes;
- response metadata for evidence time, formula/rule version, currency and data confidence;
- `202 Accepted` plus status polling only when import execution becomes asynchronous;
- no unbounded raw-attribute payload in normal product-list responses.

## 8. Data model additions to evaluate by phase

The Phase 0 model already contains the required canonical entities. Additions should be driven by
accepted stories, not by this research alone.

| Candidate                            | Why it may be needed                                    | Earliest phase   |
| ------------------------------------ | ------------------------------------------------------- | ---------------- |
| ColumnAliasRegistry / MappingVersion | Reproducible dynamic Keepa mappings                     | Phase 1          |
| ImportMappingDecision                | Audit ambiguous and confirmed mappings                  | Phase 1          |
| RecommendationEvidence               | Structured positive, negative and missing-data evidence | Phase 1          |
| SavedProductView / Shortlist         | Reusable portfolio workflows                            | Phase 1 or later |
| DecisionRecord                       | Accept, reject, defer and override recommendations      | Phase 1 or 3     |
| CostComponent / FeeAssumption        | Detailed, source-dated unit economics                   | Phase 2          |
| SupplierOfferTier                    | Quantity-sensitive supplier pricing                     | Phase 2          |
| InventoryMovement                    | Auditable manual/API inventory changes                  | Phase 3          |
| LifecycleTransition                  | Recommended and user-confirmed stage history            | Phase 3          |
| ForecastPeriod                       | Persisted monthly scenario outputs                      | Phase 4          |
| IntegrationConnection / SyncRun      | External authorization and synchronization history      | Phase 5          |
| NotificationRule / Delivery          | Preferences, suppression and delivery state             | Phase 5          |
| Role / Membership / Entitlement      | Tenant permissions and commercial limits                | Phase 6          |

Avoid adding generic JSON records when the contained data drives money, permissions, uniqueness or
business decisions. JSON is appropriate for preserved raw evidence and versioned calculation input
snapshots, with indexed canonical projections for supported queries.

## 9. Data and calculation contracts

### Source taxonomy

Every important value should carry or inherit:

- source type: Keepa export, seller input, Amazon integration, configuration or calculation;
- source identifier/import batch;
- observed/effective time;
- marketplace and currency where relevant;
- freshness/status;
- actor for seller-entered changes;
- formula/rule version for calculated or recommended values.

### Decision-safety language

- **Observed** — directly present in an import or integration.
- **Calculated** — deterministic output from stored inputs.
- **Estimated** — proxy or configurable assumption.
- **Recommended** — advisory output from versioned rules.
- **User confirmed** — accepted by an authorized user.

### Money

- Use Decimal end to end and document rounding at formula boundaries.
- Never add amounts in different currencies without an explicit dated conversion rate.
- Store amount and ISO currency code together at contracts and persistence boundaries.
- Distinguish sales proceeds, tax, fees, refunds, ad costs, COGS and inventory value.

## 10. Integration strategy

### Phase 1: Keepa Excel

Treat the workbook as untrusted, dynamic evidence. Use an adapter that yields normalized rows plus
raw source values. Formula cells are read as cached values only. Unknown headers survive the import.

### Phase 5: Keepa API

Implement the same canonical ingestion port so API synchronization and Excel upload create
equivalent snapshot records with different provenance.

### Phase 5: Amazon SP-API

Amazon publicly exposes APIs for listings, catalogue, inventory, orders, reports, finances, fees,
pricing and notifications. Introduce narrow adapters per bounded capability rather than one large
Amazon service. Reads arrive before any write-back. Authorization, marketplace endpoints,
restricted data, rate limits, retries and notification idempotency need dedicated designs.

### Advertising

Advertising data uses separate authorization and contracts. Do not assume an SP-API connection
also grants advertising access. Advertising management is not needed to prove SellerOS's operating
decision loop.

## 11. Explainability and audit

Competitor dashboards commonly offer scores, statuses and recommendations. SellerOS should improve
decision trust by guaranteeing:

- named component scores rather than one unexplained number;
- formula and rules versions;
- exact input snapshot;
- positive, negative and missing-data reason codes;
- confidence caps on aggressive actions;
- sensitivity or scenario comparison for high-value choices;
- append-only recommendation history;
- user decision and override reason;
- later outcome linkage for recommendation evaluation.

AI can summarize these facts in a future phase, but it cannot generate financial truth, silently
replace assumptions or execute a purchase/price action.

## 12. Non-functional reference

- Modular monolith for the first year; no competitor-inspired microservice sprawl.
- PostgreSQL-compatible schema, SQLite local development and reversible migrations.
- Strict tenant and marketplace scoping on every query and unique key.
- Background-job-ready imports with transactionally visible outcomes.
- Structured logs with correlation/import identifiers but no uploaded rows, supplier prices or PII.
- Metrics for import duration/failure, stale data, calculation errors and notification delivery.
- Accessible responsive UI at 360 px with semantic status text, keyboard support and visible focus.
- Deterministic synthetic test fixtures; never use the seller's private workbook.
- Contract, repository/integration, frontend component and end-to-end smoke tests as workflows land.

## 13. Delivery recommendation

Keep the approved sequence:

1. Finish dynamic import and immutable snapshot evidence.
2. Add transparent scores, strategies and product evidence views.
3. Add seller-owned costs and trustworthy unit economics.
4. Add suppliers, inventory, lifecycle and advisory pricing.
5. Add portfolio cash-flow scenarios.
6. Only then add external synchronization, notifications and commercial SaaS controls.

Keyword research, listing generation, advertising automation, review automation and browser
extensions are validated markets, but they would distract from SellerOS's primary advantage before
the cash-conversion operating loop works end to end.
