from __future__ import annotations

import json

import pytest

from app.modules.imports import AliasRegistry, RegistryValidationError, normalize_header
from app.modules.imports.domain import CanonicalValueType


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (None, ""),
        ("  BUY BOX:   90 Days AVG. ", "buy box 90 days avg"),
        ("ＦＢＡ　Pick&Pack Fee", "fba pick and pack fee"),
        ("Referral Fee %", "referral fee percent"),
        ("A+B@example.com", "a plus b at example com"),
        ("Sales\u200bRank—Current", "salesrank current"),
    ],
)
def test_normalize_header_is_conservative_and_deterministic(source: object, expected: str) -> None:
    assert normalize_header(source) == expected


def test_default_registry_is_versioned_and_maps_aliases(registry: AliasRegistry) -> None:
    assert registry.registry_id == "keepa"
    assert registry.version == "1.0.0"
    assert registry.get_field("asin").required is True
    assert registry.get_field("buy_box_price").value_type is CanonicalValueType.decimal
    assert registry.candidates_for(normalize_header(" Current Buy Box Price ")) == (
        "buy_box_price",
    )
    assert registry.candidates_for(normalize_header("buy_box_price")) == ("buy_box_price",)


def test_registry_allows_cross_field_alias_collision_for_confirmation() -> None:
    registry = AliasRegistry.from_object(
        {
            "schema_version": 1,
            "registry_id": "test",
            "version": "1",
            "fields": [
                {
                    "canonical_field": "first",
                    "required": True,
                    "value_type": "text",
                    "aliases": ["Shared"],
                    "description": "First interpretation.",
                },
                {
                    "canonical_field": "second",
                    "required": False,
                    "value_type": "text",
                    "aliases": ["shared"],
                    "description": "Second interpretation.",
                },
            ],
        }
    )

    assert registry.candidates_for("shared") == ("first", "second")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "schema_version"),
        (
            {"schema_version": True, "registry_id": "test", "version": "1", "fields": []},
            "schema_version",
        ),
        (
            {"schema_version": 1, "registry_id": "Not Valid", "version": "1", "fields": []},
            "registry_id",
        ),
        (
            {"schema_version": 1, "registry_id": "test", "version": "1", "fields": []},
            "fields",
        ),
        (
            {
                "schema_version": 1,
                "registry_id": "test",
                "version": "1",
                "fields": [
                    {
                        "canonical_field": "asin",
                        "required": True,
                        "value_type": "text",
                        "aliases": ["ASIN", " asin! "],
                        "description": "Identifier.",
                    }
                ],
            },
            "duplicate aliases",
        ),
        (
            {
                "schema_version": 1,
                "registry_id": "test",
                "version": "1",
                "fields": [
                    {
                        "canonical_field": "asin",
                        "required": "yes",
                        "value_type": "text",
                        "aliases": ["ASIN"],
                        "description": "Identifier.",
                    }
                ],
            },
            "boolean",
        ),
    ],
)
def test_registry_rejects_invalid_contracts(payload: object, message: str) -> None:
    with pytest.raises(RegistryValidationError, match=message):
        AliasRegistry.from_object(payload)


def test_registry_rejects_malformed_json_and_unknown_keys() -> None:
    with pytest.raises(RegistryValidationError, match="valid JSON"):
        AliasRegistry.from_json("{")

    valid = {
        "schema_version": 1,
        "registry_id": "test",
        "version": "1",
        "fields": [
            {
                "canonical_field": "asin",
                "required": True,
                "value_type": "text",
                "aliases": ["ASIN"],
                "description": "Identifier.",
                "unexpected": "value",
            }
        ],
    }
    with pytest.raises(RegistryValidationError, match="unknown keys"):
        AliasRegistry.from_json(json.dumps(valid))
