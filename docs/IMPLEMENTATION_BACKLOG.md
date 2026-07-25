# SellerOS Phase Plan and Product Backlog

## Delivery principles

- Complete one vertical business workflow at a time.
- Keep calculations deterministic and explainable.
- Treat every Keepa upload as an immutable snapshot.
- Do not couple database fields directly to Keepa header names.
- Finish acceptance criteria, tests and documentation before marking a story done.
- Build responsive web first; package as a native mobile app only after product-market validation.

## Phase 0 — Foundation and architecture

### Epic E0: Establish a maintainable SaaS-ready foundation

#### SOS-001 — Restructure the prototype into a modular application

**As a developer,** I need a modular repository so features can grow without placing all logic in one file.

**Scope**

- Backend: Python, FastAPI, SQLAlchemy 2.x, Alembic and Pydantic.
- Frontend: React, TypeScript, Vite and a consistent component system.
- Local database: SQLite.
- Production-compatible database: PostgreSQL.
- Create clear backend, frontend, tests and docs folders.
- Preserve useful behaviour from the current prototype, but do not preserve its monolithic design.

**Acceptance criteria**

- Backend and frontend start using documented commands.
- `/health` returns application and database health.
- Configuration is environment based.
- No secrets are committed.
- Database migrations create a clean database.
- A mobile-width layout is usable at 360 px.
- CI runs linting, type checks and tests.

#### SOS-002 — Define the canonical domain model

**As a product owner,** I need market data separated from business data so changing Keepa columns cannot corrupt the business model.

**Required entities**

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

**Acceptance criteria**

- Product identity is unique by organisation, marketplace and ASIN.
- Snapshots are immutable.
- Raw attributes can store unrecognised Keepa values.
- Business inputs do not get overwritten by imports.
- Entity relationships and indexes are documented.

## Phase 1 — Keepa import and portfolio intelligence MVP

### Epic E1: Dynamic Keepa ingestion

#### SOS-101 — Upload and validate Excel files

**As an Amazon seller,** I want to upload a Keepa `.xlsx` export so the platform can analyse my product universe.

**Acceptance criteria**

- Only allowed file types and configured maximum sizes are accepted.
- The workbook, sheet and header row are detected safely.
- Empty files and unsupported structures return user-friendly errors.
- The original filename, checksum, upload time and import status are stored.
- An import cannot partially appear successful; it is completed transactionally or marked failed.
- Formula cells are read as values only; uploaded content is never executed.

#### SOS-102 — Implement configurable column mapping

**As a system administrator,** I need Keepa columns mapped to canonical fields even when column names change.

**Acceptance criteria**

- Mapping uses a version-controlled alias registry.
- Matching normalises case, whitespace and punctuation.
- Required, optional, unknown and missing columns are reported.
- Unknown columns and values are preserved.
- Ambiguous mappings require confirmation rather than guessing.
- Mapping output can be previewed before import confirmation.
- Mapping decisions are stored per import.

#### SOS-103 — Match ASINs and create monthly snapshots

**As a seller,** I want repeated uploads to update history rather than duplicate products.

**Acceptance criteria**

- Products are matched by organisation, marketplace and ASIN.
- A new ProductSnapshot is created for every valid imported product.
- Previous snapshots remain unchanged.
- Confirmation requires an explicit seller-confirmed observation date; upload and processing
  timestamps never substitute for source evidence time.
- Each completed import records its source-schema identity/version/checksum, source-header checksum,
  calendar-month period and append-only revision.
- Every source cell is preserved by one-based ordinal, original header and JSON-safe value, including
  registered fields that SellerOS does not yet use in calculations.
- Repeated files for the same dataset month create ordered revisions rather than overwriting prior
  evidence. Product “latest” state follows observation date, then same-date revision—not upload time.
- New ASINs create products.
- Missing ASINs are recorded as row errors unless an approved fallback exists.
- Re-uploading the same file checksum is idempotent and does not duplicate snapshots.
- Import summary shows created, matched, skipped and failed rows.

### Epic E2: Explainable scoring and strategy

#### SOS-201 — Implement versioned scoring engine

**As a seller,** I want separate product scores so I understand both opportunity and risk.

**Scores**

- Demand
- Competition
- Price Stability
- Data Confidence
- Overall Opportunity

Profitability, cash efficiency and inventory risk are added when business inputs exist.

**Acceptance criteria**

- Each score returns a value from 0 to 100.
- Each score stores formula version, input values and reason codes.
- Missing fields reduce confidence rather than being silently replaced with optimistic values.
- Division by zero, invalid percentages and extreme outliers are handled.
- Unit tests cover boundaries and representative products.
- Score weights are configuration, not UI hard-coding.

#### SOS-202 — Implement first strategy classifier

**As a seller,** I want products categorised by selling strategy so I can take the right action.

**Initial strategies**

- Discovery
- Test Buy
- Growth
- Cash Cow
- Premium Margin
- Monitor
- Clearance Watch
- Avoid

**Acceptance criteria**

