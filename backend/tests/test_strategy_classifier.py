from __future__ import annotations

import json
from collections.abc import Callable
from decimal import Decimal
from typing import cast

import pytest

from app.modules.strategies import (
    DEFAULT_POLICY_PATH,
    EconomicsSignals,
    EvidenceComparison,
    InventorySignals,
    MarketScores,
    PolicyValidationError,
    ReasonCode,
    Strategy,
    StrategyClassifier,
    StrategyContext,
    load_strategy_policy,
    parse_strategy_policy,
)


def _scores(
    *,
    demand: int,
    competition: int,
    price_stability: int,
    confidence: int,
    opportunity: int,
) -> MarketScores:
    return MarketScores(
        demand=demand,
        competition=competition,
        price_stability=price_stability,
        data_confidence=confidence,
        overall_opportunity=opportunity,
    )


def _economics(
    profitability: int = 75,
    cash_efficiency: int = 70,
    contribution_margin: str = "25",
) -> EconomicsSignals:
    return EconomicsSignals(
        profitability_score=profitability,
        cash_efficiency_score=cash_efficiency,
        contribution_margin_percent=Decimal(contribution_margin),
    )


STRATEGY_CASES = (
    (
        StrategyContext(
            scores=_scores(
                demand=50,
                competition=60,
                price_stability=60,
                confidence=80,
                opportunity=55,
            )
        ),
        Strategy.DISCOVERY,
    ),
    (
        StrategyContext(
            scores=_scores(
                demand=70,
                competition=60,
                price_stability=60,
                confidence=80,
                opportunity=70,
            ),
            history_months=3,
        ),
        Strategy.TEST_BUY,
    ),
    (
        StrategyContext(
            scores=_scores(
                demand=85,
                competition=70,
                price_stability=60,
                confidence=90,
                opportunity=85,
            ),
            history_months=3,
            economics=_economics(profitability=70, cash_efficiency=65),
        ),
        Strategy.GROWTH,
    ),
    (
        StrategyContext(
            scores=_scores(
                demand=85,
                competition=70,
                price_stability=85,
                confidence=90,
                opportunity=85,
            ),
            history_months=8,
            economics=_economics(profitability=75, cash_efficiency=80),
        ),
        Strategy.CASH_COW,
    ),
    (
        StrategyContext(
            scores=_scores(
                demand=50,
                competition=65,
                price_stability=70,
                confidence=85,
                opportunity=65,
            ),
            history_months=4,
            economics=_economics(profitability=85, cash_efficiency=60, contribution_margin="35"),
        ),
        Strategy.PREMIUM_MARGIN,
    ),
    (
        StrategyContext(
            scores=_scores(
                demand=40,
                competition=55,
                price_stability=50,
                confidence=80,
                opportunity=40,
            ),
            history_months=3,
        ),
        Strategy.MONITOR,
    ),
    (
        StrategyContext(
            scores=_scores(
                demand=60,
                competition=60,
                price_stability=60,
                confidence=80,
                opportunity=60,
            ),
            history_months=3,
            inventory=InventorySignals(
                inventory_risk_score=80,
                units_on_hand=50,
                stock_cover_days=Decimal("100"),
            ),
        ),
        Strategy.CLEARANCE_WATCH,
    ),
    (
        StrategyContext(
            scores=_scores(
                demand=20,
                competition=55,
                price_stability=50,
                confidence=80,
                opportunity=35,
            ),
            history_months=3,
        ),
        Strategy.AVOID,
    ),
)


@pytest.mark.parametrize(("context", "expected_strategy"), STRATEGY_CASES)
def test_classifier_covers_every_phase_one_strategy(
    context: StrategyContext, expected_strategy: Strategy
) -> None:
    decision = StrategyClassifier().classify(context)

    assert decision.strategy is expected_strategy
    assert decision.rules_version == "strategy-v1.0.0"
    assert len(decision.evidence) >= 2
    assert decision.reason_codes
    assert decision.matched_candidates[0] is expected_strategy
    assert all(item.statement for item in decision.evidence)


