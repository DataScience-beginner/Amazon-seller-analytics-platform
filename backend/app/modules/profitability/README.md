# Profitability decision kernel

This package implements SOS-401 and SOS-402 without FastAPI, SQLAlchemy or AI dependencies. The
same explicit `EconomicsInputs` and immutable configuration always produce the same
`EconomicsResult`. Seller-entered costs and fee evidence are selected by the application service;
the kernel never chooses a tenant, marketplace, currency, product, price or missing assumption.

`selleros.unit-economics.v2` requires the seller to declare `selling_price_tax_basis` as either
`tax_inclusive` or `tax_exclusive`. Supplier purchase cost is GST-exclusive. Only the configured
unrecoverable share of input GST is included in landed cost. A tax-exclusive selling price has a
revenue factor of `1`; a tax-inclusive price has a revenue factor of `1 / (1 + gst_rate)`. Net
revenue is gross selling price times that factor, and output GST is gross price minus net revenue.
Referral, advertising and returns remain percentages of the gross selling price. Fulfilment,
closing, storage and overhead are fixed per-unit costs. Contribution profit deducts all costs from
net revenue, and margin divides contribution by net revenue.

Break-even price is `fixed_cost / (revenue_factor - variable_rate)`. Minimum and target prices use
`fixed_cost / (revenue_factor * (1 - required_margin) - variable_rate)`. The archived `v1.json`
resource is retained as immutable history, but this kernel rejects it because executing v2
semantics under a v1 label would corrupt provenance.
The result formula map defines `revenue_factor`, `fixed_unit_cost` and `total_variable_rate` from
raw input names before any output formula references them, so the returned trace is self-contained.

Money is rounded to the currency-unit quantum `0.01` and percentages to `0.01`, both with
`ROUND_HALF_UP`. Intermediate arithmetic is not rounded. If fee inputs are incomplete, the kernel
does not replace them with zero: fee-dependent outputs are unavailable and carry stable reason
codes. A zero selling price or landed cost never reaches division. Estimated fee evidence remains
labelled Estimated even though outputs are deterministic Calculated values.
Migrated legacy profiles may have a null selling-price tax basis. The kernel never infers one:
landed cost remains available, while net revenue, output GST, fees, contribution, margin, ROI and
all price recommendations remain null with a stable missing-basis reason code. New API and ORM
profile creation both require an explicit basis.
Negative imported selling-price evidence is retained on its immutable snapshot but is not passed to
the kernel. The application returns a partial calculation with
`ECONOMICS_SELLING_PRICE_INVALID`; it never treats a negative sentinel as revenue.

The configuration resource is append-only. Any change to formula meaning, input meaning or
rounding requires a new formula version and resource; persisted historical evidence must not be
rewritten. AI may explain a result but may not inject assumptions or change its calculation.

The application boundary resolves an effective product-specific profile first, then the explicit
organisation-owned marketplace default. A seller edit creates a new numbered profile revision,
closes the prior effective window and appends an audit event; it never changes imported snapshots.
Currency must match the marketplace until a future version introduces explicit FX evidence. Profile
and audit collections are bounded, and a database constraint ties every profile scope key to either
its product identifier or the marketplace-default sentinel.
