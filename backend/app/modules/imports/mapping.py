from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.modules.imports.domain import (
    ColumnMapping,
    MappingClassification,
    MappingReasonCode,
    MappingReport,
    SourceColumn,
)
from app.modules.imports.normalization import normalize_header
from app.modules.imports.registry import AliasRegistry, RegistryValidationError


class MappingResolutionError(ValueError):
    """Raised when an explicit mapping is internally inconsistent."""


@dataclass(slots=True)
class _WorkingMapping:
    column: SourceColumn
    canonical_field: str | None
    classification: MappingClassification
    candidates: tuple[str, ...]
    required_candidates: tuple[str, ...]
    is_required: bool
    explicitly_resolved: bool
    reason_code: MappingReasonCode

    def freeze(self) -> ColumnMapping:
        return ColumnMapping(
            column=self.column,
            canonical_field=self.canonical_field,
            classification=self.classification,
            candidates=self.candidates,
            required_candidates=self.required_candidates,
            is_required=self.is_required,
            explicitly_resolved=self.explicitly_resolved,
            reason_code=self.reason_code,
        )


def map_headers(
    headers: Sequence[Any],
    registry: AliasRegistry,
    *,
    explicit_mappings: Mapping[int, str | None] | None = None,
) -> MappingReport:
    """Map source headers to canonical fields while preserving source ordinals.

    Explicit mapping keys use Excel-style one-based column ordinals. Mapping an
    ordinal to ``None`` explicitly ignores that source column.
    """

    explicit = dict(explicit_mappings or {})
    invalid_ordinals = sorted(
        ordinal for ordinal in explicit if ordinal < 1 or ordinal > len(headers)
    )
    if invalid_ordinals:
        raise MappingResolutionError(
            f"Explicit mappings reference columns outside the header: {invalid_ordinals}"
        )

    field_lookup = registry.fields_by_name
    working: list[_WorkingMapping] = []
    for ordinal, raw_header in enumerate(headers, start=1):
        source_header = "" if raw_header is None else str(raw_header).strip()
        normalized_header = normalize_header(source_header)
        column = SourceColumn(
            ordinal=ordinal,
            source_header=source_header,
            normalized_header=normalized_header,
        )
        candidates = registry.candidates_for(normalized_header)

        if ordinal in explicit:
            selected = explicit[ordinal]
            if selected is None:
                working.append(
                    _WorkingMapping(
                        column=column,
                        canonical_field=None,
                        classification=MappingClassification.unknown,
                        candidates=candidates,
                        required_candidates=(),
                        is_required=False,
                        explicitly_resolved=True,
                        reason_code=MappingReasonCode.explicitly_ignored,
                    )
                )
                continue
            try:
                selected_field = field_lookup[selected]
            except KeyError as exc:
                raise RegistryValidationError(f"Unknown canonical field: {selected}") from exc
            working.append(
                _WorkingMapping(
                    column=column,
                    canonical_field=selected,
                    classification=(
                        MappingClassification.required
                        if selected_field.required
                        else MappingClassification.optional
                    ),
                    candidates=candidates,
                    required_candidates=(selected,) if selected_field.required else (),
                    is_required=selected_field.required,
                    explicitly_resolved=True,
                    reason_code=MappingReasonCode.explicit_mapping,
                )
            )
            continue

        if not candidates:
            working.append(
                _WorkingMapping(
                    column=column,
                    canonical_field=None,
                    classification=MappingClassification.unknown,
                    candidates=(),
                    required_candidates=(),
                    is_required=False,
                    explicitly_resolved=False,
                    reason_code=MappingReasonCode.no_alias_match,
                )
            )
            continue

        if len(candidates) > 1:
            working.append(
                _WorkingMapping(
                    column=column,
                    canonical_field=None,
                    classification=MappingClassification.ambiguous,
                    candidates=candidates,
                    required_candidates=tuple(
                        name for name in candidates if field_lookup[name].required
                    ),
                    is_required=any(field_lookup[name].required for name in candidates),
                    explicitly_resolved=False,
                    reason_code=MappingReasonCode.alias_collision,
                )
            )
            continue

        selected = candidates[0]
        selected_field = field_lookup[selected]
        working.append(
            _WorkingMapping(
                column=column,
                canonical_field=selected,
                classification=(
                    MappingClassification.required
                    if selected_field.required
                    else MappingClassification.optional
                ),
                candidates=candidates,
                required_candidates=(selected,) if selected_field.required else (),
                is_required=selected_field.required,
                explicitly_resolved=False,
                reason_code=MappingReasonCode.alias_match,
            )
        )

    by_target: defaultdict[str, list[_WorkingMapping]] = defaultdict(list)
    for item in working:
        if item.canonical_field is not None:
            by_target[item.canonical_field].append(item)

    for target_field_name, claims in by_target.items():
        if len(claims) == 1:
            continue
        explicit_claims = [claim for claim in claims if claim.explicitly_resolved]
        if len(explicit_claims) > 1:
            ordinals = sorted(claim.column.ordinal for claim in explicit_claims)
            raise MappingResolutionError(
                f"Canonical field '{target_field_name}' is explicitly mapped more than once: "
                f"{ordinals}"
            )
        if len(explicit_claims) == 1:
            selected_claim = explicit_claims[0]
            for claim in claims:
                if claim is selected_claim:
                    continue
                claim.canonical_field = None
                claim.classification = MappingClassification.unknown
                claim.required_candidates = ()
                claim.is_required = False
                claim.reason_code = MappingReasonCode.duplicate_not_selected
            continue
        for claim in claims:
            claim.canonical_field = None
            claim.classification = MappingClassification.ambiguous
            claim.candidates = (target_field_name,)
            claim.required_candidates = (
                (target_field_name,) if field_lookup[target_field_name].required else ()
            )
            claim.is_required = field_lookup[target_field_name].required
            claim.reason_code = MappingReasonCode.duplicate_target

    resolved_fields = {
        item.canonical_field
        for item in working
        if item.canonical_field is not None
        and item.classification in (MappingClassification.required, MappingClassification.optional)
    }
    represented_candidates = {
        candidate
        for item in working
        if item.classification is MappingClassification.ambiguous
        for candidate in item.candidates
    }
    missing: list[ColumnMapping] = []
    for field_definition in registry.fields:
        if (
            field_definition.name in resolved_fields
            or field_definition.name in represented_candidates
        ):
            continue
        missing.append(
            ColumnMapping(
                column=None,
                canonical_field=field_definition.name,
                classification=MappingClassification.missing,
                candidates=(),
                required_candidates=(),
                is_required=field_definition.required,
                explicitly_resolved=False,
                reason_code=MappingReasonCode.field_missing,
            )
        )

    return MappingReport(
        registry_id=registry.registry_id,
        registry_version=registry.version,
        columns=tuple(item.freeze() for item in working),
        missing=tuple(missing),
    )
