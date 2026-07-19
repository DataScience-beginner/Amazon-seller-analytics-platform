# Competitive feature matrix

This matrix summarizes publicly documented capabilities as of 2026-07-19. `Yes` means a clear
first-party capability was found, `Partial` means the need is covered only in a narrower or
adjacent way, and `No evidence` means the research did not find a comparable public capability.
It does not prove that a private or newly released feature does not exist.

## Market research and catalogue intelligence

| Capability                                  | Helium 10                                                   | Seller Central                                                                   | Jungle Scout                                         | SellerOS response                                                                                       |
| ------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Filter a large product catalogue            | Yes — Black Box                                             | Partial — seller catalogue and opportunity tools, not the same research database | Yes — Product Database                               | Phase 1 product table should filter imported Keepa evidence; a global research database is not required |
| Discover niches by demand and competition   | Yes — Black Box keyword/market workflows                    | Partial — Product Opportunity Explorer and Brand Analytics for eligible sellers  | Yes — Opportunity Finder                             | Add category/niche aggregation after reliable product snapshots, not before                             |
| Browser overlay on Amazon pages             | Yes — Chrome Extension/Xray                                 | Native Amazon experience                                                         | Yes — browser extension                              | Defer; a web application and import workflow have higher value                                          |
| Save products and research lists            | Yes — My List                                               | Partial — catalogue and inventory views                                          | Yes — Product Tracker and groups                     | Add shortlist/watchlist state after the Phase 1 product table                                           |
| Product history and trends                  | Yes — extension charts, Market Tracker and product insights | Partial — business, inventory and brand trends                                   | Yes — Product Tracker and extension graphs           | Core Phase 1 requirement through immutable ProductSnapshot history                                      |
| Dynamic external-file import                | Partial — imports exist for selected tools                  | Extensive bulk uploads/reports, but not Keepa mapping                            | Partial — CSV exports/imports for selected workflows | Core differentiator: versioned aliases, mapping preview, unknown-column preservation and row errors     |
| Explicit data-confidence score              | Partial — tool-specific scores and alerts                   | No clear portfolio-wide equivalent found                                         | Partial — opportunity/listing quality scores         | Core Phase 1 score; missing fields must reduce confidence rather than be guessed                        |
| Transparent product strategy classification | No clear equivalent found                                   | Recommendations exist, but not SellerOS lifecycle strategies                     | No clear equivalent found                            | Core differentiator: deterministic Test Buy, Growth, Monitor, Clearance Watch and Avoid recommendations |

## Keywords, listing and market visibility

| Capability                             | Helium 10                                              | Seller Central                                             | Jungle Scout                                   | SellerOS response                                                                                       |
| -------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Keyword discovery                      | Yes — Cerebro; Magnet was merged into it in 2026       | Partial — Brand Analytics and advertising search-term data | Yes — Keyword Scout                            | Defer until after profitability and planning; it is not required for the initial operating loop         |
| Reverse-ASIN keyword research          | Yes — Cerebro                                          | Partial — brand/search analytics for eligible sellers      | Yes — Keyword Scout ASIN search                | Defer; preserve a future adapter boundary rather than adding fields to ProductSnapshot prematurely      |
| Keyword rank tracking                  | Yes — Keyword Tracker                                  | Partial — search/query performance                         | Yes — Rank Tracker                             | Defer to a later market-intelligence epic                                                               |
| Listing quality analysis               | Yes — Listing Analyzer and extension evaluator         | Listing issues and catalogue requirements                  | Yes — Listing Analyzer/LQS                     | Consider after Phase 1 evidence view; do not mix listing quality with financial viability               |
| Listing authoring and keyword coverage | Yes — Listing Builder, Scribbles and Keyword Processor | Yes — listing creation/editing, bulk feeds and A+ tools    | Yes — Listing Builder and AI assistance        | Out of current roadmap; SellerOS should link to the system of record before becoming an authoring suite |
| Direct listing synchronization         | Yes for connected accounts and supported tools         | Native system of record                                    | Yes for connected accounts and supported tools | Future SP-API adapter only; no Phase 1 write-back                                                       |

## Economics, sourcing and inventory

| Capability                                  | Helium 10                                       | Seller Central                                                                                 | Jungle Scout                                 | SellerOS response                                                                                    |
| ------------------------------------------- | ----------------------------------------------- | ---------------------------------------------------------------------------------------------- | -------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Fee and profitability calculator            | Yes                                             | Yes — fee preview and Revenue Calculator                                                       | Yes — FBA Profit Calculator                  | Phase 2 deterministic unit economics with explicit sources, dates, currency and assumptions          |
| Seller-entered COGS                         | Yes — used by Profits                           | Partial — COGS is accepted by some inventory tools, while settlement data remains Amazon-owned | Yes — Product Costs & Settings               | Phase 2 CostProfile, separate from imported market evidence                                          |
| Sales and profit analytics                  | Yes — Profits and Insights Dashboard            | Yes — business reports and Payments                                                            | Yes — Profit Overview/Sales Analytics        | Phase 2 portfolio profitability; distinguish observed settlements from estimated costs               |
| Supplier discovery and trade history        | No equivalent emphasized in reviewed core suite | No broad supplier-discovery database                                                           | Yes — Supplier Database and Supplier Tracker | SellerOS needs seller-owned suppliers/offers in Phase 2, not a global trade database initially       |
| Supplier quotations and MOQ/lead time       | Partial — purchase order/inventory inputs       | Partial — supply-chain programs                                                                | Yes — supplier and purchase-order workflows  | Phase 2 SupplierOffer with MOQ, lead time, validity and price tiers                                  |
| Inventory synchronization                   | Yes with connected seller account               | Yes — native FBA/FBM inventory                                                                 | Yes with connected seller account            | Manual entry first, SP-API later; keep source and observation time explicit                          |
| Reorder date and quantity                   | Yes — Inventory Manager                         | Yes — FBA restock recommendations                                                              | Yes — Inventory Manager                      | Phase 3 deterministic scenarios using stock, velocity, lead time, safety stock and cash constraints  |
| Excess, aged and stranded inventory actions | Partial — inventory and alerts                  | Yes — FBA inventory tools                                                                      | Partial — inventory status and forecast      | Phase 3 lifecycle and clearance queue; distinguish Amazon listing problems from commercial overstock |
| Product lifecycle and markdown strategy     | No complete equivalent found                    | Partial — pricing, excess inventory and removal recommendations                                | No complete equivalent found                 | Core SellerOS differentiator in Phase 3                                                              |

