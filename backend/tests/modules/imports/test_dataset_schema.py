from datetime import date

from app.modules.imports.dataset_schema import (
    DatasetColumnClassification,
    DatasetSchemaMatch,
    ObservationDateSuggestionSource,
    ProductFinderDatasetSchema,
    source_header_checksum,
    suggest_observed_on,
)
from app.modules.imports.domain import SourceColumn
from app.modules.imports.mapping import map_headers
from app.modules.imports.normalization import normalize_header
from app.modules.imports.registry import AliasRegistry


def _columns(headers: tuple[str, ...]) -> tuple[SourceColumn, ...]:
    return tuple(
        SourceColumn(
            ordinal=ordinal,
            source_header=header,
            normalized_header=normalize_header(header),
        )
        for ordinal, header in enumerate(headers, start=1)
    )


def test_product_finder_v1_registers_exact_173_headers_without_position_dependence() -> None:
    schema = ProductFinderDatasetSchema.default()
    assert schema.schema_id == "keepa.product_finder"
    assert schema.version == "1.0.0"
    assert len(schema.headers) == 173
    assert len(schema.configuration_checksum) == 64

    original = _columns(schema.headers)
    reordered = _columns(tuple(reversed(schema.headers)))
    original_inspection = schema.inspect(original)
    reordered_inspection = schema.inspect(reordered)

    assert original_inspection.match is DatasetSchemaMatch.exact
    assert reordered_inspection.match is DatasetSchemaMatch.exact
    assert original_inspection.matched_column_count == 173
    assert original_inspection.new_headers == ()
    assert original_inspection.missing_headers == ()
    assert original_inspection.source_header_checksum == source_header_checksum(reordered)


def test_product_finder_v1_classifies_canonical_preserved_and_new_source_fields() -> None:
    schema = ProductFinderDatasetSchema.default()
    columns = _columns((*schema.headers, "Synthetic Future Keepa Signal"))
    mapping = map_headers(
        (*schema.headers, "Synthetic Future Keepa Signal"), AliasRegistry.default()
    )
    classifications = [
        schema.classify_column(
            normalized_header=entry.column.normalized_header,
        )
        for entry in mapping.columns
        if entry.column is not None
    ]

    assert classifications.count(DatasetColumnClassification.registered_source) == 173
    assert classifications.count(DatasetColumnClassification.unrecognized) == 1
    inspection = schema.inspect(columns)
    assert inspection.match is DatasetSchemaMatch.compatible
    assert inspection.matched_column_count == 173
    assert inspection.new_headers == ("Synthetic Future Keepa Signal",)

    explicitly_mapped = map_headers(
        ("ASIN", "Synthetic Future Keepa Signal"),
        AliasRegistry.default(),
        explicit_mappings={2: "title"},
    )
    future_entry = explicitly_mapped.columns[1]
    assert future_entry.column is not None
    assert future_entry.canonical_field == "title"
    assert (
        schema.classify_column(
            normalized_header=future_entry.column.normalized_header,
        )
        is DatasetColumnClassification.unrecognized
    )


def test_observation_date_suggestion_is_advisory_and_deterministic() -> None:
    from_sheet = suggest_observed_on(
        sheet_name="2026-05-26",
        original_filename="Synthetic-2026-05-26-ProductFinder.xlsx",
    )
    assert from_sheet is not None
    assert from_sheet.observed_on == date(2026, 5, 26)
    assert from_sheet.source is ObservationDateSuggestionSource.sheet_name

    from_filename = suggest_observed_on(
        sheet_name="Keepa",
        original_filename="Synthetic-2026-05-26-ProductFinder.xlsx",
    )
    assert from_filename is not None
    assert from_filename.observed_on == date(2026, 5, 26)
    assert from_filename.source is ObservationDateSuggestionSource.filename

    assert (
        suggest_observed_on(
            sheet_name="2026-05-26",
            original_filename="KeepaExport-2026-04-01-ProductFinder.xlsx",
        )
        is None
    )

    assert (
        suggest_observed_on(
            sheet_name="Keepa",
            original_filename="Keepa-2026-05-01-to-2026-05-31.xlsx",
        )
        is None
    )
