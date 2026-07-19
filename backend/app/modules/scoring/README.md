# Phase 1 scoring specification

This package is the deterministic market-opportunity scoring kernel. It has no
FastAPI, SQLAlchemy, file-import or AI dependencies. Callers translate canonical
snapshot fields into `MarketMetrics`, call `score_market_metrics`, and persist the
returned values, inputs, components, reason codes and formula version.

The current definition is `configs/v1.json`, with formula version
`selleros.market-opportunity.v1`. Changing a threshold, weight, input meaning or
rounding behaviour requires a new immutable formula version and regression
fixtures. A prior definition must remain available while stored scores reference
it.

## Scores

- **Demand** combines current sales rank, 90-day rank-drop count, monthly sold and
  current-versus-90-day rank trend. A lower rank is better; more drops and monthly
  sales are better; a current/average rank ratio below one indicates improvement.
- **Competition** combines offer count, review count and 90-day Buy Box winner
  count. Lower values produce a higher competition score, meaning a more
  approachable competitive environment. It is not a guarantee of entry success.
- **Price Stability** combines current-price deviation from the 90-day average and
  Buy Box out-of-stock percentage. Lower deviation and lower OOS produce a higher
  score.
- **Data Confidence** is weighted valid-field coverage. Missing, malformed and
  configured outlier values earn no confidence weight.
- **Overall Opportunity** combines Demand, Competition and Price Stability, then
  explicitly multiplies that base result by Data Confidence.

Profitability, cash efficiency and inventory risk are deliberately absent. This
module must never describe an imported-only product as profitable.

## Deterministic calculation

For every available component, its configured `full_score_at` and `zero_score_at`
define a clamped linear 0–100 scale:

```text
component = clamp((value - zero_at) / (full_at - zero_at) * 100, 0, 100)
```

When a component is unavailable, the score is calculated from the remaining
components by reweighting only their declared weights. This is always disclosed by
`SCORING_AVAILABLE_COMPONENTS_REWEIGHTED`; no optimistic replacement value is
inserted. Confidence independently falls because the absent or unusable source
field receives zero coverage weight.

```text
market score = sum(component * declared weight) / sum(available weights)
confidence   = sum(weights of valid raw inputs) * 100
base overall = demand * 0.45 + competition * 0.30 + stability * 0.25
overall      = base overall * confidence / 100
```

All parsing, ratios, interpolation and weighting use `Decimal`. Final scores and
displayed component scores use `ROUND_HALF_UP` and are clamped to integer 0–100.

## Input and quality rules

- `None`, blank strings, dashes and common NA markers are missing.
- Finite `Decimal`, integer, float and simple numeric strings are accepted. Float
  input is converted through its string representation before Decimal arithmetic.
- Grouping commas, one leading common currency symbol and a trailing `%` are
  removed conservatively.
- Booleans, non-numeric text, NaN and infinity are invalid.
- Values outside the configured metric bounds are outliers and excluded.
- Zero/invalid average rank or price cannot reach ratio division because the v1
  bounds require those fields to be greater than zero.

Every excluded field produces a stable reason code with the metric name. Reason
codes are API/storage contracts; wording can be localized later without changing
their meaning.

## Integration contract

The engine is pure: the same typed input and config always produce the same score
card. It does not select a tenant, read the database, fetch Keepa data or mutate a
snapshot. The application layer is responsible for:

1. selecting the exact immutable snapshot;
2. selecting the formula version;
3. persisting each result once for that snapshot/version;
4. recording calculation correlation and audit metadata;
5. passing the five score values to the separate strategy classifier.

AI may explain a persisted score card, but it must not change the inputs, weights,
thresholds or result.