## Operations, finance and growth

| Capability                       | Helium 10                               | Seller Central                                                        | Jungle Scout                                          | SellerOS response                                                                |
| -------------------------------- | --------------------------------------- | --------------------------------------------------------------------- | ----------------------------------------------------- | -------------------------------------------------------------------------------- |
| Order and return operations      | Partial — connected analytics/follow-up | Yes — native order and return management                              | Partial — connected analytics/review workflows        | Do not rebuild in early phases; integrate through SP-API later                   |
| Pricing and automated repricing  | Partial — monitoring and selected tools | Yes — static and Automate Pricing rules                               | Partial — competitive and profitability insights      | Advisory pricing plans in Phase 3; no automatic repricing in the MVP             |
| Advertising campaign management  | Yes — Helium 10 Ads                     | Yes — Amazon Ads/Campaign Manager                                     | Yes — Ads Analytics and PPC optimization integrations | Defer; initially allow advertising cost assumptions and imported actuals         |
| Review request automation        | Yes — Follow-Up                         | Yes — native Request a Review and customer tools                      | Yes — Review Automation                               | Out of initial scope and policy-sensitive                                        |
| Listing/account change alerts    | Yes — Alerts and Insights               | Yes — notifications, listing issues and Account Health                | Partial — notifications and connected insights        | Add business-action notifications after recommendation workflows exist           |
| FBA reimbursement discovery      | Yes — Refund Genie                      | Native reimbursement/case processes                                   | Yes — FBA Reimbursements                              | Possible future financial-recovery module; not required for product-decision MVP |
| 3/6/12-month cash-flow scenarios | No clear equivalent found               | Payments and disbursements, but no comparable planning workflow found | No clear portfolio cash-planning workflow found       | Core Phase 4 differentiator with settlement lag, purchase commitments and taxes  |
| Cash locked in ageing inventory  | Partial — inventory value/profit views  | Partial — aged/excess inventory and storage costs                     | Partial — inventory/profit views                      | Core Phase 4 portfolio measure and recovery scenario                             |

## Platform, teams and integrations

| Capability                             | Helium 10                                                            | Seller Central                                | Jungle Scout                               | SellerOS response                                                                                 |
| -------------------------------------- | -------------------------------------------------------------------- | --------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| Multiple marketplaces                  | Yes, tool-dependent                                                  | Yes                                           | Yes, tool-dependent                        | Marketplace must be explicit in every identity and integration boundary                           |
| Team access and permissions            | Yes — sub-users/tool access                                          | Yes — user permissions                        | Yes — seats/team access                    | Phase 6 RBAC; organisation isolation is already represented in the domain model                   |
| Subscription entitlements/usage limits | Yes                                                                  | Selling-plan and programme eligibility        | Yes                                        | Phase 6 plan entitlements; keep feature flags out of business calculations                        |
| Public/programmatic API                | Connected Amazon integrations; public availability varies by product | Yes — SP-API and Amazon Ads API               | Yes — selected Jungle Scout data endpoints | Define internal adapter interfaces now; implement Keepa API/SP-API only in their planned phases   |
| Exports and reports                    | Yes                                                                  | Yes                                           | Yes, plan-dependent                        | Add safe, bounded CSV/XLSX exports after primary views are stable                                 |
| Audit and explanation history          | Partial — histories and alerts                                       | Strong operational histories across workflows | Partial — histories and tracking           | SellerOS must make every score, recommendation, cost change and user-confirmed decision auditable |

## What SellerOS should emulate

- Saved filters, configurable tables and export controls for high-volume product work.
- A consistent marketplace/account context visible on every data-heavy page.
- Drill-down from portfolio KPI to product evidence without losing filters.
- Expandable product rows for quick inspection and dedicated detail pages for deeper analysis.
- Clear action states such as order now, monitor, overstock or listing issue—but based on transparent
  SellerOS rules.
- Connected workflows: research evidence should flow into economics, sourcing, inventory and
  planning without re-entering identifiers.
- Tiered disclosure: a concise recommendation first, calculations and source evidence one level
  deeper.

## What SellerOS should not emulate yet

- A browser extension, global product/keyword database or ad-management suite.
- Listing write-back, automated repricing, purchase placement or autonomous financial actions.
- Opaque opportunity, niche or listing scores.
- A large navigation catalogue containing disconnected tools.
- Market estimates presented as observed sales.

See [Platform walkthroughs](PLATFORM_WALKTHROUGHS.md) for supporting workflows and the
[SellerOS reference blueprint](SELLEROS_REFERENCE_BLUEPRINT.md) for the proposed implementation
response.
