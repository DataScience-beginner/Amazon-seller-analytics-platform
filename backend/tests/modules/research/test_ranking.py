from decimal import Decimal

from app.modules.research.ranking import (
    FORMULA_VERSION,
    RankingSignals,
    load_default_ranking_config,
    rank_research_priority,
)


def test_research_priority_weights_are_versioned_and_transparent() -> None:
    config = load_default_ranking_config()

    assert config.formula_version == FORMULA_VERSION
    assert config.weights == {
        "demand": 30,
        "price_stability": 20,
        "competition_quality": 15,
        "data_confidence": 15,
        "sales_rank_trend": 10,
        "buy_box_availability": 10,
    }
    assert len(config.configuration_checksum) == 64


def test_single_seller_is_capped_and_missing_evidence_is_not_reweighted() -> None:
    ranking = rank_research_priority(
        RankingSignals(
            demand_score=90,
            price_stability_score=80,
            competition_score=100,
            data_confidence_score=85,
            sales_rank=750,
            sales_rank_90d=1000,
            offer_count=1,
            buy_box_price_available=True,
            buy_box_oos_percentage_90d=Decimal("10"),
        )
    )

    components = {component.id: component for component in ranking.components}
    assert components["competition_quality"].score == 50
    assert components["competition_quality"].reason_code == "single_seller_control_risk"
    assert components["sales_rank_trend"].score == 100
    assert components["buy_box_availability"].score == 90
    assert ranking.score == 82
    assert ranking.warning_codes == ("single_seller_control_risk",)


def test_missing_inputs_score_zero_and_are_disclosed() -> None:
    ranking = rank_research_priority(
        RankingSignals(
            demand_score=None,
            price_stability_score=None,
            competition_score=None,
            data_confidence_score=50,
            sales_rank=None,
            sales_rank_90d=None,
            offer_count=None,
            buy_box_price_available=False,
            buy_box_oos_percentage_90d=None,
        )
    )

    assert ranking.score == 8
    assert "demand_missing" in ranking.warning_codes
    assert "sales_rank_trend_missing" in ranking.warning_codes
    assert "buy_box_price_missing" in ranking.warning_codes