def test_low_confidence_gate_blocks_action_oriented_matches() -> None:
    context = StrategyContext(
        scores=_scores(
            demand=90,
            competition=90,
            price_stability=90,
            confidence=49,
            opportunity=90,
        ),
        history_months=12,
        economics=_economics(profitability=95, cash_efficiency=95, contribution_margin="50"),
        inventory=InventorySignals(
            inventory_risk_score=95,
            units_on_hand=500,
            stock_cover_days=Decimal("300"),
        ),
    )

    decision = StrategyClassifier().classify(context)

    assert decision.strategy is Strategy.DISCOVERY
    assert decision.matched_candidates == (Strategy.DISCOVERY,)
    assert decision.reason_codes == (
        ReasonCode.LOW_DATA_CONFIDENCE,
        ReasonCode.AGGRESSIVE_RECOMMENDATION_BLOCKED,
    )


def test_confidence_threshold_is_inclusive() -> None:
    context = StrategyContext(
        scores=_scores(
            demand=40,
            competition=55,
            price_stability=50,
            confidence=50,
            opportunity=40,
        ),
        history_months=3,
    )

    decision = StrategyClassifier().classify(context)

    assert decision.strategy is Strategy.MONITOR
    assert ReasonCode.LOW_DATA_CONFIDENCE not in decision.reason_codes


def test_import_only_context_cannot_claim_business_input_strategies() -> None:
    import_only = StrategyContext(
        scores=_scores(
            demand=90,
            competition=90,
            price_stability=90,
            confidence=90,
            opportunity=90,
        ),
        history_months=12,
    )

    decision = StrategyClassifier().classify(import_only)

    business_input_strategies = {
        Strategy.GROWTH,
        Strategy.CASH_COW,
        Strategy.PREMIUM_MARGIN,
        Strategy.CLEARANCE_WATCH,
    }
    assert decision.strategy is Strategy.TEST_BUY
    assert business_input_strategies.isdisjoint(decision.matched_candidates)


def test_clearance_watch_requires_units_exposed_to_inventory_risk() -> None:
    context = StrategyContext(
        scores=_scores(
            demand=50,
            competition=60,
            price_stability=60,
            confidence=80,
            opportunity=55,
        ),
        history_months=3,
        inventory=InventorySignals(
            inventory_risk_score=100,
            units_on_hand=0,
            stock_cover_days=Decimal("500"),
        ),
    )

    decision = StrategyClassifier().classify(context)

    assert decision.strategy is Strategy.DISCOVERY
    assert Strategy.CLEARANCE_WATCH not in decision.matched_candidates


def test_priority_selects_cash_cow_over_growth_and_test_buy() -> None:
    context = StrategyContext(
        scores=_scores(
            demand=85,
            competition=80,
            price_stability=85,
            confidence=90,
            opportunity=85,
        ),
        history_months=8,
        economics=_economics(profitability=80, cash_efficiency=85),
    )

    decision = StrategyClassifier().classify(context)

    assert decision.strategy is Strategy.CASH_COW
    assert decision.matched_candidates == (
        Strategy.CASH_COW,
        Strategy.GROWTH,
        Strategy.TEST_BUY,
    )


def test_protective_clearance_rule_wins_an_economic_strategy_conflict() -> None:
    context = StrategyContext(
        scores=_scores(
            demand=85,
            competition=80,
            price_stability=85,
            confidence=90,
            opportunity=85,
        ),
        history_months=8,
        economics=_economics(profitability=80, cash_efficiency=85),
        inventory=InventorySignals(
            inventory_risk_score=90,
            units_on_hand=400,
            stock_cover_days=Decimal("200"),
        ),
    )

    decision = StrategyClassifier().classify(context)

    assert decision.strategy is Strategy.CLEARANCE_WATCH
    assert decision.matched_candidates[:4] == (
        Strategy.CLEARANCE_WATCH,
        Strategy.CASH_COW,
        Strategy.GROWTH,
        Strategy.TEST_BUY,
    )


