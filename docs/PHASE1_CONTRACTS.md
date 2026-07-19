# Phase 1 API and Decision Contracts

## Import contract

`POST /api/v1/imports` accepts multipart fields `file`, `organisation_id` and `marketplace_id`.
Successful inspection returns a pending import with workbook metadata, mapping columns, missing fields
and bounded preview rows. Source ordinals are one-based.

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

`POST /api/v1/imports/{id}/confirm` is idempotent. Its summary counts every nonblank workbook row
exactly once across `created`, `matched`, `skipped` and `failed`. `row_error_count` includes warnings
for malformed optional cells as well as blocking row errors.

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

## Portfolio query contract

`GET /api/v1/products` requires organisation/marketplace scope and supports:

- `search` across ASIN, title and brand;
- `strategy` and `category`;
- min/max opportunity score, offer count, price and confidence;
- `sort_by`, `sort_direction`, `page` and `page_size` (maximum 100).

Range inversions fail validation. Sorting has a deterministic product-ID tie-breaker. Dashboard and
product detail use the same latest-snapshot/latest-version semantics as the product collection.

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
