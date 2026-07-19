# Phase 2 Economics and Sourcing Contracts

This document is the reviewable contract for SOS-401, SOS-402, SOS-501 and SOS-502. All endpoints
are under `/api/v1` and require explicit `organisation_id` and `marketplace_id` query parameters.
An opaque product, offer or profile identifier never substitutes for tenant scope.

## Financial input contract

Financial values use `Decimal`; the UI sends decimal strings and binary JSON floats are rejected.
Currency is an explicit three-letter code. Cost profiles, supplier quotations and budgets must use
the selected marketplace currency until a versioned FX policy exists; SellerOS never infers or
converts currency.

`POST /cost-profiles` creates a new revision. It never edits imported market evidence and never
replaces an earlier revision's business inputs. `product_id` selects a product profile; `null`
creates the organisation-owned default for that marketplace.

The request records:

- GST-exclusive purchase cost, GST rate and recoverable input-GST share;
- whether the observed selling price is GST-inclusive or GST-exclusive;
- freight, prep, packaging and per-unit overhead;
- advertising and return/damage percentages;
- optional referral, fulfilment, closing and storage fees;
- minimum and target margin policy;
- explicit currency and UTC `effective_from` timestamp; and
- fee source, UTC source date and evidence status whenever any fee input is supplied.

Fee evidence is either `observed`, `estimated` or `user_confirmed`. Incomplete fees are permitted so
the seller can save known costs, but missing inputs are never replaced with zero. Metadata without
fee values, fee values without complete metadata, naive timestamps, decreasing effective dates and
target margin below minimum margin fail validation.

Each response contains its scope, version, superseded profile, effective window, configuration
checksum and `user_confirmed` evidence label. New ORM records require an explicit selling-price tax
basis. A product-specific effective profile takes precedence over the marketplace default; profiles
are not field-by-field merged. The economics response also returns both independently effective
profiles in `profiles_by_scope`, so editing one scope never copies inputs from the other.

Cost profiles are append-only. The only permitted ORM update is a one-time `effective_to` closure
from `null` to an aware UTC timestamp when a later revision is created; deletion and every other
update are rejected. Their audit events are also append-only.

## Unit-economics contract

`GET /products/{product_id}/economics` returns:

- latest imported selling-price evidence, when present;
- the effective profile and bounded profile/audit history;
- formula version and configuration SHA-256;
- exact input and formula traces;
- fee evidence source/date/status;
- structured reason codes and notices; and
- the eight required outputs: landed cost, Amazon fees, contribution profit, margin, ROI,
  break-even price, minimum acceptable price and target price; plus
- net revenue and output GST contained within the recorded selling price, which make the tax
  treatment reviewable.

The active immutable formula is `selleros.unit-economics.v2`. Let `gross price` mean the recorded
selling price and `GST rate` be expressed as a decimal rate:

```text
unrecoverable input GST = purchase cost × GST rate × (1 - recoverable share)
landed cost            = purchase cost + unrecoverable input GST + freight + prep + packaging

revenue factor         = 1 / (1 + GST rate)  when gross price includes GST
                       = 1                   when gross price excludes GST
net revenue            = gross price × revenue factor
output GST in price    = gross price - net revenue
Amazon fees            = gross price × referral rate + fulfilment + closing + storage
allowances             = gross price × (advertising rate + returns rate)
contribution           = net revenue - landed cost - Amazon fees - allowances - overhead
margin                 = contribution / net revenue
ROI                    = contribution / landed cost

fixed unit cost        = landed cost + fulfilment + closing + storage + overhead
variable rate          = referral rate + advertising rate + returns rate
break-even gross price = fixed unit cost / (revenue factor - variable rate)
minimum gross price    = fixed unit cost /
                         (revenue factor × (1 - minimum margin) - variable rate)
target gross price     = fixed unit cost /
                         (revenue factor × (1 - target margin) - variable rate)
```

Referral, advertising and return provisions deliberately use the recorded gross-price basis; this
assumption is visible in the formula trace. For a tax-exclusive selling price, `output_gst` is zero
*within that recorded price*; it is not a tax-return calculation.

All arithmetic is `Decimal`. Intermediate values are not rounded; money and displayed percentages
use `ROUND_HALF_UP` to `0.01`. Zero divisors and non-positive price denominators produce unavailable
outputs and reason codes, not exceptions or invented values. When fees, selling price or its tax
basis are missing, the calculation is `partial`. A migrated legacy profile with an unknown tax basis
may still return landed cost, but every selling-price-dependent threshold/profit output is blocked.
Estimated fee inputs remain labelled Estimated even though the resulting arithmetic is Calculated.
An imported negative selling price remains visible as immutable source evidence but is excluded from
the calculation, which returns a partial result and `ECONOMICS_SELLING_PRICE_INVALID` notice rather
than raising or treating it as revenue.

