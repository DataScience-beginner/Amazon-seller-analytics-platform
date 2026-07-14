# SellerOS Product Vision

## 1. Executive summary

SellerOS is an Amazon seller operating system. It is not only a product-research dashboard. It converts monthly Keepa exports, seller-entered costs, inventory data, pricing rules and future Amazon integrations into clear operating decisions.

The core business outcome is:

> Maximise cash conversion and annual profit while reducing dead inventory, price erosion and avoidable working-capital risk.

The first customer is the repository owner, an Amazon India seller. The architecture must nevertheless be ready to become a multi-tenant SaaS product.

## 2. The business problem

Amazon sellers currently use disconnected tools and spreadsheets for:

- product discovery;
- Keepa analysis;
- sourcing-cost calculations;
- FBA fee estimation;
- inventory planning;
- price decisions;
- supplier management;
- quarterly cash-flow forecasting;
- clearance decisions.

These tools show data, but they rarely provide a complete retail lifecycle recommendation. Sellers therefore overbuy, hold slow inventory too long, reduce prices without a strategy, or miss profitable reorder opportunities.

## 3. Product promise

For every product, SellerOS should answer:

1. Should we sell this product?
2. Which selling strategy is appropriate?
3. How many units should we test or buy?
4. What is the true landed cost and expected profit?
5. What is the minimum acceptable price?
6. When should we reorder?
7. When should we reduce the price?
8. When should we stop buying and clear stock?
9. How will this decision affect cash over 3, 6 and 12 months?

## 4. Primary data flow

Every month the seller uploads a Keepa Product Finder Excel export.

The platform must:

1. detect the workbook and header row;
2. map known Keepa columns through a configurable alias registry;
3. preserve every unknown column without data loss;
4. match products using marketplace plus ASIN;
5. create a new monthly snapshot rather than overwrite history;
6. calculate transparent scores;
7. classify products into selling strategies;
8. combine market data with seller-entered business costs;
9. create recommended actions and forecasts;
10. provide an audit trail explaining each recommendation.

Keepa exports are dynamic. Missing, renamed or newly added columns must not break the import.

## 5. Product strategies

The strategy engine may classify products as:

- **Discovery**: worth investigating, but insufficient business data exists.
- **Test Buy**: demand is promising; place a controlled trial order.
- **Growth**: demand and economics justify increasing investment.
- **Cash Cow**: stable demand, stable pricing and predictable cash generation.
- **Premium Margin**: slower velocity but attractive contribution margin.
- **Seasonal**: buy only for a defined demand window.
- **Monitor**: no immediate action; gather more monthly evidence.
- **Clearance Watch**: declining economics or excessive stock require intervention.
- **Exit**: stop reordering and liquidate responsibly.
- **Avoid**: unacceptable risk, poor economics or unreliable data.

A strategy is a business recommendation, not a permanent product attribute. It must be recalculated for each snapshot and explain the reasons.

## 6. Product scoring model

SellerOS will expose separate, explainable scores rather than one opaque number:

- Demand Score
- Competition Score
- Price Stability Score
- Profitability Score
- Cash Efficiency Score
- Inventory Risk Score
- Data Confidence Score
- Overall Opportunity Score

All formulas must be versioned. A recommendation must store the scoring-version identifier and the inputs used at calculation time.

## 7. Profitability model

The profitability engine must support:

- supplier unit price;
- supplier discount tiers;
- GST and input-tax assumptions;
- freight and inbound shipping;
- prep and packaging;
- Amazon referral fee;
- fulfilment fee;
- closing fee where applicable;
- storage fee;
- advertising allowance;
- return and damage provision;
- coupon or discount cost;
- miscellaneous overhead allocation.

Outputs:

- landed cost;
- contribution profit per unit;
- net margin;
- ROI;
- break-even price;
- minimum acceptable price;
- target price;
- expected payback period.

All monetary assumptions must be editable and auditable.

## 8. Retail lifecycle and pricing

SellerOS should treat inventory like a retail portfolio.

Lifecycle stages:

Discovery -> Test -> Growth -> Scale -> Maturity -> Decline -> Exit

Pricing recommendations must consider:

- age of stock;
- stock cover;
- current and historical Buy Box price;
- competition and seller count;
- product seasonality;
- minimum acceptable margin;
- working-capital pressure;
- competitor stock-outs;
- expected demand.

The system may propose launch, normal, accelerate, markdown and clearance prices. It must never reduce price only because time passed; market evidence and cash objectives must also support the action.

## 9. One-year product target

After one year, SellerOS should be a deployable SaaS product with:

### Market intelligence

- recurring Keepa Excel imports;
- optional Keepa API synchronisation;
- product and category history;
- price, rank, review, offer and Buy Box trends;
- configurable scoring rules.

### Business operations

- sourcing-cost database;
- suppliers and quotations;
- purchase planning;
- inventory and stock-cover planning;
- reorder recommendations;
- pricing and clearance recommendations;
- quarterly, half-yearly and annual forecasts.

### Financial intelligence

- unit economics;
- portfolio cash-flow forecast;
- working-capital requirement;
- scenario planning;
- cash locked in slow inventory;
- expected cash recovery.

### SaaS capabilities

- organisations and workspaces;
- users and role-based permissions;
- plans and usage limits;
- secure authentication;
- marketplace and currency settings;
- background jobs;
- audit logs;
- exports and notifications;
- observability and backups.

### AI advisor

The AI layer should explain calculated facts and support scenario analysis. Financial calculations, scores and hard constraints must remain deterministic and testable. AI must not invent market data or silently change numerical assumptions.

## 10. Success metrics

Business success should ultimately be measured by:

- improvement in inventory turnover;
- reduction in stock older than the configured threshold;
- reduction in cash locked in low-velocity products;
- realised contribution margin;
- forecast accuracy;
- percentage of recommendations accepted;
- reorder success rate;
- clearance loss avoided;
- time saved compared with spreadsheet analysis.

## 11. Non-goals for the first MVP

The first MVP will not include:

- automated Amazon price changes;
- automatic purchase-order placement;
- autonomous financial decisions;
- payment subscriptions;
- complete Amazon SP-API integration;
- machine-learning demand forecasting.

The MVP must first prove reliable import, scoring, strategy, profitability and planning workflows using monthly Keepa files.