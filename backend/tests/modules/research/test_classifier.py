from dataclasses import replace
from decimal import Decimal
from typing import Any, cast

import pytest

from app.modules.research import (
    BrandClassification,
    ResearchPolicyError,
    ResearchSignals,
    ResearchStatus,
    classify_research_product,
    load_default_research_policy,
)
from app.modules.research.policy import parse_research_policy


def _signals(**overrides: object) -> ResearchSignals:
    base = ResearchSignals(
        demand_score=90,
        competition_score=90,
        price_stability_score=90,
        data_confidence_score=90,
        overall_opportunity_score=88,
        current_offer_count=2,
        buy_box_price=Decimal("1499.00"),
        buy_box_price_90d=Decimal("1450.00"),
        estimated_monthly_bought=500,
        brand="Synthetic Brand",
    )
    return replace(base, **cast(dict[str, Any], overrides))


def test_priority_research_is_explainable_and_not_a_buy_claim() -> None:
    assessment = classify_research_product(_signals(), load_default_research_policy())

    assert assessment.status is ResearchStatus.priority_research
    assert assessment.brand_classification is BrandClassification.declared_brand
    assert "declared_brand_authorisation_unverified" in assessment.reason_codes
    assert any("authorisation is not verified" in item for item in assessment.risk_signals)
    assert assessment.policy_version == "product-research-v1.0.0"
    assert len(assessment.configuration_checksum) == 64


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"data_confidence_score": 60}, ResearchStatus.insufficient_evidence),
        ({"buy_box_price": None}, ResearchStatus.insufficient_evidence),
        ({"overall_opportunity_score": 35}, ResearchStatus.avoid),
        (
            {
                "overall_opportunity_score": 78,
                "demand_score": 78,
                "competition_score": 75,
                "price_stability_score": 75,
                "current_offer_count": 4,
            },
            ResearchStatus.promising,
        ),
        ({"overall_opportunity_score": 65}, ResearchStatus.monitor),
    ],
)
def test_status_boundaries(overrides: dict[str, object], expected: ResearchStatus) -> None:
    assessment = classify_research_product(
        _signals(**overrides),
        load_default_research_policy(),
    )
    assert assessment.status is expected


def test_explicit_generic_and_missing_brand_are_not_guessed() -> None:
    policy = load_default_research_policy()
    generic = classify_research_product(_signals(brand="Generic"), policy)
    unknown = classify_research_product(_signals(brand=None), policy)

    assert generic.brand_classification is BrandClassification.likely_generic
    assert unknown.brand_classification is BrandClassification.unknown
    assert "brand_evidence_missing" in unknown.reason_codes


def test_policy_parser_fails_closed() -> None:
    with pytest.raises(ResearchPolicyError, match="keys do not match"):
        parse_research_policy({"schema_version": 1})