Changing formula meaning, rounding or input semantics requires a new configuration resource and
formula version. Historical cost revisions and recommendations are not rewritten. The pre-release
`v1.json` resource remains archived, but the v2 kernel rejects it rather than emit v2 calculations
under a v1 provenance label. The configuration SHA-256 covers the loaded version/rounding resource;
`formula_version`, the returned formula trace and fixed expected tests are the semantic calculation
contract. It is not presented as a checksum of Python implementation code.

Migration `0003_phase2_economics_sourcing` backfills product-specific legacy cost profiles from the
product's explicit marketplace. It fails closed when a legacy default profile has no marketplace or
a legacy supplier offer lacks the newly required quotation evidence; an operator must resolve those
records explicitly rather than let the migration infer business facts. Migrated cost profiles keep
an unknown tax basis rather than receiving a guessed value.

## Supplier-offer contract

`POST /supplier-offers` records an immutable seller quotation with supplier name, product, explicit
marketplace currency, base unit cost, MOQ, lead-time days, quotation date, optional validity date and
notes. The supplier master identifier is retained while `supplier_name_at_quote` preserves the name
shown on that quotation even if the master record is corrected later.
Request `price_tiers` are additional tiers and must have unique increasing quantities above the base
MOQ. The persisted/returned tier list includes the base MOQ and unit cost first. Tiers can only be
inserted in the same transaction as their new parent quotation; later insertion, update and deletion
are rejected through the ORM.

`GET /products/{product_id}/supplier-offers` is paginated and bounded to 100 rows per page. It always
shows currency, cost, MOQ, lead time, validity and tiers. SellerOS does not identify a best offer from
price alone and does not accept quotations or contact suppliers.

Dates use ISO `YYYY-MM-DD`. With no seller-timezone setting in Phase 2, “today” and future-date
validation use the UTC calendar date and the UI labels that boundary explicitly. A future quotation
date or validity before quotation fails validation. An expired quotation remains historical evidence
but cannot produce a buy recommendation.

## Test-buy contract

`POST /products/{product_id}/test-buy-scenarios` accepts an in-scope supplier-offer identifier,
seller-confirmed budget decimal string and explicit budget currency. Budget and quotation currency
must match; currency conversion is never inferred.

The immutable `selleros.test-buy.v1` policy consumes:

- the latest imported Keepa monthly-sold estimate;
- the persisted Data Confidence score and formula version;
- supplier MOQ, lead time, validity and price tiers; and
- the explicit budget.

It returns and persists exactly three scenarios: `conservative`, `expected` and `aggressive`. Each
contains whole-unit quantity, applied tier cost, required supplier investment, expected sell-through
days, status and reason codes. Lead time increases bounded coverage. Budget and MOQ are hard
constraints. Low confidence applies a short evidence-window cap; if MOQ exceeds that cap, the
scenario is blocked rather than promoted to MOQ.

Missing, zero or negative demand, missing confidence, zero budget, insufficient MOQ budget or an
expired offer returns three explicit blocked scenarios. Negative imported demand remains in the
evidence trace but is excluded from policy inputs and carries `TEST_BUY_MONTHLY_DEMAND_INVALID`. An
aggregate `outcome` is `recommended` only when at least one scenario is recommended; an all-blocked
result has a null `decision_label` and is never presented as Recommended.

The append-only recommendation stores formula version, configuration checksum, inputs, notices,
structured evidence, the source snapshot identifier and the Data Confidence score-result identifier.
Missing demand has null source/label fields rather than an Estimated label. It is always
`advisory_only: true`; no endpoint places an order or grants purchasing authority.

## Evidence language and errors

UI and API evidence use these meanings:

- **Observed**: imported market evidence.
- **Calculated**: deterministic formula output.
- **Estimated**: proxy evidence such as Keepa monthly sold or a declared fee assumption.
- **Recommended**: advisory scenario output.
- **User confirmed**: seller-entered cost, quotation or budget evidence.

Expected domain failures use the standard structured error envelope with a stable code and
correlation identifier. Cross-tenant identifiers return non-disclosing 404 responses. Collection
queries are bounded. Authentication is not implemented in Phase 2, so this local build must not be
exposed as a public SaaS service.
