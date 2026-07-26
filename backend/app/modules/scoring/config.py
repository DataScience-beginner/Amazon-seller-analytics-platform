from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import TypeVar, cast

from app.modules.scoring.types import ScoreName

_T = TypeVar("_T")

METRIC_NAMES = (
    "sales_rank_current",
    "sales_rank_90_day_average",
    "rank_drops_90_days",
    "monthly_sold",
    "offer_count",
    "review_count",
    "buy_box_winner_count_90_days",
    "buy_box_price",
    "buy_box_price_90_day_average",
    "buy_box_oos_percent",
)

COMPONENT_NAMES: Mapping[ScoreName, tuple[str, ...]] = MappingProxyType(
    {
        ScoreName.demand: (
            "sales_rank_current",
            "rank_drops_90_days",
            "monthly_sold",
            "rank_trend_ratio",
        ),
        ScoreName.competition: (
            "offer_count",
            "review_count",
            "buy_box_winner_count_90_days",
        ),
        ScoreName.price_stability: (
            "price_deviation_ratio",
            "buy_box_oos_percent",
        ),
    }
)

OVERALL_SCORE_NAMES = (
    ScoreName.demand,
    ScoreName.competition,
    ScoreName.price_stability,
)


class ScoringConfigError(ValueError):
    """Raised when a scoring definition cannot be validated safely."""


@dataclass(frozen=True, slots=True)
class MetricBounds:
    minimum: Decimal
    maximum: Decimal


@dataclass(frozen=True, slots=True)
class ComponentRule:
    weight: Decimal
    full_score_at: Decimal
    zero_score_at: Decimal


@dataclass(frozen=True, slots=True)
class ScoreBands:
    weak_below: int
    strong_at_or_above: int


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    schema_version: int
    formula_version: str
    metric_bounds: Mapping[str, MetricBounds]
    component_scores: Mapping[ScoreName, Mapping[str, ComponentRule]]
    data_confidence_weights: Mapping[str, Decimal]
    overall_weights: Mapping[ScoreName, Decimal]
    overall_confidence_adjustment: str
    score_bands: ScoreBands


def _freeze(values: dict[str, _T]) -> Mapping[str, _T]:
    return MappingProxyType(dict(values))


def _freeze_score_keys(values: dict[ScoreName, _T]) -> Mapping[ScoreName, _T]:
    return MappingProxyType(dict(values))