def test_growth_reason_codes_and_evidence_are_stable() -> None:
    context = StrategyContext(
        scores=_scores(
            demand=85,
            competition=70,
            price_stability=60,
            confidence=90,
            opportunity=85,
        ),
        history_months=3,
        economics=_economics(profitability=70, cash_efficiency=65),
    )

    decision = StrategyClassifier().classify(context)

    assert decision.reason_codes == (
        ReasonCode.DEMAND_STRONG,
        ReasonCode.OPPORTUNITY_STRONG,
        ReasonCode.PROFITABILITY_HEALTHY,
        ReasonCode.CASH_EFFICIENCY_HEALTHY,
    )
    first = decision.evidence[0]
    assert first.signal == "demand"
    assert first.observed_value == 85
    assert first.comparison is EvidenceComparison.GREATER_THAN_OR_EQUAL
    assert first.threshold_value == 75


def test_classification_is_deterministic_and_side_effect_free() -> None:
    classifier = StrategyClassifier()
    context = STRATEGY_CASES[2][0]

    decisions = tuple(classifier.classify(context) for _ in range(20))

    assert all(decision == decisions[0] for decision in decisions)
    assert context == STRATEGY_CASES[2][0]


def test_market_scores_adapt_protocol_compatible_mapping() -> None:
    scores = MarketScores.from_mapping(
        {
            "demand": 61,
            "competition": 62,
            "price_stability": 63,
            "data_confidence": 64,
            "overall_opportunity": 65,
            "future_score": 99,
        }
    )

    assert scores == MarketScores(61, 62, 63, 64, 65)


def test_context_rejects_invalid_score_and_inventory_values() -> None:
    with pytest.raises(ValueError, match="demand must be between"):
        MarketScores(101, 50, 50, 50, 50)
    with pytest.raises(ValueError, match="units_on_hand cannot be negative"):
        InventorySignals(50, -1, Decimal("30"))
    with pytest.raises(ValueError, match="history_months must be at least 1"):
        StrategyContext(MarketScores(50, 50, 50, 50, 50), history_months=0)


def _default_policy_payload() -> dict[str, object]:
    raw: object = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return cast(dict[str, object], raw)


def _nested_policy_object(payload: dict[str, object], *keys: str) -> dict[str, object]:
    current = payload
    for key in keys:
        candidate = current[key]
        assert isinstance(candidate, dict)
        current = cast(dict[str, object], candidate)
    return current


@pytest.mark.parametrize(
    "mutate",
    (
        lambda payload: payload.update({"unexpected_setting": True}),
        lambda payload: payload.update({"rules_version": "unversioned"}),
        lambda payload: payload.update({"priority": ["avoid"] * 8}),
        lambda payload: _nested_policy_object(payload, "thresholds", "growth").update(
            {"demand_min": 101}
        ),
        lambda payload: _nested_policy_object(payload, "thresholds", "premium_margin").update(
            {"contribution_margin_percent_min": 30}
        ),
        lambda payload: _nested_policy_object(payload, "thresholds", "premium_margin").update(
            {"demand_min": 80, "demand_max": 60}
        ),
    ),
    ids=(
        "unknown-key",
        "invalid-version",
        "duplicate-priority",
        "score-out-of-range",
        "imprecise-decimal",
        "invalid-min-max",
    ),
)
def test_policy_validation_rejects_unsafe_configuration(
    mutate: Callable[[dict[str, object]], object],
) -> None:
    payload = _default_policy_payload()
    mutate(payload)

    with pytest.raises(PolicyValidationError):
        parse_strategy_policy(payload)


def test_bundled_json_policy_is_machine_readable_and_validated() -> None:
    policy = load_strategy_policy(DEFAULT_POLICY_PATH)

    assert policy.schema_version == 1
    assert policy.rules_version == "strategy-v1.0.0"
    assert policy.priority == (
        Strategy.CLEARANCE_WATCH,
        Strategy.AVOID,
        Strategy.CASH_COW,
        Strategy.GROWTH,
        Strategy.PREMIUM_MARGIN,
        Strategy.TEST_BUY,
        Strategy.DISCOVERY,
        Strategy.MONITOR,
    )
