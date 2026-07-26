"""Typed, framework-independent contracts for SellerOS strategy decisions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

SCORE_MINIMUM = 0
SCORE_MAXIMUM = 100


class Strategy(StrEnum):
    """Stable machine identifiers for the Phase 1 strategy taxonomy."""

    DISCOVERY = "discovery"
    TEST_BUY = "test_buy"
    GROWTH = "growth"
    CASH_COW = "cash_cow"
    PREMIUM_MARGIN = "premium_margin"
    MONITOR = "monitor"
    CLEARANCE_WATCH = "clearance_watch"
    AVOID = "avoid"


class ReasonCode(StrEnum):
    """Stable explanation identifiers stored with a recommendation."""

    LOW_DATA_CONFIDENCE = "low_data_confidence"
    AGGRESSIVE_RECOMMENDATION_BLOCKED = "aggressive_recommendation_blocked"
    DATA_CONFIDENCE_SUFFICIENT = "data_confidence_sufficient"
    OPPORTUNITY_UNACCEPTABLE = "opportunity_unacceptable"
    DEMAND_UNACCEPTABLE = "demand_unacceptable"
    MARKET_RISK_COMBINATION = "market_risk_combination"
    ECONOMICS_UNACCEPTABLE = "economics_unacceptable"
    NEGATIVE_CONTRIBUTION_MARGIN = "negative_contribution_margin"
    INVENTORY_AVAILABLE = "inventory_available"
    INVENTORY_RISK_HIGH = "inventory_risk_high"
    STOCK_COVER_EXCESSIVE = "stock_cover_excessive"
    HISTORY_ESTABLISHED = "history_established"
    DEMAND_STRONG = "demand_strong"
    DEMAND_STABLE = "demand_stable"
    PRICE_STABILITY_STRONG = "price_stability_strong"
    OPPORTUNITY_STRONG = "opportunity_strong"
    PROFITABILITY_HEALTHY = "profitability_healthy"
    CASH_EFFICIENCY_HEALTHY = "cash_efficiency_healthy"
    CONTRIBUTION_MARGIN_PREMIUM = "contribution_margin_premium"
    DEMAND_SELECTIVE = "demand_selective"
    DEMAND_PROMISING = "demand_promising"
    COMPETITION_ACCEPTABLE = "competition_acceptable"
    PRICE_STABILITY_ACCEPTABLE = "price_stability_acceptable"
    OPPORTUNITY_WORTH_INVESTIGATING = "opportunity_worth_investigating"
    LIMITED_HISTORY = "limited_history"
    ECONOMICS_NOT_AVAILABLE = "economics_not_available"
    NO_STRATEGY_RULE_MATCHED = "no_strategy_rule_matched"


class EvidencePolarity(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    INFORMATIONAL = "informational"


class EvidenceSource(StrEnum):
    MARKET_SCORE = "market_score"
    ECONOMICS = "economics"
    INVENTORY = "inventory"
    HISTORY = "history"
    POLICY = "policy"


class EvidenceComparison(StrEnum):
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    BETWEEN_INCLUSIVE = "between_inclusive"
    MISSING = "missing"
    FALLBACK = "fallback"


EvidenceValue = int | Decimal | str | bool | None


def _validate_score(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not SCORE_MINIMUM <= value <= SCORE_MAXIMUM:
        raise ValueError(f"{name} must be between {SCORE_MINIMUM} and {SCORE_MAXIMUM}")


def _validate_decimal(name: str, value: Decimal, *, minimum: Decimal | None = None) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be a Decimal")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")


@dataclass(frozen=True, slots=True)
class MarketScores:
    """Phase 1 scores consumed by the classifier, independent of score implementation."""

    demand: int
    competition: int
    price_stability: int
    data_confidence: int
    overall_opportunity: int

    def __post_init__(self) -> None:
        for name, value in (
            ("demand", self.demand),
            ("competition", self.competition),
            ("price_stability", self.price_stability),
            ("data_confidence", self.data_confidence),
            ("overall_opportunity", self.overall_opportunity),
        ):
            _validate_score(name, value)

    @classmethod
    def from_mapping(cls, values: Mapping[str, int]) -> MarketScores:
        """Adapt a protocol-compatible scoring result without importing its implementation."""

        required = (
            "demand",
            "competition",
            "price_stability",
            "data_confidence",
            "overall_opportunity",
        )
        missing = [name for name in required if name not in values]
        if missing:
            raise ValueError(f"Missing strategy scores: {', '.join(missing)}")
        return cls(
            demand=values["demand"],
            competition=values["competition"],
            price_stability=values["price_stability"],
            data_confidence=values["data_confidence"],
            overall_opportunity=values["overall_opportunity"],
        )


@dataclass(frozen=True, slots=True)
class EconomicsSignals:
    """Complete business-economics inputs required by economics-based strategies."""

    profitability_score: int
    cash_efficiency_score: int
    contribution_margin_percent: Decimal

    def __post_init__(self) -> None:
        _validate_score("profitability_score", self.profitability_score)
        _validate_score("cash_efficiency_score", self.cash_efficiency_score)
        _validate_decimal("contribution_margin_percent", self.contribution_margin_percent)


@dataclass(frozen=True, slots=True)
class InventorySignals:
    """Complete inventory inputs required by inventory-risk strategies."""

    inventory_risk_score: int
    units_on_hand: int
    stock_cover_days: Decimal

    def __post_init__(self) -> None:
        _validate_score("inventory_risk_score", self.inventory_risk_score)
        if isinstance(self.units_on_hand, bool) or not isinstance(self.units_on_hand, int):
            raise TypeError("units_on_hand must be an integer")
        if self.units_on_hand < 0:
            raise ValueError("units_on_hand cannot be negative")
        _validate_decimal("stock_cover_days", self.stock_cover_days, minimum=Decimal(0))


@dataclass(frozen=True, slots=True)
class StrategyContext:
    """All deterministic facts available to one classification decision."""

    scores: MarketScores
    history_months: int = 1
    economics: EconomicsSignals | None = None
    inventory: InventorySignals | None = None

    def __post_init__(self) -> None:
        if isinstance(self.history_months, bool) or not isinstance(self.history_months, int):
            raise TypeError("history_months must be an integer")
        if self.history_months < 1:
            raise ValueError("history_months must be at least 1")


@dataclass(frozen=True, slots=True)
class StrategyEvidence:
    """One structured, machine-readable fact supporting a recommendation."""

    reason_code: ReasonCode
    polarity: EvidencePolarity
    source: EvidenceSource
    signal: str
    observed_value: EvidenceValue
    comparison: EvidenceComparison
    threshold_value: EvidenceValue = None
    threshold_upper_value: EvidenceValue = None
    statement: str = ""


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    """Immutable output from one version of the deterministic rule policy."""

    strategy: Strategy
    rules_version: str
    evidence: tuple[StrategyEvidence, ...]
    matched_candidates: tuple[Strategy, ...]

    def __post_init__(self) -> None:
        if not self.rules_version:
            raise ValueError("rules_version cannot be empty")
        if len(self.evidence) < 2:
            raise ValueError("a strategy decision must include at least two evidence items")
        if not self.matched_candidates or self.matched_candidates[0] is not self.strategy:
            raise ValueError("the selected strategy must be the first matched candidate")

    @property
    def reason_codes(self) -> tuple[ReasonCode, ...]:
        """Return reason codes in deterministic evidence order without duplicates."""

        return tuple(dict.fromkeys(item.reason_code for item in self.evidence))
