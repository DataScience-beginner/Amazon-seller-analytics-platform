from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from importlib.resources import files
from typing import Final, cast

from app.modules.imports.domain import SourceColumn
from app.modules.imports.normalization import normalize_header

_SCHEMA_KEYS: Final = {"manifest_version", "schema_id", "version", "headers"}
_VERSION_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SCHEMA_ID_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")
_ISO_DATE_IN_TEXT: Final = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")
_COMPATIBLE_COVERAGE_PERCENT: Final = 80


class DatasetSchemaValidationError(ValueError):
    """Raised when a persisted source-schema manifest is malformed."""


class DatasetSchemaMatch(StrEnum):
    exact = "exact"
    compatible = "compatible"
    unregistered = "unregistered"


class DatasetColumnClassification(StrEnum):
    registered_source = "registered_source"
    unrecognized = "unrecognized"


class ObservationDateSuggestionSource(StrEnum):
    sheet_name = "sheet_name"
    filename = "filename"


@dataclass(frozen=True, slots=True)
class ObservationDateSuggestion:
    observed_on: date
    source: ObservationDateSuggestionSource


@dataclass(frozen=True, slots=True)
class DatasetSchemaInspection:
    schema_id: str | None
    schema_version: str | None
    match: DatasetSchemaMatch
    source_column_count: int
    registered_column_count: int
    matched_column_count: int
    new_headers: tuple[str, ...]
    missing_headers: tuple[str, ...]
    source_header_checksum: str


