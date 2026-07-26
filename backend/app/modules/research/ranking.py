from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from importlib.resources import files
from typing import Any

FORMULA_VERSION = "selleros.research-priority.v1"
_HUNDRED = Decimal("100")


@dataclass(frozen=True, slots=True)
class RankingConfig:
    formula_version: str
    weights: dict[str, int]
    rank_trend_full_score_ratio: Decimal
    rank_trend_zero_score_ratio: Decimal
    single_offer_competition_cap: int
    zero_offer_competition_cap: int
    missing_buy_box_oos_score: int
    configuration_checksum: str


@dataclass(frozen=True, slots=True)
class RankingSignals:
    demand_score: int | None
    price_stability_score: int | None
    competition_score: int | None
    data_confidence_score: int | None
    sales_rank: int | None
    sales_rank_90d: int | None
    offer_count: int | None
    buy_box_price_available: bool
    buy_box_oos_percentage_90d: Decimal | None


@dataclass(frozen=True, slots=True)
class RankingComponent:
    id: str
    label: str
    weight: int
    score: int
    reason_code: str


@dataclass(frozen=True, slots=True)
class ResearchPriorityRanking:
    score: int
    formula_version: str
    configuration_checksum: str
    components: tuple[RankingComponent, ...]
    warning_codes: tuple[str, ...]


_LABELS = {
    "demand": "Demand",
    "price_stability": "Price stability",
    "competition_quality": "Competition quality",
    "data_confidence": "Data confidence",
    "sales_rank_trend": "Sales-rank trend",
    "buy_box_availability": "Buy Box availability",
}


@lru_cache(maxsize=1)
def load_default_ranking_config() -> RankingConfig:
    raw_bytes = files("app.modules.research").joinpath("resources/ranking_v1.json").read_bytes()
    payload: dict[str, Any] = json.loads(raw_bytes)
    weights = {str(key): int(value) for key, value in payload["weights"].items()}
    if set(weights) != set(_LABELS) or sum(weights.values()) != 100:
        raise ValueError("Research-priority weights must define all components and sum to 100")
    if payload["formula_version"] != FORMULA_VERSION:
        raise ValueError("Research-priority formula version does not match the implementation")
    return RankingConfig(
        formula_version=payload["formula_version"],
        weights=weights,
        rank_trend_full_score_ratio=Decimal(str(payload["rank_trend"]["full_score_at_or_below"])),
        rank_trend_zero_score_ratio=Decimal(str(payload["rank_trend"]["zero_score_at_or_above"])),
        single_offer_competition_cap=int(payload["competition"]["single_offer_cap"]),
        zero_offer_competition_cap=int(payload["competition"]["zero_offer_cap"]),
        missing_buy_box_oos_score=int(payload["buy_box_availability"]["missing_oos_score"]),
        configuration_checksum=hashlib.sha256(raw_bytes).hexdigest(),
    )


def _rank_trend_score(signals: RankingSignals, config: RankingConfig) -> tuple[int, str]:
    if (
        signals.sales_rank is None
        or signals.sales_rank_90d is None
        or signals.sales_rank <= 0
        or signals.sales_rank_90d <= 0
    ):
        return 0, "sales_rank_trend_missing"
    ratio = Decimal(signals.sales_rank) / Decimal(signals.sales_rank_90d)
    if ratio <= config.rank_trend_full_score_ratio:
        return 100, "sales_rank_trend_improving"
    if ratio >= config.rank_trend_zero_score_ratio:
        return 0, "sales_rank_trend_declining"
    span = config.rank_trend_zero_score_ratio - config.rank_trend_full_score_ratio
    value = (config.rank_trend_zero_score_ratio - ratio) / span * _HUNDRED
    return int(value.to_integral_value(rounding=ROUND_HALF_UP)), "sales_rank_trend_measured"


def _competition_score(signals: RankingSignals, config: RankingConfig) -> tuple[int, str]:
    if signals.competition_score is None or signals.offer_count is None:
        return 0, "competition_evidence_missing"
    if signals.offer_count == 0:
        return (
            min(signals.competition_score, config.zero_offer_competition_cap),
            "zero_offers_requires_review",
        )
    if signals.offer_count == 1:
        return (
            min(signals.competition_score, config.single_offer_competition_cap),
            "single_seller_control_risk",
        )
    return signals.competition_score, "competition_quality_measured"


def _availability_score(signals: RankingSignals, config: RankingConfig) -> tuple[int, str]:
    if not signals.buy_box_price_available:
        return 0, "buy_box_price_missing"
    if signals.buy_box_oos_percentage_90d is None:
        return config.missing_buy_box_oos_score, "buy_box_oos_evidence_missing"
    bounded_oos = min(_HUNDRED, max(Decimal("0"), signals.buy_box_oos_percentage_90d))
    score = (_HUNDRED - bounded_oos).to_integral_value(rounding=ROUND_HALF_UP)
    return int(score), "buy_box_availability_measured"


def rank_research_priority(
    signals: RankingSignals, config: RankingConfig | None = None
) -> ResearchPriorityRanking:
    active = config or load_default_ranking_config()
    competition, competition_reason = _competition_score(signals, active)
    trend, trend_reason = _rank_trend_score(signals, active)
    availability, availability_reason = _availability_score(signals, active)
    values = {
        "demand": (
            signals.demand_score or 0,
            "demand_measured" if signals.demand_score is not None else "demand_missing",
        ),
        "price_stability": (
            signals.price_stability_score or 0,
            "price_stability_measured"
            if signals.price_stability_score is not None
            else "price_stability_missing",
        ),
        "competition_quality": (competition, competition_reason),
        "data_confidence": (
            signals.data_confidence_score or 0,
            "data_confidence_measured"
            if signals.data_confidence_score is not None
            else "data_confidence_missing",
        ),
        "sales_rank_trend": (trend, trend_reason),
        "buy_box_availability": (availability, availability_reason),
    }
    components = tuple(
        RankingComponent(
            id=component_id,
            label=_LABELS[component_id],
            weight=active.weights[component_id],
            score=values[component_id][0],
            reason_code=values[component_id][1],
        )
        for component_id in active.weights
    )
    weighted = (
        sum(Decimal(component.score * component.weight) for component in components) / _HUNDRED
    )
    warnings = tuple(
        component.reason_code
        for component in components
        if component.reason_code.endswith("_missing")
        or component.reason_code in {"single_seller_control_risk", "zero_offers_requires_review"}
    )
    return ResearchPriorityRanking(
        score=int(weighted.to_integral_value(rounding=ROUND_HALF_UP)),
        formula_version=active.formula_version,
        configuration_checksum=active.configuration_checksum,
        components=components,
        warning_codes=warnings,
    )
