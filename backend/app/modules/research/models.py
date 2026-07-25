from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class ResearchScreenId(StrEnum):
    priority_research = "priority_research"
    promising = "promising"
    low_competition = "low_competition"
    stable_pricing = "stable_pricing"
    needs_evidence = "needs_evidence"
    all = "all"


class ResearchStatus(StrEnum):
    priority_research = "priority_research"
    promising = "promising"
    monitor = "monitor"
    insufficient_evidence = "insufficient_evidence"
    avoid = "avoid"


class BrandClassification(StrEnum):
    declared_brand = "declared_brand"
    likely_generic = "likely_generic"
    unknown = "unknown"


@dataclass(frozen=True, slots=True)
class ResearchSignals:
    demand_score: int | None
    competition_score: int | None
    price_stability_score: int | None
    data_confidence_score: int | None
    overall_opportunity_score: int | None
    current_offer_count: int | None
    buy_box_price: Decimal | None
    buy_box_price_90d: Decimal | None
    estimated_monthly_bought: int | None
    brand: str | None

    def __post_init__(self) -> None:
        for name, value in (
            ("demand_score", self.demand_score),
            ("competition_score", self.competition_score),
            ("price_stability_score", self.price_stability_score),
            ("data_confidence_score", self.data_confidence_score),
            ("overall_opportunity_score", self.overall_opportunity_score),
        ):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100
            ):
                raise ValueError(f"{name} must be an integer from 0 through 100")
        if self.current_offer_count is not None and (
            isinstance(self.current_offer_count, bool) or self.current_offer_count < 0
        ):
            raise ValueError("current_offer_count must be a non-negative integer")
        if self.estimated_monthly_bought is not None and (
            isinstance(self.estimated_monthly_bought, bool) or self.estimated_monthly_bought < 0
        ):
            raise ValueError("estimated_monthly_bought must be a non-negative integer")
        for name, money_value in (
            ("buy_box_price", self.buy_box_price),
            ("buy_box_price_90d", self.buy_box_price_90d),
        ):
            if money_value is not None and (
                not isinstance(money_value, Decimal)
                or not money_value.is_finite()
                or money_value < 0
            ):
                raise ValueError(f"{name} must be a non-negative finite Decimal")


@dataclass(frozen=True, slots=True)
class ResearchAssessment:
    status: ResearchStatus
    brand_classification: BrandClassification
    policy_version: str
    configuration_checksum: str
    reason_codes: tuple[str, ...]
    positive_signals: tuple[str, ...]
    risk_signals: tuple[str, ...]
    missing_evidence: tuple[str, ...]
