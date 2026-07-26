# Keepa import kernel

This package is the deterministic, framework-independent boundary for SOS-101 through SOS-103. It
inspects an OOXML `.xlsx` workbook, detects its Keepa header row, maps source columns through a
versioned alias registry, and returns typed preview and row objects. It does not write to the
database, choose an organisation or marketplace, or decide whether an import transaction commits.
Those responsibilities belong to the application service and repository boundaries.

## Public contract

The supported entry points are exported from `app.modules.imports`:

- `AliasRegistry.default()` loads the packaged `keepa_aliases.v1.json` registry.
- `normalize_header(value)` performs deterministic, position-independent header normalization.
- `map_headers(headers, registry, explicit_mappings=...)` returns a `MappingReport` without opening
  a workbook.
- `inspect_workbook(source, registry, explicit_mappings=..., limits=...)` validates a workbook and
  returns its checksum, selected sheet/header, mapping report and bounded preview.
- `iter_workbook_rows(source, inspection, registry, limits=...)` streams parsed rows after verifying
  that the workbook checksum, headers and registry identity/version still match the preview.
- `read_workbook_rows(...)` is the bounded materializing convenience used by tests and small callers.
- `ProductFinderDatasetSchema.default()` loads the immutable
  `keepa_product_finder.v1.json` 173-header source-model manifest.
- `ProductFinderDatasetSchema.inspect(columns)` classifies the source as exact, compatible or
  unregistered and returns source/schema checksums without changing canonical alias mapping.
- `observation_date_candidates(...)` and `suggest_observed_on(...)` expose worksheet/filename date
  evidence. A suggestion exists only when every candidate agrees.

`source` is either immutable workbook bytes or a `Path`. Mapping ordinals are one-based, matching
Excel column positions. An explicit mapping value selects a canonical field; `None` explicitly
ignores that source column. Two automatic claims on one canonical field remain ambiguous. The
kernel never chooses between them. Two explicit claims on one canonical field are rejected.

Every mapping carries a stable classification and reason code. Callers must persist the registry
identifier/version and each source ordinal, source header, selected target or explicit-ignore
decision with the import batch. This makes later reprocessing and AI-assisted diagnosis auditable.

Source-schema classification and canonical alias mapping are separate axes. A header may be a
registered Product Finder field even when SellerOS does not map it into a canonical decision field.
Such a value is still retained in the snapshot source payload. Exact schema matching compares the
normalised header multiset, independent of column order. Compatible matching requires ASIN and at
least 80% registered-header coverage; weaker dynamic exports receive an explicit
`keepa.unregistered` identity with a version derived from the actual header checksum.

## Workbook and value semantics

- Workbooks are opened read-only with `data_only=True` and external-link preservation disabled.
  Formula expressions are never returned or evaluated. A formula without a cached result appears
  as an empty value and normal row validation applies.
- Archive paths, encryption, executable/embedded content, entity declarations, compression ratios,
  member sizes, worksheet counts, row counts and column counts are bounded before row processing.
- Header selection is deterministic. Equally ranked candidates produce `ambiguous_header`; the
  kernel does not guess.
- Blank data rows are skipped, while reported row numbers retain their original Excel positions.
- Canonical decimal and percentage values are exact decimal strings, not binary floats. Dates and
  datetimes are ISO-8601 strings.
- `WorkbookRow.source_values` includes every source column, including unmapped columns. This is the
  lossless hand-off used to preserve unknown Keepa values. `canonical_values` contains only resolved
  mappings.
- Invalid cells become `None` in the canonical view and receive a `CellIssue`; their JSON-safe source
  representation remains available. Required identifiers are never invented.

The HTTP upload adapter remains responsible for filename, extension, media-type and configured
request-size checks. The application service remains responsible for idempotency by organisation,
marketplace and checksum, transactional status changes, row-error persistence and immutable snapshot
creation. It also requires a user-confirmed observation date, assigns a calendar-month revision and
stores every source cell as ordinal/header/value evidence. Upload or processing time must never be
used as the observation date.

## Registry changes

Alias registry and source-schema files are append-only contracts. Change aliases or the registered
source model by adding a new resource and version rather than silently changing the meaning of a
completed import. Cross-field alias collisions are permitted intentionally: they appear as ambiguous
mappings that require an explicit decision.

## Example

```python
from app.modules.imports import AliasRegistry, inspect_workbook, read_workbook_rows

registry = AliasRegistry.default()
preview = inspect_workbook(workbook_bytes, registry)

if preview.mapping.requires_confirmation:
    # Present candidates to the user, then inspect again with decisions such as {3: "brand"}.
    preview = inspect_workbook(workbook_bytes, registry, explicit_mappings={3: "brand"})

if preview.mapping.unresolved_required_fields:
    raise ValueError("A required identifier still needs a mapping")

rows = read_workbook_rows(workbook_bytes, preview, registry)
```
