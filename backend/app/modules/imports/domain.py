from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

type JsonScalar = None | bool | int | float | str


class CanonicalValueType(StrEnum):
    text = "text"
    integer = "integer"
    decimal = "decimal"
    percentage = "percentage"
    boolean = "boolean"
    date = "date"
    datetime = "datetime"
    url = "url"


class MappingClassification(StrEnum):
    required = "required"
    optional = "optional"
    unknown = "unknown"
    missing = "missing"
    ambiguous = "ambiguous"


class MappingReasonCode(StrEnum):
    alias_match = "alias_match"
    explicit_mapping = "explicit_mapping"
    explicitly_ignored = "explicitly_ignored"
    no_alias_match = "no_alias_match"
    alias_collision = "alias_collision"
    duplicate_target = "duplicate_target"
    duplicate_not_selected = "duplicate_not_selected"
    field_missing = "field_missing"


class WorkbookErrorCode(StrEnum):
    corrupt_workbook = "corrupt_workbook"
    empty_workbook = "empty_workbook"
    unsupported_structure = "unsupported_structure"
    ambiguous_header = "ambiguous_header"
    safety_limit_exceeded = "safety_limit_exceeded"
    dangerous_archive = "dangerous_archive"
    workbook_changed = "workbook_changed"
    registry_changed = "registry_changed"


@dataclass(frozen=True, slots=True)
class CanonicalField:
    name: str
    required: bool
    value_type: CanonicalValueType
    aliases: tuple[str, ...]
    description: str


@dataclass(frozen=True, slots=True)
class SourceColumn:
    """A source column identified by its one-based workbook ordinal."""

    ordinal: int
    source_header: str
    normalized_header: str


@dataclass(frozen=True, slots=True)
class ColumnMapping:
    column: SourceColumn | None
    canonical_field: str | None
    classification: MappingClassification
    candidates: tuple[str, ...] = ()
    required_candidates: tuple[str, ...] = ()
    is_required: bool = False
    explicitly_resolved: bool = False
    reason_code: MappingReasonCode = MappingReasonCode.no_alias_match

    @property
    def is_resolved(self) -> bool:
        return (
            self.column is not None
            and self.canonical_field is not None
            and self.classification
            in (MappingClassification.required, MappingClassification.optional)
        )


@dataclass(frozen=True, slots=True)
class MappingReport:
    registry_id: str
    registry_version: str
    columns: tuple[ColumnMapping, ...]
    missing: tuple[ColumnMapping, ...]

    @property
    def entries(self) -> tuple[ColumnMapping, ...]:
        return self.columns + self.missing

    @property
    def requires_confirmation(self) -> bool:
        return any(
            entry.classification is MappingClassification.ambiguous for entry in self.columns
        )

    @property
    def missing_required_fields(self) -> tuple[str, ...]:
        return tuple(
            entry.canonical_field
            for entry in self.missing
            if entry.is_required and entry.canonical_field is not None
        )

    @property
    def unresolved_required_fields(self) -> tuple[str, ...]:
        unresolved = set(self.missing_required_fields)
        for entry in self.columns:
            if entry.classification is not MappingClassification.ambiguous:
                continue
            unresolved.update(entry.required_candidates)
        return tuple(sorted(unresolved))

    @property
    def resolved_by_field(self) -> dict[str, ColumnMapping]:
        return {
            entry.canonical_field: entry
            for entry in self.columns
            if entry.is_resolved and entry.canonical_field is not None
        }


@dataclass(frozen=True, slots=True)
class SourceCell:
    ordinal: int
    source_header: str
    value: JsonScalar


@dataclass(frozen=True, slots=True)
class CellIssue:
    code: str
    message: str
    column_ordinal: int | None = None
    canonical_field: str | None = None


@dataclass(frozen=True, slots=True)
class WorkbookRow:
    row_number: int
    canonical_values: dict[str, JsonScalar]
    source_values: tuple[SourceCell, ...]
    issues: tuple[CellIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkbookInspection:
    checksum_sha256: str
    sheet_names: tuple[str, ...]
    selected_sheet: str
    header_row: int
    columns: tuple[SourceColumn, ...]
    mapping: MappingReport
    preview_rows: tuple[WorkbookRow, ...]


@dataclass(frozen=True, slots=True)
class WorkbookSafetyLimits:
    max_archive_bytes: int = 50 * 1024 * 1024
    max_archive_entries: int = 20_000
    max_member_uncompressed_bytes: int = 128 * 1024 * 1024
    max_total_uncompressed_bytes: int = 512 * 1024 * 1024
    max_compression_ratio: float = 1_000.0
    max_filename_length: int = 512
    max_worksheets: int = 50
    max_header_scan_rows: int = 50
    max_columns: int = 512
    min_header_cells: int = 2
    preview_rows: int = 5
    max_preview_scan_rows: int = 250
    max_data_scan_rows: int = 250_000
    max_data_rows: int = 100_000


@dataclass(frozen=True, slots=True)
class WorkbookInspectionError(ValueError):
    code: WorkbookErrorCode
    user_message: str
    details: dict[str, JsonScalar] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.user_message