- Strategy rules are deterministic and versioned.
- A recommendation includes at least two positive/negative evidence statements where data permits.
- Low data confidence prevents aggressive recommendations.
- Strategy history can be viewed by product and snapshot.
- Tests cover every strategy and priority conflict.

### Epic E3: Portfolio experience

#### SOS-301 — Build executive dashboard

**As a seller,** I want a command-centre view so I know where to focus.

**Acceptance criteria**

- Shows number of tracked products, latest import, strategy distribution and data-quality alerts.
- Shows top opportunities and top risks.
- Every KPI has a documented definition.
- Empty and first-use states guide the user to upload data.
- Desktop and mobile layouts are accessible and usable.

#### SOS-302 — Build product opportunity table

**As a seller,** I want to search, filter and sort products so I can shortlist opportunities.

**Acceptance criteria**

- Search by ASIN, title and brand.
- Filter by strategy, category, score ranges, offer count, price and confidence.
- Sort is server-side and paginated.
- Columns can be configured without breaking the API.
- Selected filters remain in the URL.
- Loading, no-result and error states are implemented.

#### SOS-303 — Build product detail and evidence view

**As a seller,** I want to inspect why a product received its recommendation.

**Acceptance criteria**

- Shows latest market metrics and historical snapshots.
- Shows scores, reason codes and formula version.
- Shows positive signals, warnings and missing-data notices.
- Links to the Amazon listing when available.
- No recommendation is presented without its supporting data.

#### SOS-304 — Build a decision-first product research screener

**As a seller,** I want a small, explainable candidate list so I can decide what deserves deeper
supplier and profitability research without being overwhelmed by raw Keepa columns.

**Acceptance criteria**

- Versioned screens cover priority research, promising, low seller competition, stable pricing,
  insufficient evidence and the bounded full universe.
- Results show demand, current seller offers, observed Buy Box price, price stability, data
  confidence and Keepa-estimated monthly purchases where available.
- Brand evidence is classified as declared, likely generic or unknown without inferring resale
  authorisation.
- Every product receives structured reason, positive, risk and missing-evidence codes from a pure
  configuration-driven policy.
- “Priority research” is explicitly a research shortlist, never a buy instruction.
- Filters and screen selection remain in the URL, results stay server-paginated and charts identify
  when they represent only the current page.

#### SOS-305 — Explain dataset readiness before product decisions

**As a seller,** I want a broad explanation of each imported dataset so I know what conclusions its
evidence can responsibly support.

**Acceptance criteria**

- The dashboard shows bounded, tenant-scoped product, category, subcategory and brand counts.
- Coverage is charted for price, rank, rank history, seller offers, reviews, brand and monthly demand.
- Category or subcategory distribution and brand concentration precede individual product rankings.
- Selecting a category loads its scoped subcategory, brand and coverage charts plus a bounded ranked
  product table without replacing the whole-dataset context.
- Estimated revenue is hidden unless at least 70% of products have both monthly demand and price
  evidence in one currency.
- Conclusions clearly distinguish relative product research from revenue-ready evidence.
- Single-category and material brand-concentration datasets receive explicit notices.

#### SOS-306 — Compare category evidence with target sourcing cost

**As a seller,** I want Keepa evidence and a reverse cost estimate in separate table views so I can
decide the maximum wholesale price worth investigating.

**Acceptance criteria**

- Selecting a subcategory opens a bounded, paginated Keepa evidence table.
- A separate tab calculates target wholesale cost from the 90-day average Buy Box price, falling
  back explicitly to the current Buy Box.
- GST, Amazon fee, shipping/fulfilment, advertising, returns and target-profit assumptions are
  configurable Decimal percentages with labelled defaults.
- Maximum wholesale cost is GST-exclusive and purchasing cash outlay including recoverable input GST
  is shown separately.
- The versioned calculation runs in a pure backend kernel and never creates a seller cost profile,
  supplier quotation or purchasing instruction.

#### SOS-307 — Select an imported dataset explicitly

**As a seller,** I want to switch between completed imports so separate research datasets are not
silently blended.

**Acceptance criteria**

- The dashboard lists completed imports with filename, observation date and row count.
- The combined latest-evidence view is explicitly labelled and remains available.
- Selecting an import batch scopes dataset overview, category drill-down, subcategory product table
  and target-sourcing-cost estimates to snapshots from that batch.
- Import selection never deletes, overwrites or re-dates historical evidence.
- A CSV that was not successfully imported cannot appear as an available dataset.

## Phase 2 — Unit economics and sourcing

### Epic E4: Profitability engine

#### SOS-401 — Create editable cost profiles

**As a seller,** I want to enter sourcing and operational costs so profitability reflects my business.

**Acceptance criteria**

- Supports purchase cost, GST assumptions, freight, prep, packaging, advertising, returns and overhead.
- Cost profiles may be product-specific or defaulted from organisation settings.
- Inputs have effective dates and audit history.
- Imports never overwrite seller-entered costs.
- Currency and marketplace are explicit.

#### SOS-402 — Calculate unit economics

**As a seller,** I want trustworthy profit metrics before placing an order.

**Outputs**