@dataclass(frozen=True, slots=True)
class ProductFinderDatasetSchema:
    schema_id: str
    version: str
    headers: tuple[str, ...]

    @classmethod
    def default(cls) -> ProductFinderDatasetSchema:
        resource = files("app.modules.imports").joinpath("resources/keepa_product_finder.v1.json")
        return cls.from_json(resource.read_text(encoding="utf-8"))

    @classmethod
    def from_json(cls, manifest: str) -> ProductFinderDatasetSchema:
        try:
            raw_payload: object = json.loads(manifest)
        except json.JSONDecodeError as exc:
            raise DatasetSchemaValidationError("Dataset schema manifest is not valid JSON") from exc
        if not isinstance(raw_payload, dict) or any(
            not isinstance(key, str) for key in raw_payload
        ):
            raise DatasetSchemaValidationError(
                "Dataset schema manifest must be an object with string keys"
            )
        payload = cast(dict[str, object], raw_payload)
        unknown_keys = sorted(set(payload) - _SCHEMA_KEYS)
        if unknown_keys:
            raise DatasetSchemaValidationError(
                f"Dataset schema manifest contains unknown keys: {', '.join(unknown_keys)}"
            )
        if payload.get("manifest_version") != 1:
            raise DatasetSchemaValidationError("manifest_version must be the integer 1")

        schema_id = payload.get("schema_id")
        if not isinstance(schema_id, str) or _SCHEMA_ID_PATTERN.fullmatch(schema_id) is None:
            raise DatasetSchemaValidationError("schema_id has an unsupported format")
        version = payload.get("version")
        if not isinstance(version, str) or _VERSION_PATTERN.fullmatch(version) is None:
            raise DatasetSchemaValidationError("version has an unsupported format")
        raw_headers = payload.get("headers")
        if not isinstance(raw_headers, list) or not raw_headers:
            raise DatasetSchemaValidationError("headers must be a non-empty array")

        headers: list[str] = []
        normalized_headers: set[str] = set()
        for position, raw_header in enumerate(raw_headers, start=1):
            if not isinstance(raw_header, str) or not raw_header.strip():
                raise DatasetSchemaValidationError(
                    f"headers[{position}] must be a non-empty string"
                )
            header = raw_header.strip()
            normalized = normalize_header(header)
            if not normalized:
                raise DatasetSchemaValidationError(
                    f"headers[{position}] normalizes to an empty value"
                )
            if normalized in normalized_headers:
                raise DatasetSchemaValidationError(
                    f"headers[{position}] duplicates another header after normalization"
                )
            normalized_headers.add(normalized)
            headers.append(header)
        return cls(schema_id=schema_id, version=version, headers=tuple(headers))

    @property
    def normalized_to_header(self) -> dict[str, str]:
        return {normalize_header(header): header for header in self.headers}

    @property
    def configuration_checksum(self) -> str:
        canonical = json.dumps(
            {
                "schema_id": self.schema_id,
                "version": self.version,
                "headers": list(self.headers),
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def inspect(self, columns: tuple[SourceColumn, ...]) -> DatasetSchemaInspection:
        registered = self.normalized_to_header
        source_counter = Counter(column.normalized_header for column in columns)
        registered_counter = Counter(registered.keys())
        source_set = set(source_counter)
        registered_set = set(registered_counter)
        matched = source_set & registered_set
        new_headers = tuple(
            column.source_header
            for column in columns
            if column.normalized_header not in registered_set
        )
        missing_headers = tuple(
            header for normalized, header in registered.items() if normalized not in source_set
        )
        exact = source_counter == registered_counter
        asin_present = normalize_header("ASIN") in source_set
        strong_coverage = len(matched) * 100 >= len(registered_set) * _COMPATIBLE_COVERAGE_PERCENT
        schema_match = (
            DatasetSchemaMatch.exact
            if exact
            else DatasetSchemaMatch.compatible
            if asin_present and strong_coverage
            else DatasetSchemaMatch.unregistered
        )
        return DatasetSchemaInspection(
            schema_id=self.schema_id
            if schema_match is not DatasetSchemaMatch.unregistered
            else None,
            schema_version=self.version
            if schema_match is not DatasetSchemaMatch.unregistered
            else None,
            match=schema_match,
            source_column_count=len(columns),
            registered_column_count=len(self.headers),
            matched_column_count=sum(
                min(source_counter[header], registered_counter[header]) for header in matched
            ),
            new_headers=new_headers,
            missing_headers=missing_headers,
            source_header_checksum=source_header_checksum(columns),
        )

    def classify_column(
        self,
        *,
        normalized_header: str,
    ) -> DatasetColumnClassification:
        if normalized_header in self.normalized_to_header:
            return DatasetColumnClassification.registered_source
        return DatasetColumnClassification.unrecognized


def source_header_checksum(columns: tuple[SourceColumn, ...]) -> str:
    normalized_headers = sorted(column.normalized_header for column in columns)
    canonical = json.dumps(normalized_headers, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def suggest_observed_on(
    *,
    sheet_name: str | None,
    original_filename: str,
) -> ObservationDateSuggestion | None:
    candidates = list(
        observation_date_candidates(
            sheet_name=sheet_name,
            original_filename=original_filename,
        )
    )
    if not candidates or len({candidate.observed_on for candidate in candidates}) != 1:
        return None
    return next(
        (
            candidate
            for candidate in candidates
            if candidate.source is ObservationDateSuggestionSource.sheet_name
        ),
        candidates[0],
    )


def observation_date_candidates(
    *,
    sheet_name: str | None,
    original_filename: str,
) -> tuple[ObservationDateSuggestion, ...]:
    candidates: list[ObservationDateSuggestion] = []
    if sheet_name is not None:
        sheet_date = _parse_exact_iso_date(sheet_name)
        if sheet_date is not None:
            candidates.append(
                ObservationDateSuggestion(
                    observed_on=sheet_date,
                    source=ObservationDateSuggestionSource.sheet_name,
                )
            )
    filename_dates = [
        parsed
        for candidate in _ISO_DATE_IN_TEXT.findall(original_filename)
        if (parsed := _parse_exact_iso_date(candidate)) is not None
    ]
    for filename_date in dict.fromkeys(filename_dates):
        candidates.append(
            ObservationDateSuggestion(
                observed_on=filename_date,
                source=ObservationDateSuggestionSource.filename,
            )
        )
    return tuple(candidates)


def _parse_exact_iso_date(value: str) -> date | None:
    candidate = value.strip()
    if _ISO_DATE_IN_TEXT.fullmatch(candidate) is None:
        return None
    try:
        return date.fromisoformat(candidate)
    except ValueError:
        return None
