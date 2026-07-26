from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator


class ImportSummary(BaseModel):
    total: int
    created: int
    matched: int
    skipped: int
    failed: int
    row_error_count: int


class ImportWorkbook(BaseModel):
    sheet_name: str | None
    header_row_number: int | None
    alias_registry_version: str | None


class MappingColumnResponse(BaseModel):
    ordinal: int
    header: str
    normalized_header: str
    canonical_field: str | None
    classification: str
    dataset_classification: str
    candidates: list[str] = Field(default_factory=list)
    required_candidates: list[str] = Field(default_factory=list)
    is_required: bool
    samples: list[Any] = Field(default_factory=list)


class MappingResponse(BaseModel):
    registry_id: str
    registry_version: str
    columns: list[MappingColumnResponse] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)
    missing_optional: list[str] = Field(default_factory=list)
    requires_confirmation: bool


class PreviewRowResponse(BaseModel):
    row_number: int
    values: dict[str, Any] = Field(default_factory=dict)
    issues: list[dict[str, Any]] = Field(default_factory=list)


class ImportFailure(BaseModel):
    code: str
    message: str


class ImportDatasetResponse(BaseModel):
    schema_id: str | None
    schema_version: str | None
    schema_match: str
    dataset_schema_checksum: str
    source_column_count: int
    registered_column_count: int
    matched_column_count: int
    new_headers: list[str] = Field(default_factory=list)
    missing_headers: list[str] = Field(default_factory=list)
    source_header_checksum: str | None
    observed_on: date | None
    period_month: date | None
    revision: int | None
    date_status: str
    observation_date_candidates: list[dict[str, str]] = Field(default_factory=list)
    observed_on_suggestion: date | None
    suggestion_source: str | None
    observed_on_source: str | None


class ImportDetailResponse(BaseModel):
    id: str
    organisation_id: str
    marketplace_id: str
    original_filename: str
    checksum: str
    status: str
    uploaded_at: datetime
    confirmed_at: datetime | None
    completed_at: datetime | None
    workbook: ImportWorkbook
    dataset: ImportDatasetResponse
    mapping: MappingResponse
    preview_rows: list[PreviewRowResponse] = Field(default_factory=list)
    summary: ImportSummary | None
    failure: ImportFailure | None
    duplicate: bool = False


class ImportListItem(BaseModel):
    id: str
    original_filename: str
    status: str
    uploaded_at: datetime
    completed_at: datetime | None
    observed_on: date | None
    period_month: date | None
    revision: int | None
    summary: ImportSummary | None


class ImportListResponse(BaseModel):
    items: list[ImportListItem] = Field(default_factory=list)


CanonicalMapping = Annotated[str, Field(min_length=1, max_length=128)]


class MappingUpdate(BaseModel):
    mappings: dict[int, CanonicalMapping | None]

    @field_validator("mappings")
    @classmethod
    def validate_ordinals(
        cls, mappings: dict[int, CanonicalMapping | None]
    ) -> dict[int, CanonicalMapping | None]:
        if not mappings:
            raise ValueError("At least one mapping decision is required")
        if any(ordinal < 1 for ordinal in mappings):
            raise ValueError("Mapping ordinals must be positive one-based column numbers")
        return mappings


class ConfirmImportCommand(BaseModel):
    observed_on: date
