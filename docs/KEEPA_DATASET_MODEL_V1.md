# Keepa Product Finder Dataset Model v1

## Purpose

SellerOS treats a Keepa Product Finder workbook as immutable market evidence for a user-confirmed
date. The workbook is not merely an upload event: confirmation creates a dated monthly dataset,
product snapshots and versioned decision evidence without changing earlier months.

This contract implements SOS-103. It is deliberately separate from seller-owned costs, inventory,
supplier quotations and planning inputs.

## Registered source model

| Contract field | Value |
| --- | --- |
| Schema ID | `keepa.product_finder` |
| Schema version | `1.0.0` |
| Manifest | `backend/app/modules/imports/resources/keepa_product_finder.v1.json` |
| Registered headers | 173 |
| Canonical decision mappings in the reference export | 21 |
| Registered source fields preserved but not yet calculated | 152 |

The manifest contains public column headers only. It contains no workbook rows, ASINs, seller data or
credentials. Its configuration SHA-256 is persisted with each import so a future agent can identify
the exact source contract used.

Header recognition normalises case, punctuation and whitespace and does not depend on Excel column
positions. An exact match has the same normalised header multiset. A compatible match must contain
ASIN and at least 80% of the registered headers. A weaker or materially different export remains
importable as `keepa.unregistered`, with its version derived from the actual header checksum.

Source recognition does not decide calculation meaning. The versioned alias registry separately maps
known headers into canonical SellerOS fields. Ambiguous aliases always require an explicit mapping
decision.

## Dataset date and revisions

Inspection records ISO dates detected in:

- the selected worksheet name;
- the original filename.

SellerOS offers a suggestion only when all detected candidates represent the same date. A suggestion
is never confirmation. The user must submit an explicit `observed_on` date; future dates are rejected.

On confirmation SellerOS derives:

- `period_month`: the first day of the observed calendar month;
- `revision`: the next positive integer for organisation + marketplace + schema + month;
- `observed_on_source`: `user_confirmed`.

Different workbook checksums for the same month create separate revisions. The same checksum is
idempotent. Older observation dates may be uploaded later, but cannot replace a product's newer
latest evidence. Latest selection compares observation date, then same-date revision.

Upload, confirmation and completion timestamps remain operational metadata and never substitute for
the market observation date.

## Lossless evidence

Each valid row creates one immutable `ProductSnapshot` for its organisation + marketplace + ASIN.
The snapshot stores:

- the confirmed observation date;
- typed canonical fields used by deterministic calculations;
- all canonical market metrics;
- every source cell as an ordered `{ordinal, header, value}` item, including blanks;
- source row number and import-batch link.

`RawAttribute` provides an indexed exception view for genuinely unrecognised headers and malformed
mapped cells. It is not the only raw store. Registered-but-unused fields remain available in the full
snapshot source payload for future versioned features.

Imported evidence never overwrites seller-owned costs, inventory, quotations, budgets or plans.

## Legacy evidence

Migration `0004_dated_keepa_datasets` adds nullable date/source fields without inventing dates for
existing snapshots. Those rows report `legacy_unconfirmed`. They remain browsable but are excluded
from current portfolio, economics and sourcing decisions because their evidence date is unknown.

The safe correction path is a new import with a user-confirmed date, not an in-place rewrite.

## UI contract

The import detail screen:

- shows the source schema and source/canonical/preserved/new field counts;
- collapses registered fields and asks the user to review only new or ambiguous exceptions;
- displays every date candidate and warns when candidates conflict;
- requires an editable date plus explicit acknowledgement;
- labels Observed, Uploaded and Processed dates separately;
- names the action using the resulting month, for example `Create May 2026 dataset`.

The product, dashboard, planning and economics views use the confirmed observed date for market
chronology. Estimated or recommended values retain their existing evidence labels.
