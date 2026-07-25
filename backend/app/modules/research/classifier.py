from __future__ import annotations

from app.modules.research.models import (
    BrandClassification,
    ResearchAssessment,
    ResearchScreenId,
    ResearchSignals,
    ResearchStatus,
)
from app.modules.research.policy import ResearchPolicy, ResearchScreen


def _brand_classification(brand: str | None, policy: ResearchPolicy) -> BrandClassification:
    normalized = brand.strip().casefold() if brand else ""
    if not normalized:
        return BrandClassification.unknown
    if normalized in policy.generic_brand_markers:
        return BrandClassification.likely_generic
    return BrandClassification.declared_brand


def matches_screen(signals: ResearchSignals, screen: ResearchScreen) -> bool:
    values = (
        (signals.overall_opportunity_score, screen.min_overall, screen.max_overall),
        (signals.demand_score, screen.min_demand, None),
        (signals.competition_score, screen.min_competition, None),
        (signals.price_stability_score, screen.min_price_stability, None),
        (
            signals.data_confidence_score,
            screen.min_data_confidence,
            screen.max_data_confidence,
        ),
    )
    for value, minimum, maximum in values:
        if minimum is not None and (value is None or value < minimum):
            return False
        if maximum is not None and (value is None or value > maximum):
            return False
    if screen.max_offer_count is not None and (
        signals.current_offer_count is None or signals.current_offer_count > screen.max_offer_count
    ):
        return False
    return not screen.require_price or signals.buy_box_price is not None


def classify_research_product(
    signals: ResearchSignals,
    policy: ResearchPolicy,
) -> ResearchAssessment:
    brand_classification = _brand_classification(signals.brand, policy)
    missing: list[str] = []
    for field, value in (
        ("demand_score", signals.demand_score),
        ("competition_score", signals.competition_score),
        ("price_stability_score", signals.price_stability_score),
        ("data_confidence_score", signals.data_confidence_score),
        ("overall_opportunity_score", signals.overall_opportunity_score),
        ("current_offer_count", signals.current_offer_count),
        ("buy_box_price", signals.buy_box_price),
    ):
        if value is None:
            missing.append(field)
    if signals.estimated_monthly_bought is None:
        missing.append("estimated_monthly_bought")

    if (
        signals.overall_opportunity_score is not None
        and signals.overall_opportunity_score <= policy.avoid_overall_max
    ):
        status = ResearchStatus.avoid
    elif (
        signals.data_confidence_score is None
        or signals.data_confidence_score < policy.evidence_confidence_min
        or any(name != "estimated_monthly_bought" for name in missing)
    ):
        status = ResearchStatus.insufficient_evidence
    elif matches_screen(signals, policy.screens[ResearchScreenId.priority_research]):
        status = ResearchStatus.priority_research
    elif matches_screen(signals, policy.screens[ResearchScreenId.promising]):
        status = ResearchStatus.promising
    else:
        status = ResearchStatus.monitor

    positives: list[str] = []
    risks: list[str] = []
    reasons: list[str] = [f"research_status_{status.value}"]
    if signals.demand_score is not None and signals.demand_score >= 80:
        positives.append("Demand score indicates strong market activity.")
        reasons.append("demand_score_strong")
    if signals.competition_score is not None and signals.competition_score >= 80:
        positives.append("Competition score indicates a more approachable seller environment.")
        reasons.append("competition_score_approachable")
    if signals.price_stability_score is not None and signals.price_stability_score >= 80:
        positives.append("Price stability is strong relative to the configured market policy.")
        reasons.append("price_stability_strong")
    if signals.current_offer_count is not None and signals.current_offer_count <= 3:
        positives.append("The ASIN currently has three or fewer seller offers.")
        reasons.append("current_offer_count_low")
    if signals.estimated_monthly_bought is not None:
        positives.append("Keepa provides a bought-in-past-month estimate for demand context.")
        reasons.append("monthly_bought_estimate_available")

    if brand_classification is BrandClassification.declared_brand:
        risks.append("A declared brand is present; selling authorisation is not verified.")
        reasons.append("declared_brand_authorisation_unverified")
    elif brand_classification is BrandClassification.likely_generic:
        risks.append("The source brand looks generic; confirm the listing and packaging manually.")
        reasons.append("generic_brand_requires_validation")
    else:
        risks.append("Brand evidence is missing; brand and restriction risk require manual review.")
        reasons.append("brand_evidence_missing")
    if signals.current_offer_count is not None and signals.current_offer_count > 5:
        risks.append("More than five current offers may increase Buy Box competition.")
        reasons.append("current_offer_count_elevated")
    if signals.buy_box_price is not None and signals.buy_box_price_90d is not None:
        deviation = abs(signals.buy_box_price - signals.buy_box_price_90d)
        if signals.buy_box_price_90d > 0 and deviation / signals.buy_box_price_90d > 0.15:
            risks.append("Current price differs from the 90-day average by more than 15%.")
            reasons.append("current_price_deviation_high")
    if not positives:
        positives.append("No strong positive signal passed the Product Research v1 thresholds.")

    missing_messages = tuple(
        {
            "demand_score": "Demand score is unavailable.",
            "competition_score": "Competition score is unavailable.",
            "price_stability_score": "Price stability score is unavailable.",
            "data_confidence_score": "Data confidence score is unavailable.",
            "overall_opportunity_score": "Overall opportunity score is unavailable.",
            "current_offer_count": "Current seller-offer count is unavailable.",
            "buy_box_price": "Current Buy Box price is unavailable.",
            "estimated_monthly_bought": (
                "Keepa bought-in-past-month estimate is unavailable; demand remains score-based."
            ),
        }[name]
        for name in missing
    )
    return ResearchAssessment(
        status=status,
        brand_classification=brand_classification,
        policy_version=policy.policy_version,
        configuration_checksum=policy.configuration_checksum,
        reason_codes=tuple(dict.fromkeys(reasons)),
        positive_signals=tuple(positives[:4]),
        risk_signals=tuple(risks[:4]),
        missing_evidence=missing_messages,
    )
