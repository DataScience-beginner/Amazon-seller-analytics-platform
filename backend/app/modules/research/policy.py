from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from types import MappingProxyType
from typing import cast

from app.modules.research.models import ResearchScreenId

_ROOT_KEYS = {
    "schema_version",
    "policy_version",
    "avoid_overall_max",
    "evidence_confidence_min",
    "generic_brand_markers",
    "screens",
}
_SCREEN_KEYS = {
    "label",
    "description",
    "min_overall",
    "max_overall",
    "min_demand",
    "min_competition",
    "min_price_stability",
    "min_data_confidence",
    "max_data_confidence",
    "max_offer_count",
    "require_price",
}
_VERSION_PATTERN = re.compile(r"^product-research-v\d+\.\d+\.\d+$")


class ResearchPolicyError(ValueError):
    """Raised when the product-research policy cannot be executed safely."""


@dataclass(frozen=True, slots=True)
class ResearchScreen:
    id: ResearchScreenId
    label: str
    description: str
    min_overall: int | None
    max_overall: int | None
    min_demand: int | None
    min_competition: int | None
    min_price_stability: int | None
    min_data_confidence: int | None
    max_data_confidence: int | None
    max_offer_count: int | None
    require_price: bool


@dataclass(frozen=True, slots=True)
class ResearchPolicy:
    schema_version: int
    policy_version: str
    configuration_checksum: str
    avoid_overall_max: int
    evidence_confidence_min: int
    generic_brand_markers: frozenset[str]
    screens: Mapping[ResearchScreenId, ResearchScreen]


def _object(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ResearchPolicyError(f"{path} must be an object with string keys")
    return cast(dict[str, object], value)


def _exact_keys(value: dict[str, object], expected: set[str], path: str) -> None:
    if set(value) != expected:
        raise ResearchPolicyError(
            f"{path} keys do not match the contract; "
            f"missing={sorted(expected - set(value))}, unknown={sorted(set(value) - expected)}"
        )


def _integer(value: object, path: str, *, nullable: bool = False) -> int | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ResearchPolicyError(f"{path} must be an integer")
    if not 0 <= value <= 100:
        raise ResearchPolicyError(f"{path} must be between 0 and 100")
    return value


def _text(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResearchPolicyError(f"{path} must be a non-empty string")
    return value.strip()


def _screen(screen_id: ResearchScreenId, value: object) -> ResearchScreen:
    path = f"screens.{screen_id.value}"
    raw = _object(value, path)
    _exact_keys(raw, _SCREEN_KEYS, path)
    require_price = raw["require_price"]
    if not isinstance(require_price, bool):
        raise ResearchPolicyError(f"{path}.require_price must be boolean")
    max_offer_count = _integer(raw["max_offer_count"], f"{path}.max_offer_count", nullable=True)
    min_confidence = _integer(
        raw["min_data_confidence"], f"{path}.min_data_confidence", nullable=True
    )
    max_confidence = _integer(
        raw["max_data_confidence"], f"{path}.max_data_confidence", nullable=True
    )
    if (
        min_confidence is not None
        and max_confidence is not None
        and min_confidence > max_confidence
    ):
        raise ResearchPolicyError(f"{path} confidence range is inverted")
    return ResearchScreen(
        id=screen_id,
        label=_text(raw["label"], f"{path}.label"),
        description=_text(raw["description"], f"{path}.description"),
        min_overall=_integer(raw["min_overall"], f"{path}.min_overall", nullable=True),
        max_overall=_integer(raw["max_overall"], f"{path}.max_overall", nullable=True),
        min_demand=_integer(raw["min_demand"], f"{path}.min_demand", nullable=True),
        min_competition=_integer(raw["min_competition"], f"{path}.min_competition", nullable=True),
        min_price_stability=_integer(
            raw["min_price_stability"], f"{path}.min_price_stability", nullable=True
        ),
        min_data_confidence=min_confidence,
        max_data_confidence=max_confidence,
        max_offer_count=max_offer_count,
        require_price=require_price,
    )


def parse_research_policy(payload: object) -> ResearchPolicy:
    root = _object(payload, "root")
    _exact_keys(root, _ROOT_KEYS, "root")
    if root["schema_version"] != 1:
        raise ResearchPolicyError("schema_version must be 1")
    policy_version = _text(root["policy_version"], "policy_version")
    if _VERSION_PATTERN.fullmatch(policy_version) is None:
        raise ResearchPolicyError(
            "policy_version must use product-research-v<major>.<minor>.<patch>"
        )

    markers = root["generic_brand_markers"]
    if not isinstance(markers, list) or not markers:
        raise ResearchPolicyError("generic_brand_markers must be a non-empty array")
    normalized_markers: set[str] = set()
    for index, marker in enumerate(cast(list[object], markers)):
        normalized_markers.add(_text(marker, f"generic_brand_markers[{index}]").casefold())

    raw_screens = _object(root["screens"], "screens")
    expected_screens = {screen.value for screen in ResearchScreenId}
    _exact_keys(raw_screens, expected_screens, "screens")
    screens = {
        screen_id: _screen(screen_id, raw_screens[screen_id.value])
        for screen_id in ResearchScreenId
    }
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return ResearchPolicy(
        schema_version=1,
        policy_version=policy_version,
        configuration_checksum=hashlib.sha256(canonical.encode()).hexdigest(),
        avoid_overall_max=cast(int, _integer(root["avoid_overall_max"], "avoid_overall_max")),
        evidence_confidence_min=cast(
            int, _integer(root["evidence_confidence_min"], "evidence_confidence_min")
        ),
        generic_brand_markers=frozenset(normalized_markers),
        screens=MappingProxyType(screens),
    )


@lru_cache
def load_default_research_policy() -> ResearchPolicy:
    resource = files("app.modules.research").joinpath("resources/v1.json")
    try:
        payload: object = json.loads(resource.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResearchPolicyError("Research policy is not valid JSON") from exc
    return parse_research_policy(payload)
