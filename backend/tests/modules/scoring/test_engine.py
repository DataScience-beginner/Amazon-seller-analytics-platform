from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from app.modules.scoring import (
    InputState,
    MarketMetrics,
    ScoreReasonCode,
    ScoringConfigError,
    load_default_scoring_config,
    parse_scoring_config,
    score_market_metrics,
)
from app.modules.scoring import config as scoring_config_module


def _complete_metrics() -> MarketMetrics:
    return MarketMetrics(
        sales_rank_current=100_000,
        sales_rank_90_day_average=120_000,
        rank_drops_90_days=45,
        monthly_sold=150,
        offer_count=10,
        review_count=1_000,
        buy_box_winner_count_90_days=5,
        buy_box_price="₹90.00",
        buy_box_price_90_day_average="100.00",
        buy_box_oos_percent="10%",
    )


def _raw_default_config() -> dict[str, Any]:
    config_path = Path(scoring_config_module.__file__).with_name("configs") / "v1.json"
    payload: object = json.loads(config_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_default_config_is_versioned_and_validated() -> None:
    config = load_default_scoring_config()

    assert config.schema_version == 1
    assert config.formula_version == "selleros.market-opportunity.v1"
    assert sum(config.data_confidence_weights.values()) == 1
    assert sum(config.overall_weights.values()) == 1


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda payload: payload["overall_weights"].__setitem__("demand", "0.44"),
            "weights must sum exactly to 1",
        ),
        (
            lambda payload: payload["component_scores"]["demand"]["sales_rank_current"].__setitem__(
                "zero_score_at", "10000"
            ),
            "full_score_at and zero_score_at must differ",
        ),
        (
            lambda payload: payload.__setitem__("formula_version", ""),
            "must be a non-empty string",
        ),
    ],
)
def test_invalid_config_is_rejected(
    mutation: Any,
    message: str,
) -> None:
    payload = deepcopy(_raw_default_config())
    mutation(payload)

    with pytest.raises(ScoringConfigError, match=message):
        parse_scoring_config(payload)


def test_representative_product_has_fixed_expected_scores() -> None:
    score_card = score_market_metrics(_complete_metrics())

    assert score_card.demand.value == 66
    assert score_card.competition.value == 68
    assert score_card.price_stability.value == 67
    assert score_card.data_confidence.value == 100
    assert score_card.overall_opportunity.value == 67
    assert {score.formula_version for score in score_card.scores} == {
        "selleros.market-opportunity.v1"
    }


def test_configured_best_and_worst_boundaries_return_zero_or_one_hundred() -> None:
    best = score_market_metrics(
        MarketMetrics(
            sales_rank_current="10,000",
            sales_rank_90_day_average="20,000",
            rank_drops_90_days=90,
            monthly_sold=300,
            offer_count=1,
            review_count=25,
            buy_box_winner_count_90_days=1,
            buy_box_price="$1,000",
            buy_box_price_90_day_average=1_000,
            buy_box_oos_percent="0%",
        )
    )
    worst = score_market_metrics(
        MarketMetrics(
            sales_rank_current=500_000,
            sales_rank_90_day_average=400_000,
            rank_drops_90_days=0,
            monthly_sold=0,
            offer_count=25,
            review_count=5_000,
            buy_box_winner_count_90_days=12,
            buy_box_price=130,
            buy_box_price_90_day_average=100,
            buy_box_oos_percent=30,
        )
    )

    assert [score.value for score in best.scores] == [100, 100, 100, 100, 100]
    assert [score.value for score in worst.scores] == [0, 0, 0, 100, 0]


def test_missing_inputs_reduce_confidence_and_explicitly_adjust_overall() -> None:
    score_card = score_market_metrics(MarketMetrics(sales_rank_current=10_000))

    assert score_card.demand.value == 100
    assert score_card.data_confidence.value == 15
    assert score_card.overall_opportunity.value == 7
    assert ScoreReasonCode.available_components_reweighted.value in (score_card.demand.reason_codes)
    assert ScoreReasonCode.confidence_low.value in score_card.data_confidence.reason_codes
    assert ScoreReasonCode.overall_confidence_adjusted.value in (
        score_card.overall_opportunity.reason_codes
    )


def test_invalid_outlier_and_zero_average_values_are_excluded_without_crashing() -> None:
    score_card = score_market_metrics(
        MarketMetrics(
            sales_rank_current="not-a-rank",
            sales_rank_90_day_average=0,
            rank_drops_90_days=float("nan"),
            monthly_sold=-1,
            offer_count=True,
            buy_box_price=float("inf"),
            buy_box_price_90_day_average=0,
            buy_box_oos_percent=101,
        )
    )
    confidence_inputs = {item.name: item for item in score_card.data_confidence.inputs}

    assert confidence_inputs["sales_rank_current"].state is InputState.invalid
    assert confidence_inputs["sales_rank_90_day_average"].state is InputState.outlier
    assert confidence_inputs["rank_drops_90_days"].state is InputState.invalid
    assert confidence_inputs["monthly_sold"].state is InputState.outlier
    assert confidence_inputs["offer_count"].state is InputState.invalid
    assert confidence_inputs["buy_box_oos_percent"].state is InputState.outlier
    assert ScoreReasonCode.input_invalid.value in score_card.data_confidence.reason_codes
    assert ScoreReasonCode.input_outlier.value in score_card.data_confidence.reason_codes
    assert all(0 <= score.value <= 100 for score in score_card.scores)


@pytest.mark.parametrize(
    "metrics",
    [
        MarketMetrics(),
        MarketMetrics(sales_rank_current=1, offer_count=0, buy_box_oos_percent=0),
        MarketMetrics(
            sales_rank_current=100_000_000,
            sales_rank_90_day_average=100_000_000,
            rank_drops_90_days=1_000_000,
            monthly_sold=1_000_000,
            offer_count=100_000,
            review_count=1_000_000_000,
            buy_box_winner_count_90_days=1_000_000,
            buy_box_price=1_000_000_000,
            buy_box_price_90_day_average=1_000_000_000,
            buy_box_oos_percent=100,
        ),
        MarketMetrics(
            sales_rank_current=9_999_999_999,
            offer_count=-100,
            buy_box_price="garbage",
        ),
    ],
)
def test_every_score_is_always_within_contract_range(metrics: MarketMetrics) -> None:
    score_card = score_market_metrics(metrics)

    assert all(0 <= score.value <= 100 for score in score_card.scores)


def test_scoring_is_deterministic_and_serializes_decimals_as_strings() -> None:
    first = score_market_metrics(_complete_metrics())
    second = score_market_metrics(_complete_metrics())

    assert first == second
    serialized = first.to_dict()
    scores = serialized["scores"]
    assert isinstance(scores, dict)
    demand = scores["demand"]
    assert isinstance(demand, dict)
    first_component = demand["components"][0]
    assert first_component["configured_weight"] == "0.35"
    assert not isinstance(first_component["configured_weight"], float)