def _as_object_mapping(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ScoringConfigError(f"{path} must be a JSON object with string keys")
    return cast(dict[str, object], value)


def _require_exact_keys(mapping: Mapping[str, object], expected: set[str], path: str) -> None:
    actual = set(mapping)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise ScoringConfigError(
            f"{path} keys do not match the scoring contract; "
            f"missing={missing}, unexpected={unexpected}"
        )


def _decimal(value: object, path: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, str | int | float | Decimal):
        raise ScoringConfigError(f"{path} must be a finite decimal value")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise ScoringConfigError(f"{path} must be a finite decimal value") from exc
    if not parsed.is_finite():
        raise ScoringConfigError(f"{path} must be a finite decimal value")
    return parsed


def _integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ScoringConfigError(f"{path} must be an integer")
    return value


def _string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScoringConfigError(f"{path} must be a non-empty string")
    return value


def _validate_unit_weights(weights: Mapping[str, Decimal], path: str) -> None:
    if any(weight <= 0 for weight in weights.values()):
        raise ScoringConfigError(f"{path} weights must all be greater than zero")
    if sum(weights.values(), Decimal("0")) != Decimal("1"):
        raise ScoringConfigError(f"{path} weights must sum exactly to 1")


def _parse_metric_bounds(value: object) -> Mapping[str, MetricBounds]:
    raw = _as_object_mapping(value, "metric_bounds")
    _require_exact_keys(raw, set(METRIC_NAMES), "metric_bounds")
    bounds: dict[str, MetricBounds] = {}
    for metric_name in METRIC_NAMES:
        item = _as_object_mapping(raw[metric_name], f"metric_bounds.{metric_name}")
        _require_exact_keys(item, {"minimum", "maximum"}, f"metric_bounds.{metric_name}")
        minimum = _decimal(item["minimum"], f"metric_bounds.{metric_name}.minimum")
        maximum = _decimal(item["maximum"], f"metric_bounds.{metric_name}.maximum")
        if minimum > maximum:
            raise ScoringConfigError(f"metric_bounds.{metric_name}.minimum must not exceed maximum")
        bounds[metric_name] = MetricBounds(minimum=minimum, maximum=maximum)
    return _freeze(bounds)


def _parse_component_scores(
    value: object,
) -> Mapping[ScoreName, Mapping[str, ComponentRule]]:
    raw = _as_object_mapping(value, "component_scores")
    expected_scores = {name.value for name in COMPONENT_NAMES}
    _require_exact_keys(raw, expected_scores, "component_scores")
    groups: dict[ScoreName, Mapping[str, ComponentRule]] = {}
    for score_name, component_names in COMPONENT_NAMES.items():
        group_path = f"component_scores.{score_name.value}"
        group = _as_object_mapping(raw[score_name.value], group_path)
        _require_exact_keys(group, set(component_names), group_path)
        rules: dict[str, ComponentRule] = {}
        for component_name in component_names:
            rule_path = f"{group_path}.{component_name}"
            item = _as_object_mapping(group[component_name], rule_path)
            _require_exact_keys(
                item,
                {"weight", "full_score_at", "zero_score_at"},
                rule_path,
            )
            rule = ComponentRule(
                weight=_decimal(item["weight"], f"{rule_path}.weight"),
                full_score_at=_decimal(item["full_score_at"], f"{rule_path}.full_score_at"),
                zero_score_at=_decimal(item["zero_score_at"], f"{rule_path}.zero_score_at"),
            )
            if rule.full_score_at == rule.zero_score_at:
                raise ScoringConfigError(f"{rule_path} full_score_at and zero_score_at must differ")
            rules[component_name] = rule
        _validate_unit_weights(
            {name: rule.weight for name, rule in rules.items()},
            group_path,
        )
        groups[score_name] = _freeze(rules)
    return _freeze_score_keys(groups)


def _parse_named_weights(
    value: object,
    *,
    path: str,
    expected_names: tuple[str, ...],
) -> Mapping[str, Decimal]:
    raw = _as_object_mapping(value, path)
    _require_exact_keys(raw, set(expected_names), path)
    weights = {name: _decimal(raw[name], f"{path}.{name}") for name in expected_names}
    _validate_unit_weights(weights, path)
    return _freeze(weights)


def parse_scoring_config(payload: object) -> ScoringConfig:
    """Validate an untrusted JSON-compatible scoring definition."""

    root = _as_object_mapping(payload, "root")
    expected_root_keys = {
        "schema_version",
        "formula_version",
        "metric_bounds",
        "component_scores",
        "data_confidence_weights",
        "overall_weights",
        "overall_confidence_adjustment",
        "score_bands",
    }
    _require_exact_keys(root, expected_root_keys, "root")

    schema_version = _integer(root["schema_version"], "schema_version")
    if schema_version != 1:
        raise ScoringConfigError("schema_version must be 1")

    formula_version = _string(root["formula_version"], "formula_version")
    metric_bounds = _parse_metric_bounds(root["metric_bounds"])
    component_scores = _parse_component_scores(root["component_scores"])
    confidence_weights = _parse_named_weights(
        root["data_confidence_weights"],
        path="data_confidence_weights",
        expected_names=METRIC_NAMES,
    )

    raw_overall_weights = _parse_named_weights(
        root["overall_weights"],
        path="overall_weights",
        expected_names=tuple(name.value for name in OVERALL_SCORE_NAMES),
    )
    overall_weights = _freeze_score_keys(
        {ScoreName(name): weight for name, weight in raw_overall_weights.items()}
    )

    confidence_adjustment = _string(
        root["overall_confidence_adjustment"], "overall_confidence_adjustment"
    )
    if confidence_adjustment != "multiply":
        raise ScoringConfigError("overall_confidence_adjustment must be 'multiply'")

    raw_bands = _as_object_mapping(root["score_bands"], "score_bands")
    _require_exact_keys(
        raw_bands,
        {"weak_below", "strong_at_or_above"},
        "score_bands",
    )
    score_bands = ScoreBands(
        weak_below=_integer(raw_bands["weak_below"], "score_bands.weak_below"),
        strong_at_or_above=_integer(
            raw_bands["strong_at_or_above"], "score_bands.strong_at_or_above"
        ),
    )
    if not 0 <= score_bands.weak_below < score_bands.strong_at_or_above <= 100:
        raise ScoringConfigError(
            "score bands must satisfy 0 <= weak_below < strong_at_or_above <= 100"
        )

    return ScoringConfig(
        schema_version=schema_version,
        formula_version=formula_version,
        metric_bounds=metric_bounds,
        component_scores=component_scores,
        data_confidence_weights=confidence_weights,
        overall_weights=overall_weights,
        overall_confidence_adjustment=confidence_adjustment,
        score_bands=score_bands,
    )


def load_scoring_config(path: Path) -> ScoringConfig:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScoringConfigError(f"Unable to load scoring config from {path}") from exc
    return parse_scoring_config(payload)


@lru_cache
def load_default_scoring_config() -> ScoringConfig:
    path = Path(__file__).with_name("configs") / "v1.json"
    return load_scoring_config(path)
