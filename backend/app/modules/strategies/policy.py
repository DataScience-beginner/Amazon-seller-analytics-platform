"""Strict loader for version-controlled SellerOS strategy policies."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import cast

from app.modules.strategies.models import SCORE_MAXIMUM, SCORE_MINIMUM, Strategy

DEFAULT_POLICY_PATH = Path(__file__).with_name("policies") / "v1.json"
RULES_VERSION_PATTERN = re.compile(r"^strategy-v\d+\.\d+\.\d+$")


class PolicyValidationError(ValueError):
    """Raised when a strategy policy is not safe to execute."""


@dataclass(frozen=True, slots=True)
class ScoreRange:
    minimum: int
    maximum: int


@dataclass(frozen=True, slots=True)
class DiscoveryThresholds:
    opportunity_min: int
    minimum_history_months: int


@dataclass(frozen=True, slots=True)
class TestBuyThresholds:
    demand_min: int
    opportunity_min: int
    competition_min: int
    price_stability_min: int


@dataclass(frozen=True, slots=True)
class GrowthThresholds:
    demand_min: int
    opportunity_min: int
    competition_min: int
    price_stability_min: int
    profitability_min: int
    cash_efficiency_min: int


@dataclass(frozen=True, slots=True)
class CashCowThresholds:
    demand_min: int
    opportunity_min: int
    price_stability_min: int
    profitability_min: int
    cash_efficiency_min: int
    history_months_min: int


@dataclass(frozen=True, slots=True)
class PremiumMarginThresholds:
    demand_min: int
    demand_max: int
    opportunity_min: int
    price_stability_min: int
    profitability_min: int
    contribution_margin_percent_min: Decimal


@dataclass(frozen=True, slots=True)
class ClearanceWatchThresholds:
    units_on_hand_min: int
    inventory_risk_min: int
    stock_cover_days_min: Decimal
    risk_triggers_required: int


@dataclass(frozen=True, slots=True)
class AvoidThresholds:
    opportunity_max: int
    demand_max: int
    competition_max: int
    price_stability_max: int
    profitability_max: int
    contribution_margin_percent_max: Decimal


@dataclass(frozen=True, slots=True)
class StrategyThresholds:
    discovery: DiscoveryThresholds
    test_buy: TestBuyThresholds
    growth: GrowthThresholds
    cash_cow: CashCowThresholds
    premium_margin: PremiumMarginThresholds
    clearance_watch: ClearanceWatchThresholds
    avoid: AvoidThresholds


@dataclass(frozen=True, slots=True)
class StrategyPolicy:
    """Validated and immutable strategy policy used by the classifier."""

    schema_version: int
    rules_version: str
    score_range: ScoreRange
    low_confidence_threshold: int
    default_strategy: Strategy
    priority: tuple[Strategy, ...]
    thresholds: StrategyThresholds


def _expect_object(value: object, location: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise PolicyValidationError(f"{location} must be a JSON object")
    untyped = cast(dict[object, object], value)
    result: dict[str, object] = {}
    for key, item in untyped.items():
        if not isinstance(key, str):
            raise PolicyValidationError(f"{location} keys must be strings")
        result[key] = item
    return result


def _expect_exact_keys(value: dict[str, object], expected: set[str], location: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    messages: list[str] = []
    if missing:
        messages.append(f"missing keys: {', '.join(missing)}")
    if unknown:
        messages.append(f"unknown keys: {', '.join(unknown)}")
    if messages:
        raise PolicyValidationError(f"{location} has {'; '.join(messages)}")


def _expect_int(value: dict[str, object], key: str, location: str) -> int:
    candidate = value[key]
    if isinstance(candidate, bool) or not isinstance(candidate, int):
        raise PolicyValidationError(f"{location}.{key} must be an integer")
    return candidate


def _expect_string(value: dict[str, object], key: str, location: str) -> str:
    candidate = value[key]
    if not isinstance(candidate, str) or not candidate:
        raise PolicyValidationError(f"{location}.{key} must be a non-empty string")
    return candidate


def _expect_decimal(value: dict[str, object], key: str, location: str) -> Decimal:
    candidate = value[key]
    if not isinstance(candidate, str):
        raise PolicyValidationError(
            f"{location}.{key} must be a JSON string to preserve decimal precision"
        )
    try:
        parsed = Decimal(candidate)
    except InvalidOperation as error:
        raise PolicyValidationError(f"{location}.{key} must be a decimal string") from error
    if not parsed.is_finite():
        raise PolicyValidationError(f"{location}.{key} must be finite")
    return parsed


def _expect_score(value: int, name: str, score_range: ScoreRange) -> int:
    if not score_range.minimum <= value <= score_range.maximum:
        raise PolicyValidationError(
            f"{name} must be between {score_range.minimum} and {score_range.maximum}"
        )
    return value


def _threshold_object(
    thresholds: dict[str, object], strategy: Strategy, expected_keys: set[str]
) -> dict[str, object]:
    result = _expect_object(thresholds[strategy.value], f"thresholds.{strategy.value}")
    _expect_exact_keys(result, expected_keys, f"thresholds.{strategy.value}")
    return result


def _parse_priority(root: dict[str, object]) -> tuple[Strategy, ...]:
    raw_priority = root["priority"]
    if not isinstance(raw_priority, list):
        raise PolicyValidationError("priority must be a JSON array")
    untyped = cast(list[object], raw_priority)
    priority: list[Strategy] = []
    for index, raw_strategy in enumerate(untyped):
        if not isinstance(raw_strategy, str):
            raise PolicyValidationError(f"priority[{index}] must be a strategy string")
        try:
            priority.append(Strategy(raw_strategy))
        except ValueError as error:
            raise PolicyValidationError(
                f"priority[{index}] contains unknown strategy {raw_strategy!r}"
            ) from error

    expected = set(Strategy)
    if len(priority) != len(expected) or set(priority) != expected:
        raise PolicyValidationError("priority must contain every Phase 1 strategy exactly once")
    return tuple(priority)


def _parse_thresholds(root: dict[str, object], score_range: ScoreRange) -> StrategyThresholds:
    thresholds = _expect_object(root["thresholds"], "thresholds")
    _expect_exact_keys(thresholds, {strategy.value for strategy in Strategy}, "thresholds")

    discovery_raw = _threshold_object(
        thresholds, Strategy.DISCOVERY, {"opportunity_min", "minimum_history_months"}
    )
    discovery = DiscoveryThresholds(
        opportunity_min=_expect_score(
            _expect_int(discovery_raw, "opportunity_min", "thresholds.discovery"),
            "thresholds.discovery.opportunity_min",
            score_range,
        ),
        minimum_history_months=_expect_int(
            discovery_raw, "minimum_history_months", "thresholds.discovery"
        ),
    )
    if discovery.minimum_history_months < 1:
        raise PolicyValidationError("thresholds.discovery.minimum_history_months must be positive")

    test_buy_raw = _threshold_object(
        thresholds,
        Strategy.TEST_BUY,
        {"demand_min", "opportunity_min", "competition_min", "price_stability_min"},
    )
    test_buy = TestBuyThresholds(
        demand_min=_expect_score(
            _expect_int(test_buy_raw, "demand_min", "thresholds.test_buy"),
            "thresholds.test_buy.demand_min",
            score_range,
        ),
        opportunity_min=_expect_score(
            _expect_int(test_buy_raw, "opportunity_min", "thresholds.test_buy"),
            "thresholds.test_buy.opportunity_min",
            score_range,
        ),
        competition_min=_expect_score(
            _expect_int(test_buy_raw, "competition_min", "thresholds.test_buy"),
            "thresholds.test_buy.competition_min",
            score_range,
        ),
        price_stability_min=_expect_score(
            _expect_int(test_buy_raw, "price_stability_min", "thresholds.test_buy"),
            "thresholds.test_buy.price_stability_min",
            score_range,
        ),
    )

    growth_raw = _threshold_object(
        thresholds,
        Strategy.GROWTH,
        {
            "demand_min",
            "opportunity_min",
            "competition_min",
            "price_stability_min",
            "profitability_min",
            "cash_efficiency_min",
        },
    )
    growth = GrowthThresholds(
        demand_min=_expect_score(
            _expect_int(growth_raw, "demand_min", "thresholds.growth"),
            "thresholds.growth.demand_min",
            score_range,
        ),
        opportunity_min=_expect_score(
            _expect_int(growth_raw, "opportunity_min", "thresholds.growth"),
            "thresholds.growth.opportunity_min",
            score_range,
        ),
        competition_min=_expect_score(
            _expect_int(growth_raw, "competition_min", "thresholds.growth"),
            "thresholds.growth.competition_min",
            score_range,
        ),
        price_stability_min=_expect_score(
            _expect_int(growth_raw, "price_stability_min", "thresholds.growth"),
            "thresholds.growth.price_stability_min",
            score_range,
        ),
        profitability_min=_expect_score(
            _expect_int(growth_raw, "profitability_min", "thresholds.growth"),
            "thresholds.growth.profitability_min",
            score_range,
        ),
        cash_efficiency_min=_expect_score(
            _expect_int(growth_raw, "cash_efficiency_min", "thresholds.growth"),
            "thresholds.growth.cash_efficiency_min",
            score_range,
        ),
    )

    cash_cow_raw = _threshold_object(
        thresholds,
        Strategy.CASH_COW,
        {
            "demand_min",
            "opportunity_min",
            "price_stability_min",
            "profitability_min",
            "cash_efficiency_min",
            "history_months_min",
        },
    )
    cash_cow = CashCowThresholds(
        demand_min=_expect_score(
            _expect_int(cash_cow_raw, "demand_min", "thresholds.cash_cow"),
            "thresholds.cash_cow.demand_min",
            score_range,
        ),
        opportunity_min=_expect_score(
            _expect_int(cash_cow_raw, "opportunity_min", "thresholds.cash_cow"),
            "thresholds.cash_cow.opportunity_min",
            score_range,
        ),
        price_stability_min=_expect_score(
            _expect_int(cash_cow_raw, "price_stability_min", "thresholds.cash_cow"),
            "thresholds.cash_cow.price_stability_min",
            score_range,
        ),
        profitability_min=_expect_score(
            _expect_int(cash_cow_raw, "profitability_min", "thresholds.cash_cow"),
            "thresholds.cash_cow.profitability_min",
            score_range,
        ),
        cash_efficiency_min=_expect_score(
            _expect_int(cash_cow_raw, "cash_efficiency_min", "thresholds.cash_cow"),
            "thresholds.cash_cow.cash_efficiency_min",
            score_range,
        ),
        history_months_min=_expect_int(cash_cow_raw, "history_months_min", "thresholds.cash_cow"),
    )
    if cash_cow.history_months_min < 1:
        raise PolicyValidationError("thresholds.cash_cow.history_months_min must be positive")

    premium_raw = _threshold_object(
        thresholds,
        Strategy.PREMIUM_MARGIN,
        {
            "demand_min",
            "demand_max",
            "opportunity_min",
            "price_stability_min",
            "profitability_min",
            "contribution_margin_percent_min",
        },
    )
    premium_margin = PremiumMarginThresholds(
        demand_min=_expect_score(
            _expect_int(premium_raw, "demand_min", "thresholds.premium_margin"),
            "thresholds.premium_margin.demand_min",
            score_range,
        ),
        demand_max=_expect_score(
            _expect_int(premium_raw, "demand_max", "thresholds.premium_margin"),
            "thresholds.premium_margin.demand_max",
            score_range,
        ),
        opportunity_min=_expect_score(
            _expect_int(premium_raw, "opportunity_min", "thresholds.premium_margin"),
            "thresholds.premium_margin.opportunity_min",
            score_range,
        ),
        price_stability_min=_expect_score(
            _expect_int(premium_raw, "price_stability_min", "thresholds.premium_margin"),
            "thresholds.premium_margin.price_stability_min",
            score_range,
        ),
        profitability_min=_expect_score(
            _expect_int(premium_raw, "profitability_min", "thresholds.premium_margin"),
            "thresholds.premium_margin.profitability_min",
            score_range,
        ),
        contribution_margin_percent_min=_expect_decimal(
            premium_raw, "contribution_margin_percent_min", "thresholds.premium_margin"
        ),
    )
    if premium_margin.demand_min > premium_margin.demand_max:
        raise PolicyValidationError("thresholds.premium_margin.demand_min cannot exceed demand_max")

    monitor_raw = _threshold_object(thresholds, Strategy.MONITOR, set())
    if monitor_raw:
        raise PolicyValidationError("thresholds.monitor must be empty")

    clearance_raw = _threshold_object(
        thresholds,
        Strategy.CLEARANCE_WATCH,
        {
            "units_on_hand_min",
            "inventory_risk_min",
            "stock_cover_days_min",
            "risk_triggers_required",
        },
    )
    clearance_watch = ClearanceWatchThresholds(
        units_on_hand_min=_expect_int(
            clearance_raw, "units_on_hand_min", "thresholds.clearance_watch"
        ),
        inventory_risk_min=_expect_score(
            _expect_int(clearance_raw, "inventory_risk_min", "thresholds.clearance_watch"),
            "thresholds.clearance_watch.inventory_risk_min",
            score_range,
        ),
        stock_cover_days_min=_expect_decimal(
            clearance_raw, "stock_cover_days_min", "thresholds.clearance_watch"
        ),
        risk_triggers_required=_expect_int(
            clearance_raw, "risk_triggers_required", "thresholds.clearance_watch"
        ),
    )
    if clearance_watch.units_on_hand_min < 1:
        raise PolicyValidationError("thresholds.clearance_watch.units_on_hand_min must be positive")
    if clearance_watch.stock_cover_days_min < 0:
        raise PolicyValidationError(
            "thresholds.clearance_watch.stock_cover_days_min cannot be negative"
        )
    if clearance_watch.risk_triggers_required not in (1, 2):
        raise PolicyValidationError(
            "thresholds.clearance_watch.risk_triggers_required must be 1 or 2"
        )

    avoid_raw = _threshold_object(
        thresholds,
        Strategy.AVOID,
        {
            "opportunity_max",
            "demand_max",
            "competition_max",
            "price_stability_max",
            "profitability_max",
            "contribution_margin_percent_max",
        },
    )
    avoid = AvoidThresholds(
        opportunity_max=_expect_score(
            _expect_int(avoid_raw, "opportunity_max", "thresholds.avoid"),
            "thresholds.avoid.opportunity_max",
            score_range,
        ),
        demand_max=_expect_score(
            _expect_int(avoid_raw, "demand_max", "thresholds.avoid"),
            "thresholds.avoid.demand_max",
            score_range,
        ),
        competition_max=_expect_score(
            _expect_int(avoid_raw, "competition_max", "thresholds.avoid"),
            "thresholds.avoid.competition_max",
            score_range,
        ),
        price_stability_max=_expect_score(
            _expect_int(avoid_raw, "price_stability_max", "thresholds.avoid"),
            "thresholds.avoid.price_stability_max",
            score_range,
        ),
        profitability_max=_expect_score(
            _expect_int(avoid_raw, "profitability_max", "thresholds.avoid"),
            "thresholds.avoid.profitability_max",
            score_range,
        ),
        contribution_margin_percent_max=_expect_decimal(
            avoid_raw, "contribution_margin_percent_max", "thresholds.avoid"
        ),
    )

    return StrategyThresholds(
        discovery=discovery,
        test_buy=test_buy,
        growth=growth,
        cash_cow=cash_cow,
        premium_margin=premium_margin,
        clearance_watch=clearance_watch,
        avoid=avoid,
    )


def parse_strategy_policy(payload: object) -> StrategyPolicy:
    """Validate an already decoded JSON value and return an immutable policy."""

    root = _expect_object(payload, "policy")
    _expect_exact_keys(
        root,
        {
            "schema_version",
            "rules_version",
            "score_range",
            "low_confidence_threshold",
            "default_strategy",
            "priority",
            "thresholds",
        },
        "policy",
    )

    schema_version = _expect_int(root, "schema_version", "policy")
    if schema_version != 1:
        raise PolicyValidationError("policy.schema_version must be 1")

    rules_version = _expect_string(root, "rules_version", "policy")
    if RULES_VERSION_PATTERN.fullmatch(rules_version) is None:
        raise PolicyValidationError(
            "policy.rules_version must match strategy-v<major>.<minor>.<patch>"
        )

    score_range_raw = _expect_object(root["score_range"], "score_range")
    _expect_exact_keys(score_range_raw, {"minimum", "maximum"}, "score_range")
    score_range = ScoreRange(
        minimum=_expect_int(score_range_raw, "minimum", "score_range"),
        maximum=_expect_int(score_range_raw, "maximum", "score_range"),
    )
    if score_range != ScoreRange(SCORE_MINIMUM, SCORE_MAXIMUM):
        raise PolicyValidationError("policy.score_range must be 0 through 100")

    low_confidence_threshold = _expect_score(
        _expect_int(root, "low_confidence_threshold", "policy"),
        "policy.low_confidence_threshold",
        score_range,
    )
    if low_confidence_threshold in (score_range.minimum, score_range.maximum):
        raise PolicyValidationError(
            "policy.low_confidence_threshold must be inside the score range"
        )

    raw_default = _expect_string(root, "default_strategy", "policy")
    try:
        default_strategy = Strategy(raw_default)
    except ValueError as error:
        raise PolicyValidationError("policy.default_strategy is unknown") from error
    if default_strategy is not Strategy.MONITOR:
        raise PolicyValidationError("policy.default_strategy must be monitor")

    priority = _parse_priority(root)
    if priority[-1] is not default_strategy:
        raise PolicyValidationError("the default strategy must be last in priority")

    return StrategyPolicy(
        schema_version=schema_version,
        rules_version=rules_version,
        score_range=score_range,
        low_confidence_threshold=low_confidence_threshold,
        default_strategy=default_strategy,
        priority=priority,
        thresholds=_parse_thresholds(root, score_range),
    )


def load_strategy_policy(path: Path) -> StrategyPolicy:
    """Read and validate a JSON policy from an explicit path."""

    try:
        raw_payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyValidationError(f"Unable to read strategy policy {path}: {error}") from error
    return parse_strategy_policy(raw_payload)


@lru_cache(maxsize=1)
def load_default_strategy_policy() -> StrategyPolicy:
    """Load the bundled Phase 1 policy once after validating it."""

    return load_strategy_policy(DEFAULT_POLICY_PATH)
