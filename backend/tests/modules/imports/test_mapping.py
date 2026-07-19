from __future__ import annotations

import pytest

from app.modules.imports import (
    AliasRegistry,
    MappingClassification,
    MappingResolutionError,
    RegistryValidationError,
    map_headers,
)
from app.modules.imports.domain import MappingReasonCode


def _collision_registry() -> AliasRegistry:
    return AliasRegistry.from_object(
        {
            "schema_version": 1,
            "registry_id": "collision_test",
            "version": "1.2.3",
            "fields": [
                {
                    "canonical_field": "asin",
                    "required": True,
                    "value_type": "text",
                    "aliases": ["ASIN", "Identifier"],
                    "description": "Product identifier.",
                },
                {
                    "canonical_field": "merchant_sku",
                    "required": False,
                    "value_type": "text",
                    "aliases": ["SKU", "Identifier"],
                    "description": "Seller SKU.",
                },
                {
                    "canonical_field": "title",
                    "required": False,
                    "value_type": "text",
                    "aliases": ["Title"],
                    "description": "Title.",
                },
            ],
        }
    )


def test_mapping_reports_required_optional_unknown_and_missing(
    registry: AliasRegistry,
) -> None:
    report = map_headers(
        [" amazon asin ", "Product Name", "Vendor Secret", "Referral Fee%"], registry
    )

    assert [entry.classification for entry in report.columns] == [
        MappingClassification.required,
        MappingClassification.optional,
        MappingClassification.unknown,
        MappingClassification.optional,
    ]
    assert report.columns[0].canonical_field == "asin"
    assert report.columns[0].column is not None
    assert report.columns[0].column.ordinal == 1
    assert report.columns[2].reason_code is MappingReasonCode.no_alias_match
    assert report.missing_required_fields == ()
    assert "brand" in {entry.canonical_field for entry in report.missing if not entry.is_required}
    assert report.resolved_by_field["title"].column is not None


def test_missing_required_field_is_explicitly_reported(registry: AliasRegistry) -> None:
    report = map_headers(["Title", "Brand"], registry)

    assert report.missing_required_fields == ("asin",)
    assert report.unresolved_required_fields == ("asin",)
    missing_asin = next(entry for entry in report.missing if entry.canonical_field == "asin")
    assert missing_asin.classification is MappingClassification.missing
    assert missing_asin.reason_code is MappingReasonCode.field_missing


def test_alias_collision_requires_confirmation_and_can_be_resolved() -> None:
    registry = _collision_registry()
    unresolved = map_headers(["Identifier", "Title"], registry)

    ambiguous = unresolved.columns[0]
    assert ambiguous.classification is MappingClassification.ambiguous
    assert ambiguous.candidates == ("asin", "merchant_sku")
    assert ambiguous.required_candidates == ("asin",)
    assert unresolved.requires_confirmation is True
    assert unresolved.unresolved_required_fields == ("asin",)

    resolved = map_headers(["Identifier", "Title"], registry, explicit_mappings={1: "asin"})
    assert resolved.requires_confirmation is False
    assert resolved.missing_required_fields == ()
    assert resolved.columns[0].canonical_field == "asin"
    assert resolved.columns[0].explicitly_resolved is True
    assert resolved.columns[0].reason_code is MappingReasonCode.explicit_mapping


def test_duplicate_automatic_targets_are_not_guessed(registry: AliasRegistry) -> None:
    report = map_headers(["ASIN", "Amazon ASIN", "Title"], registry)

    assert report.requires_confirmation is True
    assert report.missing_required_fields == ()
    assert report.unresolved_required_fields == ("asin",)
    for entry in report.columns[:2]:
        assert entry.canonical_field is None
        assert entry.classification is MappingClassification.ambiguous
        assert entry.candidates == ("asin",)
        assert entry.reason_code is MappingReasonCode.duplicate_target


def test_explicit_decision_wins_over_automatic_duplicate(registry: AliasRegistry) -> None:
    report = map_headers(
        ["ASIN", "Amazon ASIN", "Title"],
        registry,
        explicit_mappings={2: "asin"},
    )

    assert report.requires_confirmation is False
    assert report.columns[1].canonical_field == "asin"
    assert report.columns[1].reason_code is MappingReasonCode.explicit_mapping
    assert report.columns[0].canonical_field is None
    assert report.columns[0].classification is MappingClassification.unknown
    assert report.columns[0].reason_code is MappingReasonCode.duplicate_not_selected


def test_explicit_ignore_preserves_column_but_restores_required_missing(
    registry: AliasRegistry,
) -> None:
    report = map_headers(["ASIN", "Title"], registry, explicit_mappings={1: None})

    ignored = report.columns[0]
    assert ignored.classification is MappingClassification.unknown
    assert ignored.canonical_field is None
    assert ignored.explicitly_resolved is True
    assert ignored.reason_code is MappingReasonCode.explicitly_ignored
    assert report.missing_required_fields == ("asin",)


def test_explicit_mapping_can_resolve_an_unknown_vendor_header(registry: AliasRegistry) -> None:
    report = map_headers(["Vendor Identifier", "Title"], registry, explicit_mappings={1: "asin"})

    assert report.columns[0].candidates == ()
    assert report.columns[0].canonical_field == "asin"
    assert report.missing_required_fields == ()


def test_conflicting_or_invalid_explicit_decisions_are_rejected(registry: AliasRegistry) -> None:
    with pytest.raises(MappingResolutionError, match="explicitly mapped more than once"):
        map_headers(
            ["First", "Second"],
            registry,
            explicit_mappings={1: "asin", 2: "asin"},
        )

    with pytest.raises(MappingResolutionError, match="outside the header"):
        map_headers(["ASIN"], registry, explicit_mappings={2: "asin"})

    with pytest.raises(RegistryValidationError, match="Unknown canonical field"):
        map_headers(["ASIN"], registry, explicit_mappings={1: "not_a_field"})
