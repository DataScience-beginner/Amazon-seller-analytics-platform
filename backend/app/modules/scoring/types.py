from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

type NumericInput = Decimal | int | float | str | None


class ScoreName(StrEnum):
    demand = "demand"
    competition = "competition"
    price_stability = "price_stability"
    data_confidence = "data_confidence"
    overall_opportunity = "overall_opportunity"


class InputState(StrEnum):
    valid = "valid"
    missing = "missing"
    invalid = "invalid"
    outlier = "outlier"


class ScoreReasonCode(StrEnum):
    input_missing = "SCORING_INPUT_MISSING"
    input_invalid = "SCORING_INPUT_INVALID"
    input_outlier = "SCORING_INPUT_OUTLIER"
    component_unavailable = "SCORING_COMPONENT_UNAVAILABLE"
    available_components_reweighted = "SCORING_AVAILABLE_COMPONENTS_REWEIGHTED"
    no_usable_inputs = "SCORING_NO_USABLE_INPUTS"
    score_weak = "SCORING_SCORE_WEAK"
    score_moderate = "SCORING_SCORE_MODERATE"
    score_strong = "SCORING_SCORE_STRONG"
    confidence_low = "SCORING_CONFIDENCE_LOW"
    confidence_medium = "SCORING_CONFIDENCE_MEDIUM"
    confidence_high = "SCORING_CONFIDENCE_HIGH"
    overall_confidence_adjusted = "SCORING_OVERALL_CONFIDENCE_ADJUSTED"


@dataclass(frozen=True, slots=True)
class MarketMetrics:
    """Canonical market inputs accepted by the Phase 1 scoring engine.

    Values may still be raw spreadsheet scalars. Parsing and all subsequent
    calculations are performed with :class:`~decimal.Decimal`.
    """

    sales_rank_current: NumericInput = None
    sales_rank_90_day_average: NumericInput = None
    rank_drops_90_days: NumericInput = None
    monthly_sold: NumericInput = None
    offer_count: NumericInput = None
    review_count: NumericInput = None
    buy_box_winner_count_90_days: NumericInput = None
    buy_box_price: NumericInput = None
    buy_box_price_90_day_average: NumericInput = None
    buy_box_oos_percent: NumericInput = None


@dataclass(frozen=True, slots=True)
class MetricInput:
    name: str
    raw_value: str | None
    parsed_value: Decimal | None
    state: InputState

    def to_dict(self) -> dict[str, str | None]:
        return {
            "name": self.name,
            "raw_value": self.raw_value,
            "parsed_value": str(self.parsed_value) if self.parsed_value is not None else None,
            "state": self.state.value,
        }


@dataclass(frozen=True, slots=True)
class ScoreReason:
    code: ScoreReasonCode
    metric: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {"code": self.code.value, "metric": self.metric}


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    name: str
    value: int | None
    configured_weight: Decimal
    effective_weight: Decimal

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "name": self.name,
            "value": self.value,
            "configured_weight": str(self.configured_weight),
            "effective_weight": str(self.effective_weight),
        }


@dataclass(frozen=True, slots=True)
class ScoreResult:
    name: ScoreName
    value: int
    formula_version: str
    inputs: tuple[MetricInput, ...]
    components: tuple[ScoreComponent, ...]
    reasons: tuple[ScoreReason, ...]

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return tuple(reason.code.value for reason in self.reasons)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name.value,
            "value": self.value,
            "formula_version": self.formula_version,
            "inputs": [item.to_dict() for item in self.inputs],
            "components": [component.to_dict() for component in self.components],
            "reasons": [reason.to_dict() for reason in self.reasons],
        }


@dataclass(frozen=True, slots=True)
class ScoreCard:
    demand: ScoreResult
    competition: ScoreResult
    price_stability: ScoreResult
    data_confidence: ScoreResult
    overall_opportunity: ScoreResult

    @property
    def scores(self) -> tuple[ScoreResult, ...]:
        return (
            self.demand,
            self.competition,
            self.price_stability,
            self.data_confidence,
            self.overall_opportunity,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "formula_version": self.demand.formula_version,
            "scores": {score.name.value: score.to_dict() for score in self.scores},
        }
