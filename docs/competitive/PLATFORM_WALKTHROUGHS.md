# Helium 10, Amazon Seller Central and Jungle Scout walkthroughs

This document describes the current public product surfaces and seller workflows of three reference
platforms. It focuses on behavior useful to SellerOS product and engineering decisions. It does not
claim access to their private implementation.

Research checked: **2026-07-19**

## 1. Helium 10

### 1.1 Product role and surfaces

Helium 10 is a multi-tool research, optimization, analytics and operations suite layered over
Amazon and selected other channels. Its current product menu supports a goal-oriented Solutions
view and a tool-name Classic view. The main surfaces are:

- web command center and specialized tools;
- Chrome extension embedded into marketplace browsing;
- iOS/Android companion for monitoring and limited actions;
- connected Amazon Seller and Advertising account data;
- read-only MCP access for supported AI clients on eligible plans.

Sources: [official tool index](https://www.helium10.com/tools/),
[current product-menu guide](https://kb.helium10.com/hc/en-us/articles/44522416225051-Where-Are-My-Tools-The-Products-Menu-Classic-and-Solutions-Overview),
[mobile guide](https://kb.helium10.com/hc/en-us/articles/47438277453595-Helium-10-Mobile-App-Complete-Feature-Guide-Detailed-Navigation-Walkthrough-iOS-Android),
[MCP guide](https://kb.helium10.com/hc/en-us/articles/51580564409883-Getting-Started-with-Helium-10-MCP).

### 1.2 Typical seller journey

1. Connect an Amazon seller account and, separately, an advertising profile where needed.
2. Select account, marketplace and date context.
3. Discover products/niches through Black Box or inspect live Amazon results with Xray.
4. Save candidates to lists or Product Launchpad and compare competitors.
5. Discover keywords in the unified Cerebro surface, then clean and organize keyword sets.
6. Analyze or build a listing and optionally synchronize supported fields to Amazon.
7. Track keywords, products, competitors and market movement.
8. Add COGS and supplier/inventory assumptions to unlock profit and replenishment views.
9. Review insights, alerts, advertising suggestions, reimbursement candidates and customer
   follow-up queues.

The important pattern is cross-tool continuation: a selected ASIN, marketplace, competitor or
keyword set can move into another workflow instead of being re-entered.

### 1.3 Home and insights

The Insights Dashboard combines account KPIs, charts and a configurable My Products table. Public
documentation describes revenue, profit, orders, refunds, advertising and product views with
period comparison, alerts, keyword/inventory summaries, export and deep links to analysis tools.
Product rows can expand into keywords, alerts and inventory. Insight cards expose impact, details,
an action link and completion/deletion handling.

Inputs:

- connected account/profile and marketplace;
- date range and product selection;
- seller-entered COGS;
- PPC connection for advertising fields;
- tracked keywords and alert settings.

Outputs:

- KPI cards and comparative trends;
- product-level net profit when cost data exists;
- impact-ranked insights and alerts;
- quick product evidence and cross-tool actions;
- Excel export.

Sources: [Insights setup](https://kb.helium10.com/hc/en-us/articles/13836165722395-Getting-Started-with-Insights-Dashboard),
[dashboard graphs](https://kb.helium10.com/hc/en-us/articles/13837251378331-Insights-Dashboard-Graphs),
[My Products](https://kb.helium10.com/hc/en-us/articles/13838311787419-My-Products-Insights-Dashboard),
[Insights queue](https://kb.helium10.com/hc/en-us/articles/13837186083867-Insights).

### 1.4 Product and niche research

Black Box is the primary database research surface. It supports product, keyword, Amazon Brand
Analytics, competitor, niche, product-targeting and specialist workflows. Product search supports
marketplace/category, simple or advanced filters, saved presets, sortable results, bulk identifiers,
lists and export. Publicly documented result fields include product identity, dimensions,
fulfillment, age, price, estimated sales/revenue, ratings and trends.

Product Launchpad organizes an idea around keywords, competitors and an idea scorecard. The Chrome
extension adds Xray result tables, niche aggregates, history graphs, profitability calculations,
inventory estimates and listing widgets directly to Amazon browsing.

Inputs:

- marketplace, categories and subcategories;
- price, size, competition, sales/revenue, review and fulfilment filters;
- seed ASINs/keywords or bulk identifiers;
- seller-entered dimensions and costs for profitability.

Outputs:

- filterable/sortable research results;
- estimated opportunity and trend measures;
- saved products/presets and exports;
- related product targets and competitor sets;
- deep links to keyword, listing and profit workflows.

Sources: [Black Box overview](https://kb.helium10.com/hc/en-us/articles/360034015153-Tutorial-Navigating-the-Black-Box-Dashboard),
[2026 Product tab](https://kb.helium10.com/hc/en-us/articles/6710274045339-Black-Box-Product-Tab-Overview),
[tab purposes](https://kb.helium10.com/hc/en-us/articles/4406553685147-How-Are-the-Different-Tabs-in-Black-Box-Used-for-Product-Research),
[Product Launchpad](https://kb.helium10.com/hc/en-us/articles/32602915902235-Product-Launchpad-Intro-and-Overview),
[Xray](https://kb.helium10.com/hc/en-us/articles/360048281774-How-Do-I-Set-Up-and-Navigate-Xray).

### 1.5 Keyword research

Helium 10 merged Magnet into Cerebro in January 2026. Current workflows combine seed-keyword
discovery, reverse-ASIN research and competitor comparison in one surface. The UI supports pasted,
uploaded or saved keyword sets, quick/advanced filters, configurable columns, word-frequency
analysis, histories and export.

Common outputs include search volume/history, keyword sales estimates, competing-product count,
title density, sponsored presence, organic/sponsored/recommended rank, Amazon Brand Analytics
shares where eligible and tool-specific opportunity metrics.

Sources: [Magnet/Cerebro merger](https://kb.helium10.com/hc/en-us/articles/44262552100891-Magnet-Has-Been-Merged-Into-Cerebro-Everything-You-Need-to-Know),
[current keyword analysis](https://kb.helium10.com/hc/en-us/articles/44519579661211-How-to-Analyze-Keywords-Using-Cerebro-Plus-Magnet),
[reverse-ASIN workflow](https://kb.helium10.com/hc/en-us/articles/360046326894-How-Do-I-Use-Cerebro).

### 1.6 Listing optimization

The listing toolchain is progressive:

- Keyword Processor cleans, deduplicates, analyzes and exports large keyword lists.
- Scribbles shows keyword popularity/usage while the seller edits listing sections.
- Listing Builder combines a keyword bank, competitor research, listing fields, optional AI
  generation and connected-listing synchronization.
- Listing Analyzer compares a main ASIN with competitors and reports listing, sales, rank, traffic
  and conversion evidence where available.
- Index Checker evaluates whether an ASIN is indexed for supplied terms.

Listing synchronization exposes processing/synced/error states because Amazon performs final
processing asynchronously.

Sources: [Keyword Processor](https://kb.helium10.com/hc/en-us/articles/360034474954-How-to-Use-Keyword-Processor),
[Scribbles](https://kb.helium10.com/hc/en-us/articles/360034588014-How-to-Optimize-Your-Product-Listings-Using-Ranking-Keywords-in-Scribbles),
[Listing Builder](https://kb.helium10.com/hc/en-us/articles/4407213995419-Listing-Builder-Keyword-Research-Revamped-AI-Listing-Generation),
[listing synchronization](https://kb.helium10.com/hc/en-us/articles/4407261160347-What-Do-I-Need-to-Know-to-Successfully-Sync-My-Listing-with-Amazon),
[Listing Analyzer](https://kb.helium10.com/hc/en-us/articles/1260804050970-How-Do-I-Use-the-Helium-10-Listing-Analyzer),
[Index Checker](https://kb.helium10.com/hc/en-us/articles/360034828174-How-to-Use-Index-Checker-to-ID-Which-Words-Amazon-Indexes-for-a-Product).

### 1.7 Analytics and tracking

- Profits combines connected sales, fees, refunds and advertising with manually maintained COGS to
  show account/product P&L and margin views.
- Keyword Tracker stores ASIN-keyword monitoring, rank history, notes, tags and competitor
  comparisons.
- Market Tracker monitors a defined competitive set and reports price, review, rank, estimated
  sales/revenue and market-share changes.
- Search Query Analyzer combines Amazon query-funnel data with keyword/rank measures for eligible
  brand accounts.
- Review Insights uses Amazon customer-feedback data to summarize topics, changes and impact.

Sources: [Profits](https://kb.helium10.com/hc/en-us/sections/360005091973-Profits),
[COGS workflow](https://kb.helium10.com/hc/en-us/articles/47393301572891-Profits-How-to-Add-or-Update-Cost-of-Goods-Sold-COGS),
[Keyword Tracker](https://kb.helium10.com/hc/en-us/articles/360036302794-How-Do-I-Navigate-the-Keyword-Tracker-Dashboard),
[Market Tracker](https://kb.helium10.com/hc/en-us/articles/360044672854-How-Do-I-Track-My-Competition-Using-Helium-10-s-Market-Tracker),
[Search Query Analyzer](https://kb.helium10.com/hc/en-us/articles/35108027467675-How-to-Use-the-Search-Query-Analyzer),
[Review Insights](https://kb.helium10.com/hc/en-us/articles/48006601967643-Review-Insights-Analyze-Customer-Feedback-with-Amazon-Data).

### 1.8 Operations and marketing

Inventory Management joins Amazon inventory/sales history to seller-entered supplier, cost, lead
time, reorder frequency, MOQ, case pack and local stock inputs. It returns days of supply, reorder
date/units/cost, suppliers, purchase orders and inbound shipment status. Purchase orders move
through explicit direct-to-Amazon or local-warehouse states and ultimately hand inbound work to
Seller Central.

Other operational surfaces include:

- Alerts for Buy Box, seller, price, dimension, title, category and rating changes;
- Follow-Up for policy-constrained review requests and messaging sequences;
- Refund Genie and a managed service for potential FBA reimbursement recovery;
- Portals for landing pages, tracked links, QR codes and lead analytics;
- Helium 10 Ads for campaign tables, bid/budget edits, rules, suggestions and guarded automation.

Seller Assistant is not a current capability: an official June 2026 notice says it was
discontinued, despite stale references on older pages.

Sources: [inventory overview](https://kb.helium10.com/hc/en-us/articles/360057872533-Inventory-Management-PRO-Training-An-Introduction-and-Overview),
[reorder calculation inputs](https://kb.helium10.com/hc/en-us/articles/360060376193-How-Does-the-Helium-10-Inventory-Manager-Calculate-My-Restock-Recommendations),
[purchase orders](https://kb.helium10.com/hc/en-us/articles/1260801111489-How-Do-I-Create-and-Manage-Purchase-Orders-in-Inventory-Management),
[Alerts](https://kb.helium10.com/hc/en-us/articles/360037349253-How-Do-I-Activate-Alerts-for-My-Amazon-Products),
[Follow-Up](https://kb.helium10.com/hc/en-us/articles/52858656680859-How-to-Automate-and-Manually-Send-Amazon-Review-Requests-in-Follow-Up),
[Refund Genie](https://kb.helium10.com/hc/en-us/articles/360037645153-How-Do-I-Navigate-the-Refund-Genie-Dashboard),
[Ads rules](https://kb.helium10.com/hc/en-us/articles/18076439623963-Helium-10-Ads-Rules-Automation),
[Seller Assistant discontinuation](https://kb.helium10.com/hc/en-us/articles/51588628437531-Helium-10-Chrome-Extension-Seller-Assistant-Important-Update-for-Users).

### 1.9 UI patterns

- persistent account/marketplace/date context;
- KPI cards, comparison charts and dense tables in a repeatable page anatomy;
- configurable/reorderable columns, saved presets and export;
- row expansion and detail drawers for fast inspection;
- filter chips, search, checkbox selection and bulk actions;
- recommendation queues with impact, explanation, action and completion state;
- processing/synced/error states for asynchronous work;
- cross-tool deep links preserving ASINs and keyword sets;
- plan locks, limits and usage meters displayed in context.

### 1.10 Architectural inference

The following are plausible enabling capabilities, not claims about Helium 10's code:

- tenant identity, sub-user permissions, subscriptions, entitlements and usage metering;
- encrypted connector/token management for Seller, Ads and other channels;
- a canonical account/marketplace/product/SKU/keyword/advertising/inventory model;
- separate global research intelligence and tenant-owned operational data;
- time-series storage and materialized daily/weekly aggregates;
- asynchronous search, synchronization, report, export and AI jobs;
- generic table/filter/saved-view/report schemas shared across tools;
- rule/scheduler/change-ledger services for advertising and operational workflows;
- notification routing across in-app, email, SMS and push;
- curated read-only APIs behind web, extension, mobile and MCP clients.

### 1.11 Availability caveats

Plan, marketplace, Brand Registry and account connections change feature access. The official
pricing and entitlement pages should be checked at decision time. Current official pages also
contain stale or conflicting details, so SellerOS must not hard-code competitor limits. The
important current changes are the Cerebro/Magnet merger, Seller Assistant discontinuation and
read-only MCP launch.

Sources: [pricing](https://www.helium10.com/pricing/),
[detailed plan entitlements](https://kb.helium10.com/hc/en-us/articles/1260803831790-Which-Helium-10-Plan-Is-the-Right-One-for-Me),
[market support](https://kb.helium10.com/hc/en-us/articles/360036359334-Which-Tools-Are-Supported-in-Which-Markets).

## 2. Amazon Seller Central

### 2.1 Product role and access model

Seller Central is the system of record for an Amazon selling account. Its public overview covers
listing, pricing, FBA/FBM fulfillment, orders, returns, advertising, payments, performance,
programs, settings and support. The visible product depends on marketplace, Individual/Professional
plan, user permissions, FBA/Ads enrollment, brand relationship and Amazon experiments.

Source: [Seller Central overview](https://sell.amazon.com/tools/seller-central).

### 2.2 Typical seller journey

1. Register/verify the business and configure bank, card, tax, shipping, return and notification
   settings.
2. Invite users and assign permissions.
3. Match an offer to an existing ASIN or create a new catalogue item/listing.
4. Set price, quantity, condition and FBA/FBM fulfilment.
5. For FBA, prepare/send inventory and monitor receiving; for FBM, manage order shipment directly.
6. Process orders, cancellations, returns, refunds and permitted buyer communication.
7. Review sales, fees, transactions, settlements and disbursements.
8. Resolve listing, inventory, customer-experience and account-health exceptions.
9. Use advertising, promotions, Brand Registry and growth tools where eligible.

### 2.3 Catalogue and listings

Amazon separates the shared product detail page from a seller-specific offer. A documented listing
workflow searches the catalogue by identifier/name/keyword, matches or creates a product, gathers
product-type-dependent identity, content, facts, offer and compliance data, then validates and
submits it. Bulk upload provides templates and processing feedback; Manage All Inventory becomes
the operational listing/offer grid.

Inputs:

- marketplace, product type, GTIN/ASIN and seller SKU;
- brand, product facts, variation structure and compliance declarations;
- title, bullets, description, search terms and media;
- price, quantity, condition and fulfilment channel.

Outputs:

- catalogue/ASIN relationship and seller offer;
- draft, active, inactive, incomplete or suppressed status;
- validation issues, restrictions and approval actions;
- bulk processing report.

Public APIs form a composable listing stack: Catalog Items, Product Type Definitions, Listings
Restrictions, Listings Items, Feeds, Notifications and Reports. Submission acceptance can be
synchronous while catalogue processing remains asynchronous.

Sources: [listing walkthrough](https://sell.amazon.com/blog/amazon-product-listings),
[listing lifecycle/API guide](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/manage-product-listings-guide),
[workflow guide](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/building-listings-management-workflows-guide).

### 2.4 Inventory, FBA and inbound

Manage All Inventory handles listing availability and merchant quantities. FBA adds the FBA
Dashboard, FBA Inventory, Inventory Performance, Shipping Queue and Send to Amazon. Inventory is
shown in operational buckets and exception states, including fulfilable, inbound, reserved,
unfulfillable, ageing, excess and stranded. Seller Central documents days of supply, sell-through,
fees, restock suggestions and IPI.

Send to Amazon captures source, SKUs/quantities, packing, placement, transport, labels and tracking,
then follows multiple shipments through receiving.

Public integration surfaces include FBA Inventory, Fulfillment Inbound, Listings/Feeds,
Replenishment and extensive inventory reports.

Sources: [FBA inventory](https://sell.amazon.com/fulfill.html),
[FBA Inventory tool](https://sell.amazon.com/es/blog/fba-inventory),
[Send to Amazon](https://sell.amazon.com/blog/send-to-amazon-shipment-creation),
[FBA Inventory API](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/fba-inventory-api),
[Fulfillment Inbound API](https://developer-docs.amazon.com/sp-api/docs/fulfillment-inbound-api).

### 2.5 Orders, fulfillment, returns and messaging

Manage Orders is a status-filtered queue covering pending, unshipped, cancelled and shipped orders.
For FBM, the seller picks/packs, purchases or records shipping, confirms shipment, then handles
cancellations, returns, refunds and buyer requests. FBA delegates most physical fulfilment and
customer service while retaining visibility.

Public interfaces include the Orders API, order-change notifications, Shipping API, selected
messaging/solicitation actions and reports. Sensitive buyer/address data uses restricted roles; not
every UI action has a general write API.

Sources: [order management](https://sell.amazon.com/blog/amazon-order-management),
[Orders API](https://developer-docs.amazon.com/sp-api/docs/orders-api),
[order information](https://developer-docs.amazon.com/sp-api/docs/get-order-information).

### 2.6 Pricing, promotions and fees

Sellers can edit prices manually or assign products to Automate Pricing rules. Documented rules
cover competitive, sales-based and business-price behavior with mandatory minimum and optional
maximum boundaries. The workflow exposes rule/product status and repricing history. Deals, Coupons
and Promotions are separate merchandising tools.

The Product Pricing API exposes competitive/offer/reference data, notifications can signal offer or
pricing-health changes, Listings/Feeds can submit price updates, and Product Fees returns estimates.
Amazon does not document a general API for configuring its native Automate Pricing rules.

Sources: [Automate Pricing](https://sell.amazon.com/tools/automate-pricing),
[Product Pricing API](https://developer-docs.amazon.com/sp-api/lang-en_EN/reference/product-pricing-v2022-05-01),
[Product Fees API](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/product-fees-api).

### 2.7 Advertising

Amazon Ads/Campaign Manager is a related but separately authorized system. Sponsored Products
captures products, targeting, negatives, bids, budget and schedule, then reports impressions,
clicks, CPC, spend, attributed orders/sales and ACoS/ROAS. Sponsored Brands and display capabilities
add creative/destination and eligibility requirements. Reporting and campaign APIs belong to the
Amazon Ads platform, not SP-API; Marketing Stream can provide hourly metrics/change data.

Sources: [Sponsored Products](https://advertising.amazon.com/solutions/products/sponsored-products),
[Sponsored Brands](https://advertising.amazon.com/solutions/products/sponsored-brands),
[Marketing Stream](https://advertising.amazon.com/library/guides/amazon-marketing-stream).

### 2.8 Reports, analytics, payments and fees

Business Reports use date/channel filters, comparison charts and by-date/by-ASIN tables for sales,
units, traffic, conversion and Featured Offer metrics, with CSV download. Payments provides balance,
transactions, fees, refunds, reserves, settlements and disbursements with drill-through.

Public integrations include asynchronous Reports jobs/documents, Data Kiosk queries and the
Finances API. Amazon warns that report fields and formats evolve—directly validating SellerOS's
requirement for schema-tolerant parsers and raw preservation.

Sources: [Business Reports](https://sell.amazon.com/blog/amazon-business-reports),
[seller payments](https://sell.amazon.com/blog/amazon-seller-payments),
[Reports API](https://developer-docs.amazon.com/sp-api/lang-tr_TR/docs/reports-api-v2021-06-30-use-case-guide),
[report types](https://developer-docs.amazon.com/sp-api/lang-US/docs/report-type-values),
[Finances API](https://developer-docs.amazon.com/sp-api/docs/finances-api-faq).

### 2.9 Performance, customer experience and account health

Account Health combines a rating, policy issues, performance rates, alerts and remediation paths.
Adjacent tools include Feedback Manager, Voice of the Customer, Customer Reviews, return insights
and Request a Review. Public API coverage is narrower than the UI: reports and Customer Feedback
provide selected data, while the full Account Health remediation experience is not generally
exposed.

Sources: [policy and Account Health](https://sell.amazon.com/blog/selling-policies),
[Customer Reviews](https://sell.amazon.com/tools/customer-reviews),
[Customer Feedback API](https://developer-docs.amazon.com/sp-api/docs/customer-feedback-api-v2024-06-01-use-case-guide).

### 2.10 Brand and growth tools

Brand Registry unlocks varying combinations of A+ Content, Stores, Brand Analytics, experiments,
Vine, Customer Reviews, brand promotions, bundles, Attribution and protection tools. Brand
Analytics documents search/customer-journey/loyalty/repeat-purchase/demographic/market-basket
dashboards. Manage Your Experiments tests content variants and reports probabilistic and projected
commercial impact.

Other important discovery/growth modules include Product Opportunity Explorer and Growth
Opportunities, which surface demand evidence and prioritized recommended actions.

Sources: [Brand Registry](https://sell.amazon.com/brand-registry),
[Brand Analytics](https://sell.amazon.com/tools/amazon-brand-analytics),
[Manage Your Experiments](https://sell.amazon.com/tools/manage-your-experiments),
[Product Opportunity Explorer](https://sell.amazon.com/tools/product-opportunity-explorer),
[Growth Opportunities](https://sell.amazon.com/tools/growth-opportunities).

### 2.11 Accounts, permissions and integrations

Settings include business/payment/tax identity, shipping/returns, notifications, login/security,
users and programme configuration. User Permissions, Brand Registry roles and authorized
service-provider roles are distinct. Public SP-API applications use authorization scopes/roles and
OAuth, with restricted roles for sensitive data and reauthorization requirements.

The current SP-API reference spans catalogue, listings, inventory, inbound/outbound fulfillment,
orders, reports, finances, fees, pricing, feedback, notifications and other domains.

Sources: [SP-API index](https://developer-docs.amazon.com/sp-api/lang-US/reference/welcome-to-api-references),
[SP-API overview](https://developer-docs.amazon.com/sp-api/docs/what-is-the-selling-partner-api),
[service-provider authorization](https://developer-docs.amazon.com/sp-api/lang-US/docs/learn-how-sellers-authorize-service-providers).

### 2.12 UI patterns

- summary dashboard leading to specialist workspaces;
- entitlement-driven navigation;
- dense inventory/listing/order/payment grids with filters and bulk actions;
- explicit operational statuses and exception queues;
- step-by-step setup and inbound wizards;
- downloadable processing/error reports;
- recommendation cards linked to one-click or guided action;
- detail drill-through from KPI to transaction/order/listing;
- support, help and policy context close to high-risk actions.

### 2.13 Architectural inference

The following are product-derived inferences, not claims about Amazon internals:

- separate catalogue item, seller listing, offer and product-type schema services;
- event/ledger-based inventory and financial models;
- state machines for listings, inbound shipments, orders, returns and compliance cases;
- schema-versioned file/API ingestion with raw records and row issues;
- asynchronous jobs and notifications with idempotent reconciliation;
- role/program/marketplace entitlement service and protected PII projections;
- rules/recommendation engine with reason and projected impact;
- operational store plus analytics/reporting projections;
- full audit history across business-critical mutations.

The most reusable pattern is **summary → filtered work queue → detail → recommended action →
status/history**, not Seller Central's menu density.

## 3. Jungle Scout

### 3.1 Product role and surfaces

Jungle Scout currently distinguishes Catalyst for sellers, Cobalt for enterprise/brand market
intelligence and an MCP product for conversational access to supported Cobalt data. Seller-facing
work primarily uses the Catalyst web application and browser extension, with connected Seller
Central data unlocking operational analytics.

Sources: [platform comparison](https://support.junglescout.com/hc/en-us/articles/37123724151319-Choosing-the-Right-Jungle-Scout-Platform-Catalyst-Cobalt-MCP),
[tool overview](https://support.junglescout.com/hc/en-us/articles/360008616534-Jungle-Scout-Tools).

### 3.2 Typical seller journey

1. Select a marketplace and discover products or keyword-defined niches.
2. Validate candidates in the extension and Product Tracker over time.
3. Research keywords and competitor rankings.
4. Analyze/build listing content and track keyword rank.
5. Find and monitor suppliers and sourcing evidence.
6. Connect Seller Central to import products, sales, fees, ads and inventory.
7. Enter COGS/logistics assumptions and review profit/inventory/reorder views.
8. Monitor advertising, reimbursements, competitive intelligence and review automation where
   plan/account access permits.

### 3.3 Product and niche research

The Product Database filters Amazon catalogue candidates by marketplace/category and measures such
as price, net revenue, rank, reviews, estimated demand and listing quality. Search presets can be
saved. Opportunity Finder starts from keyword-defined niches and filters demand, price, search
volume/trend, competition, seasonality and a tool-specific niche score. Product Tracker persists
candidates and trend history; Category Trends adds category-level discovery. The extension validates
current Amazon result pages and adds embedded data/history.

Inputs:

- marketplace and category;
- product/financial/demand/competition/review filters;
- include/exclude terms and brands;
- candidate ASINs and groups.

Outputs:

- configurable candidate/niche result tables;
- estimated sales, revenue and opportunity measures;
- saved searches/products and historical tracking;
- export where entitled;
- continuation to supplier, keyword and listing workflows.

Product Tracker is the persistence layer for candidate validation: marketplace-specific groups,
notes, customizable columns and rolling daily price/sales/rank trends. Newly tracked products can
show an explicit collection delay rather than fabricated history. Category Trends exposes a
category/date view of leading products, while the Sales Estimator turns category plus BSR into a
quota-metered monthly-sales estimate. The browser extension adds customizable research cards,
historical graphs and one-click hand-offs on Amazon pages.

Sources: [Product Database](https://support.junglescout.com/hc/en-us/articles/360008616554-How-to-use-the-Product-Database),
[Opportunity Finder](https://support.junglescout.com/hc/en-us/articles/360037689513-Opportunity-Finder),
[Product Tracker](https://support.junglescout.com/hc/en-us/articles/360008769073-Product-Tracker-Viewing-Organizing-your-Tracked-Products),
[Category Trends](https://support.junglescout.com/hc/en-us/articles/1500005246661-Category-Trends),
[extension](https://www.junglescout.com/features/extension/),
[research tool index](https://support.junglescout.com/hc/en-us/categories/9708786011415-Research-Optimization-Tools).

### 3.4 Keywords and listings

Keyword Scout supports keyword, single-ASIN and multi-ASIN research with marketplace-specific
results. Public columns include search demand, trends, ranking difficulty, organic product count,
PPC-related measures and connected-campaign context. Keyword lists organize selected terms; Rank
Tracker follows ASIN/keyword positions.

Listing Analyzer and its in-house Listing Quality Score assess listing content and reviews.
Listing Builder combines keywords with structured listing fields and optional AI assistance.
Its documented states include draft, queued, syncing, synced and retry, making Amazon publication
an explicit asynchronous workflow. AI-generated fields remain reviewable and replaceable rather
than being silently published.

Sources: [Keyword Scout](https://support.junglescout.com/hc/en-us/articles/360008770253-Keyword-Scout),
[Keyword Scout columns](https://support.junglescout.com/hc/en-us/articles/360048778674-Keyword-Scout-columns),
[Rank Tracker](https://support.junglescout.com/hc/en-us/articles/360037532674-Adding-Products-in-the-Rank-Tracker),
[Listing Builder](https://support.junglescout.com/hc/en-us/articles/360012629154-Listing-Builder),
[AI Assist](https://support.junglescout.com/hc/en-us/articles/14125467234583-AI-Assist-in-Listing-Builder),
[Jungle Scout help index](https://support.junglescout.com/hc/en-us).

### 3.5 Suppliers and sourcing

Supplier Database searches suppliers/manufacturers and trade records by product, company,
competitor or supplier. Supplier Tracker persists candidates and notes/history. Public help also
documents shipment history, HS codes, quotes, samples and purchase-order agreements. The source is
described as US customs import records. This is a broader sourcing-data surface than either Seller
Central or the reviewed Helium 10 core suite.

For SellerOS, the transferable pattern is a product-linked supplier comparison and workflow—not a
global supplier/trade database in the MVP.

Sources: [Supplier Database](https://support.junglescout.com/hc/en-us/articles/360019317034-Supplier-Database-Feature-Overview),
[shipment history](https://support.junglescout.com/hc/en-us/articles/360019477353-Supplier-Shipping-History),
[Supplier Tracker](https://support.junglescout.com/hc/en-us/articles/360020394834-Supplier-Tracker-Feature-Overview).

### 3.6 Sales, profit and inventory

Connecting Seller Central unlocks Product Costs & Settings, Profit Overview/Sales Analytics,
inventory, advertising and reimbursement features by plan. Seller-entered COGS and logistics
settings combine with connected marketplace activity.

Inventory Manager reports product status such as Order Now, Reorder Soon, Overstock and In Stock,
then recommends date/quantity and presents expected costs/profit. Public documentation says it uses
real-time FBA inventory plus demand forecasting and seller settings.

Profit Overview and P&L views combine Amazon sales/fees with effective-dated costs and manually
entered other income/expense. The UI supports company or product scope, date comparison, KPI cards,
cost breakdown and a ledger-like waterfall. AI Profit Analysis is a separately documented
summarization/reporting layer over selected financial data, not a replacement for those calculations.

Sources: [Inventory Manager](https://support.junglescout.com/hc/en-us/articles/360038089014-Inventory-Manager),
[Product Costs & Settings](https://support.junglescout.com/hc/en-us/articles/360035714594-Product-Costs-Settings),
[Profit Overview](https://support.junglescout.com/hc/en-us/articles/360036200053-Analytics-Performance-Profit-Overview),
[P&L](https://support.junglescout.com/hc/en-us/articles/8822869933719-P-L-Profit-Loss-Statement),
[plan capability summary](https://support.junglescout.com/hc/en-us/articles/26264588139799-Information-about-our-Membership-Plans),
[Help Center business-performance index](https://support.junglescout.com/hc/en-us).

### 3.7 Marketing, advertising and competitive intelligence

The reviewed suite publicly documents:

- Review Automation using connected eligible orders;
- Ads Analytics and PPC optimization integrations;
- FBA reimbursements and other-transaction views;
- Competitive Intelligence for higher-tier brand/market-share analysis;
- a public data API for selected product, keyword, sales-estimate, history and share-of-voice uses;
- MCP for eligible Cobalt data access.

These features depend strongly on plan and account connections.

Ads Analytics documents KPI cards, organic-versus-ad sales, cost/profit waterfalls and switchable
campaign/ad group/keyword/search-term tables. Review Automation uses Amazon's own Request a Review
mechanism with explicit Scheduled, Requested, Skipped, Ineligible, Refunded and Amazon Issue states.
FBA reimbursement handling is currently documented as a partner workflow with Carbon6 rather than
only a Jungle Scout calculation.

Sources: [Help Center index](https://support.junglescout.com/hc/en-us),
[Ads Analytics](https://support.junglescout.com/hc/en-us/articles/5471703345687-Ads-Analytics),
[Review Automation](https://support.junglescout.com/hc/en-us/articles/360055244714-Review-Automation),
[FBA Reimbursements](https://support.junglescout.com/hc/en-us/articles/16965376324119-FBA-Reimbursements),
[current platform comparison](https://support.junglescout.com/hc/en-us/articles/37123724151319-Choosing-the-Right-Jungle-Scout-Platform-Catalyst-Cobalt-MCP).

### 3.8 Public API and data access

Catalyst documents API-key management, usage/quota tracking, pagination and selected endpoints for
keywords by keyword/ASIN, historical search volume, Product Database, sales estimates and Share of
Voice. Zapier is documented as a client. The API is a metered product surface rather than unrestricted
access to every web feature.

Sources: [endpoint descriptions](https://support.junglescout.com/hc/en-us/articles/21641823937943-API-Endpoint-Descriptions),
[API keys and quotas](https://support.junglescout.com/hc/en-us/articles/21534064295447-How-to-Access-the-API-and-Generate-API-keys),
[Zapier](https://support.junglescout.com/hc/en-us/articles/23913780321431-How-to-Use-the-Jungle-Scout-API-with-Zapier).

### 3.9 Cobalt enterprise reference

Cobalt is intentionally different from Catalyst. It targets established brands, retailers and
agencies with category/brand/portfolio intelligence and richer delivery/integration options;
Catalyst's Listing Builder, Listing Analyzer and Review Automation are not described as Cobalt
features.

Current public Cobalt modules include:

- Executive Overview joining eligible Seller/Vendor, category, keyword and advertising context;
- configurable multi-tab dashboards with charts/tables, filters, sharing and export;
- Market Analysis for category/brand/product/attribute/price-band movement, currently documented
  with beta/market limitations;
- Product Catalog combining portfolio sales, traffic, ads and offer/Buy Box evidence;
- Seller Compliance for authorized/unauthorized seller and Buy Box impact monitoring;
- Shelf Intelligence and Share of Voice with tracked keyword/device/market contracts;
- keyword lists/research and reverse-ASIN analysis;
- advertising automation and Amazon Marketing Stream options by contract;
- API, Data Cloud and MCP delivery for programmatic, BI and conversational use.

This suggests a useful future separation: SellerOS's core seller operating workflows should not be
coupled to a later enterprise market-intelligence/data-delivery tier.

Sources: [Cobalt overview](https://www.junglescout.com/products/cobalt/),
[Executive Overview](https://cobaltjs.zendesk.com/hc/en-us/articles/35920131632279-Executive-Overview-Feature-Overview),
[custom dashboards](https://cobaltjs.zendesk.com/hc/en-us/articles/14401538800535-Dashboards-Feature-Overview),
[Market Analysis](https://cobaltjs.zendesk.com/hc/en-us/articles/39612710002071-Market-Analysis-Feature-Overview),
[Product Catalog](https://cobaltjs.zendesk.com/hc/en-us/articles/31971443766039-Product-Catalog-Feature-Overview),
[Seller Compliance](https://cobaltjs.zendesk.com/hc/en-us/articles/39937094504471-Seller-Compliance-Feature-Overview),
[Shelf Intelligence](https://cobaltjs.zendesk.com/hc/en-us/articles/14132063212439-Shelf-Intelligence-Feature-Overview).

### 3.10 UI patterns

- left navigation grouped by seller goal;
- marketplace dropdown at the beginning of research workflows;
- broad filter panels and saved presets;
- dense sortable/configurable result tables;
- product groups/trackers carrying candidates between workflows;
- extension overlays and historical product graphs;
- status-oriented inventory dashboard;
- Seller Central connection as progressive activation of business features;
- plan-based historical windows, query/tracking limits and locked capabilities.

### 3.11 Architectural inference

The following are plausible capabilities, not claims about Jungle Scout's private implementation:

- global marketplace product/keyword/supplier intelligence stores separated from tenant data;
- estimation and scoring pipelines with historical snapshots;
- Seller Central connector, backfill/sync jobs and freshness metadata;
- tenant product-cost, inventory-setting and supplier-workspace services;
- time-series product/keyword/inventory/profit aggregates;
- saved searches, trackers, groups and export jobs;
- forecasting/reorder service with product status classification;
- entitlement/usage service controlling queries, history windows, exports, seats and features;
- public API/MCP gateways over curated read-only capabilities.

### 3.12 Availability caveats

Marketplace, subscription, connected-account and brand access affect results and history. Official
sources can conflict—for example, current Jungle Scout material has presented inconsistent seat
counts for the same plan. Do not hard-code pricing or plan limits from this research; verify the
live checkout/contract when commercial decisions depend on them.

Sources: [membership plans](https://support.junglescout.com/hc/en-us/articles/26264588139799-Information-about-our-Membership-Plans),
[pricing](https://www.junglescout.com/pricing/).

## 4. Cross-platform conclusions

### Shared strengths

- consistent marketplace/account context;
- data-heavy filtering and customizable tables;
- saved products, searches or tracked groups;
- current summary joined to historical trends;
- workflow links that retain selected identifiers;
- progressive activation after connecting Amazon;
- action/exception queues and status histories;
- exports and plan-aware usage limits.

### Gaps SellerOS can own

- a deterministic, transparent strategy for every product rather than an isolated opportunity
  score;
- explicit separation of imported market evidence and seller-owned costs/inventory;
- product lifecycle from discovery through exit;
- markdown/clearance advice constrained by minimum acceptable economics;
- test-buy and reorder scenarios constrained by working capital;
- integrated quarterly, half-yearly and annual cash planning;
- full trace from source evidence through formula/recommendation to user decision and outcome.

### Product warning

A broad “toolbox” clone would dilute SellerOS. The next milestone should remain reliable Keepa
ingestion, transparent scoring, strategy and product evidence. Keyword, listing, ad, review,
extension and automation suites can be reconsidered only after the core cash-conversion loop proves
valuable.