- landed cost;
- Amazon fees;
- contribution profit;
- margin;
- ROI;
- break-even price;
- minimum acceptable price;
- target price.

**Acceptance criteria**

- Calculations use Decimal, not binary floating point.
- Fee inputs show source and date.
- Missing fee data is clearly marked as estimated.
- Every output can be traced to its formula and inputs.
- Automated tests use fixed expected examples.

### Epic E5: Suppliers and sourcing decisions

#### SOS-501 — Record supplier offers

**As a seller,** I want supplier quotations stored by product so I can compare sourcing options.

**Acceptance criteria**

- Store supplier, MOQ, unit cost, lead time, quotation date, validity and notes.
- Support price tiers.
- Supplier documents are out of scope initially, but the model allows attachments later.
- The best offer is not selected only by price; lead time and MOQ are shown.

#### SOS-502 — Generate test-buy recommendation

**As a seller,** I want a proposed test quantity based on demand, confidence, lead time and budget.

**Acceptance criteria**

- Conservative, expected and aggressive scenarios are returned.
- Low-confidence products have capped quantities.
- Recommendation shows required investment and expected sell-through period.
- The system does not automatically place an order.

## Phase 3 — Inventory, lifecycle and pricing

### Epic E6: Inventory planning

#### SOS-601 — Maintain inventory positions

**As a seller,** I want current, inbound and reserved stock recorded so stock-cover calculations are useful.

**Acceptance criteria**

- Manual entry is supported initially.
- Inventory changes have an audit trail.
- Negative inventory is prevented unless an explicit adjustment is recorded.
- Future SP-API synchronisation can replace manual updates without changing the domain model.

#### SOS-602 — Calculate stock cover and reorder recommendations

**Acceptance criteria**

- Calculates demand rate, safety stock, reorder point, reorder date and proposed quantity.
- Lead-time and scenario assumptions are visible.
- A reorder recommendation is blocked when economics or risk violate configured thresholds.
- Recommendations include cash required and projected stock-out date.

### Epic E7: Product lifecycle and markdown strategy

#### SOS-701 — Track lifecycle stage

**Acceptance criteria**

- Stages: Discovery, Test, Growth, Scale, Maturity, Decline and Exit.
- Changes may be system-recommended but require user confirmation in the MVP.
- Every change stores reason, actor and timestamp.

#### SOS-702 — Create pricing and clearance plan

**Acceptance criteria**

- Produces launch, normal, accelerate, markdown and clearance price recommendations.
- Never recommends below minimum acceptable price without an explicit loss-clearance warning.
- Considers price trend, stock age, stock cover, competition and seasonality.
- Recommendations are advisory only.
- Sensitivity analysis shows units required at each proposed price.

## Phase 4 — Cash flow and forecasting

### Epic E8: Portfolio financial planning

#### SOS-801 — Create 3-, 6- and 12-month forecast scenarios

**Acceptance criteria**

- Supports conservative, expected and aggressive scenarios.
- Includes opening cash, purchase commitments, sales receipts, Amazon settlement lag, expenses and taxes as configurable assumptions.
- Displays monthly opening cash, inflows, outflows and closing cash.
- Highlights lowest cash balance and maximum working-capital requirement.
- Forecast assumptions are saved and versioned.

#### SOS-802 — Identify cash locked in inventory

**Acceptance criteria**

- Calculates cash tied by product and ageing band.
- Highlights slow-moving stock and expected recovery under normal versus clearance pricing.
- Does not treat unsold inventory value as realised cash.

## Phase 5 — Integrations and automation

### Epic E9: Data integrations

#### SOS-901 — Add Keepa API adapter

- Use an adapter interface so Excel remains supported.
- Store source metadata and timestamps.
- Implement rate-limit and failure handling.

#### SOS-902 — Add Amazon SP-API adapter

- Synchronise inventory, orders and settlement data only after permissions and data contracts are documented.
- Use background jobs and secure secret storage.

### Epic E10: Notifications

- Reorder alerts.
- Price deterioration alerts.
- Excess inventory alerts.
- Import completion/failure alerts.
- Notification preferences and suppression rules.

## Phase 6 — Multi-tenant SaaS and commercial launch

### Epic E11: Organisations, security and billing readiness

- Authentication and secure session handling.
- Organisation isolation at every query boundary.
- Roles: Owner, Admin, Analyst and Viewer.
- Usage metering for imports, products and integrations.
- Subscription-ready plan model.
- Audit log and data export/deletion processes.

### Epic E12: AI business advisor

- AI receives calculated, cited platform facts only.
- AI explains recommendations and compares scenarios.
- AI output is labelled advisory.
- Numerical responses are validated against deterministic calculations.
- No autonomous purchasing or pricing actions.

## Definition of Done for every story

A story is done only when:

1. acceptance criteria are met;
2. backend and frontend validation exist where applicable;
3. tests cover happy paths, important edge cases and permissions;
4. errors are observable and user friendly;
5. migrations are included;
6. API contracts are documented;
7. mobile layout is checked where applicable;
8. no secrets or private workbook data are committed;
9. the README or relevant documentation is updated;
10. the change is committed with a focused message.
