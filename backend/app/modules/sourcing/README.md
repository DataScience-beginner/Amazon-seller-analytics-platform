# Sourcing recommendation kernel

This package implements the deterministic SOS-502 test-buy policy. It consumes an explicit supplier
quotation, a seller-confirmed budget, the latest stored monthly-demand estimate and the persisted
data-confidence score. It does not fetch data, choose a tenant, convert currency or execute an order.

The v1 policy returns conservative, expected and aggressive scenarios. Scenario coverage includes a
bounded lead-time factor. Supplier MOQ, applicable price tiers and budget are hard constraints.
Products below the configured confidence threshold are capped to a short evidence window; if MOQ
would breach that cap the scenario is blocked instead of overbuying. Missing or zero demand,
missing confidence, currency mismatch and insufficient MOQ budget fail closed.
Negative imported demand remains preserved in the recommendation evidence, is excluded from kernel
inputs and blocks all scenarios with `TEST_BUY_MONTHLY_DEMAND_INVALID` rather than raising or being
converted into a quantity.

Quantities are whole units rounded upward before caps. Investment uses exact Decimal tier prices and
`ROUND_HALF_UP` to `0.01`; sell-through days round to `0.1`. Every result carries stable reason codes,
the immutable formula version and the configuration checksum. Recommendations are advisory only and
their application-layer records are append-only. AI may explain or compare scenarios, but cannot
change the configuration or place a purchase order.

Supplier quotations are separate, immutable seller evidence. An offer records currency, MOQ, lead
time, quotation and validity dates, notes, and an ordered base-plus-discount tier schedule. API
listings are paginated and expose price, MOQ and lead time together; no repository or route declares
a price-only winner. Documents are intentionally absent in Phase 2. Stable offer identifiers provide
the future foreign-key boundary for attachment metadata without changing quotation semantics.
