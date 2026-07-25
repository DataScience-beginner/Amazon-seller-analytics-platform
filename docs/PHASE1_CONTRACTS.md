# Phase 1 API and Decision Contracts

## Import contract

`POST /api/v1/imports` accepts multipart fields `file`, `organisation_id` and `marketplace_id`.
Successful inspection returns a pending import with workbook metadata, source-dataset metadata,
mapping columns, missing fields and bounded preview rows. Source ordinals are one-based.

The `dataset` object reports the source schema ID/version/match, immutable schema checksum, actual
header checksum, registered/matched/source column counts, new/missing headers, all detected date
candidates and an optional date suggestion. `exact` means the normalised registered header multiset
matches regardless of column order. `compatible` requires ASIN plus at least 80% registered-header
coverage. Other dynamic exports remain importable as `keepa.unregistered`, with a schema version
derived from the actual header checksum; their unknown fields are preserved.

`GET /api/v1/imports/{id}`, `PUT /api/v1/imports/{id}/mapping` and
`POST /api/v1/imports/{id}/confirm` require `organisation_id` and `marketplace_id` query parameters.
The import identifier and both scope values must match; mismatches return not found without exposing a
different tenant's import.

`PUT /api/v1/imports/{id}/mapping` accepts:

```json
{"mappings": {"3": "brand", "7": null}}
```

A string explicitly selects a canonical field; `null` explicitly ignores the source column. A
canonical field cannot be explicitly selected twice. Confirmation is blocked while required fields
are missing or any mapping is ambiguous.

`POST /api/v1/imports/{id}/confirm` requires:

```json
{"observed_on": "2026-05-26"}
```

The UI may prefill a suggestion only when all ISO dates detected in the worksheet name and filename
agree. The seller must review the date and explicitly confirm it. A future UTC date fails with
`observed_on_in_future`. A completed import is idempotent for the same date and returns
`import_observed_on_conflict` if a different date is submitted.

Confirmation derives `period_month` as the first day of the confirmed month and assigns the next
positive revision within organisation + marketplace + source schema + period. A revision race fails
retryably with `import_dataset_revision_retryable`; it never overwrites the other import. The summary
counts every nonblank workbook row exactly once across `created`, `matched`, `skipped` and `failed`.
`row_error_count` includes warnings for malformed optional cells as well as blocking row errors.

Snapshot evidence is flushed in bounded write chunks inside one outer transaction. This limits each
ORM flush burst, not total process memory: confirmation currently materialises all inspected rows and
retains the atomic unit of work until commit. A known retryable
database lock, serialization, deadlock or connection failure returns HTTP 503 with code
`import_confirmation_retryable`; the pending batch, storage key and staged workbook remain available
for retry. An unclassified operational database failure returns HTTP 500 with code
`import_confirmation_database_error` and `retryable: false`; it also preserves the pending batch and
staged evidence for operator diagnosis instead of looping or deleting evidence. File-backed SQLite
uses WAL and a bounded busy timeout for local reader concurrency. Terminal workbook/content failures
still roll back domain writes and remove staged content only after the failed state is durable.

Stable import errors use:

```json
{
  "error": {
    "code": "unsupported_file_type",
    "message": "Upload a Keepa export in .xlsx format",
    "correlation_id": "...",
    "details": {}
  }
}
```

No stack trace, SQL detail or source row value is returned or logged.

Each new `ProductSnapshot` stores the confirmed observation date and a complete `source_payload`
array containing every source cell as `{ordinal, header, value}`. This includes blank values and the
registered source fields that do not yet feed canonical calculations. `RawAttribute` remains the
indexed exception view for unrecognised headers or malformed canonical values; it is not the only
lossless store.

Imports and snapshots completed before the dated-dataset contract retain null observation metadata
and report `legacy_unconfirmed`. They are not silently backdated. They remain browsable as historical
evidence but are excluded from current portfolio, economics and sourcing decisions.

## Portfolio query contract

`GET /api/v1/products` requires organisation/marketplace scope and supports:

- `search` across ASIN, title and brand;
- versioned research `screen` and `brand_classification`;
- `strategy` and `category`;
- min/max opportunity score, offer count, price and confidence, plus demand, competition and price
  stability sorting;
- `sort_by`, `sort_direction`, `page` and `page_size` (maximum 100).

Range inversions fail validation. Sorting has a deterministic product-ID tie-breaker. Dashboard and
product detail use the same latest-snapshot/latest-version semantics as the product collection:
confirmed observation date first, then same-date revision. Upload time never promotes an older
dataset over newer market evidence.

The collection and product-detail responses include a `research` assessment from
`product-research-v1.0.0`, its configuration checksum, structured evidence and brand classification.
The collection also returns the available screens. `estimated_monthly_bought` is parsed only from
the exact preserved Keepa header `Monthly Sales Trends: Bought in past month`, remains labelled
Estimated, and is never substituted when absent. `offer_count` means current listing offers; it is
not a count of substitute products or a claim about total market competitors.

`GET /api/v1/dashboard` includes a `dataset_overview` derived from at most 10,000 latest confirmed
product snapshots in the requested organisation and marketplace. It reports evidence coverage,
category/subcategory distribution, brand concentration and structured conclusion codes. Revenue is
returned only when at least 70% of products have both a Keepa bought-in-past-month estimate and
current Buy Box price, and all contributing rows use one currency. Below that threshold the response
is `relative_research_only` and revenue fields remain null.

`GET /api/v1/dashboard/dataset-overview` accepts the same required scope plus an optional exact
`category`. It returns the same aggregate contract for the selected category. The dashboard uses
this endpoint together with the bounded product collection endpoint to render a category drill-down;
the selection never changes or reinterprets the whole-dataset overview.

`POST /api/v1/dashboard/category-cost-estimate` requires scope, exact subcategory, bounded pagination
and explicit percentage assumptions. `selleros.target-sourcing-cost.v1` uses the 90-day average Buy
Box price where available, otherwise the current Buy Box with an explicit source label. It returns
maximum wholesale cost excluding GST, GST-inclusive cash outlay and the individual Estimated
allowances. This ephemeral research calculation does not persist or replace audited cost profiles.

## Score semantics

All scores are integer 0–100, where higher is favourable:

- Demand: rank, rank drops, monthly sold and rank trend.
- Competition: a more approachable competitive environment scores higher.
- Price Stability: lower price deviation and lower Buy Box OOS score higher.
- Data Confidence: valid weighted source-field coverage.
- Overall Opportunity: weighted market scores multiplied by Data Confidence.

The persisted record contains the exact formula version, configuration SHA-256, parsed inputs,
components and reason codes. Missing values are never replaced with optimistic defaults.

## Strategy semantics

Strategies are Discovery, Test Buy, Growth, Cash Cow, Premium Margin, Monitor, Clearance Watch and
Avoid. Policy priority and thresholds live in a strict versioned JSON resource. Each stored decision
contains the rules version, configuration SHA-256, confidence and structured evidence.

With Phase 1 import-only inputs, Growth, Cash Cow and Premium Margin are gated because economics are
absent; Clearance Watch is gated because inventory is absent. Low confidence returns Discovery.
Test Buy, Avoid, Discovery and Monitor remain eligible from market evidence. These are advisory labels,
not actions.

## Version-change rule

Changing alias meaning, score weights/thresholds/rounding, strategy thresholds/priority or evidence
semantics requires a new resource and version plus boundary tests. Historical rows are append-only and
must continue to reference their original configuration checksum.
