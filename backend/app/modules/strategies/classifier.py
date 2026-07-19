"""Pure deterministic strategy classification for SellerOS Phase 1."""

from __future__ import annotations

from collections.abc import Callable

from app.modules.strategies.models import (
    EvidenceComparison,
    EvidencePolarity,
    EvidenceSource,
    EvidenceValue,
    ReasonCode,
    Strategy,
    StrategyContext,
    StrategyDecision,
    StrategyEvidence,
)
from app.modules.strategies.policy import StrategyPolicy, load_default_strategy_policy

RuleEvidence = tuple[StrategyEvidence, ...]
RuleEvaluator = Callable[[StrategyContext, StrategyPolicy], RuleEvidence | None]


def _evidence(
    *,
    reason_code: ReasonCode,
    polarity: EvidencePolarity,
    source: EvidenceSource,
    signal: str,
    observed_value: EvidenceValue,
    comparison: EvidenceComparison,
    threshold_value: EvidenceValue = None,
    threshold_upper_value: EvidenceValue = None,
    statement: str,
) -> StrategyEvidence:
    return StrategyEvidence(
        reason_code=reason_code,
        polarity=polarity,
        source=source,
        signal=signal,
        observed_value=observed_value,
        comparison=comparison,
        threshold_value=threshold_value,
        threshold_upper_value=threshold_upper_value,
        statement=statement,
    )


def _confidence_sufficient(context: StrategyContext, policy: StrategyPolicy) -> StrategyEvidence:
    return _evidence(
        reason_code=ReasonCode.DATA_CONFIDENCE_SUFFICIENT,
        polarity=EvidencePolarity.POSITIVE,
        source=EvidenceSource.MARKET_SCORE,
        signal="data_confidence",
        observed_value=context.scores.data_confidence,
        comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
        threshold_value=policy.low_confidence_threshold,
        statement="Data confidence meets the minimum classification threshold.",
    )


def _low_confidence_decision(
    context: StrategyContext, policy: StrategyPolicy
) -> StrategyDecision | None:
    if context.scores.data_confidence >= policy.low_confidence_threshold:
        return None
    return StrategyDecision(
        strategy=Strategy.DISCOVERY,
        rules_version=policy.rules_version,
        evidence=(
            _evidence(
                reason_code=ReasonCode.LOW_DATA_CONFIDENCE,
                polarity=EvidencePolarity.NEGATIVE,
                source=EvidenceSource.MARKET_SCORE,
                signal="data_confidence",
                observed_value=context.scores.data_confidence,
                comparison=EvidenceComparison.LESS_THAN,
                threshold_value=policy.low_confidence_threshold,
                statement="Data confidence is below the policy threshold.",
            ),
            _evidence(
                reason_code=ReasonCode.AGGRESSIVE_RECOMMENDATION_BLOCKED,
                polarity=EvidencePolarity.INFORMATIONAL,
                source=EvidenceSource.POLICY,
                signal="confidence_gate",
                observed_value=True,
                comparison=EvidenceComparison.FALLBACK,
                statement="The confidence gate blocks buy, growth, and margin recommendations.",
            ),
        ),
        matched_candidates=(Strategy.DISCOVERY,),
    )


def _clearance_watch(context: StrategyContext, policy: StrategyPolicy) -> RuleEvidence | None:
    inventory = context.inventory
    thresholds = policy.thresholds.clearance_watch
    if inventory is None or inventory.units_on_hand < thresholds.units_on_hand_min:
        return None

    risk_is_high = inventory.inventory_risk_score >= thresholds.inventory_risk_min
    cover_is_excessive = inventory.stock_cover_days >= thresholds.stock_cover_days_min
    if sum((risk_is_high, cover_is_excessive)) < thresholds.risk_triggers_required:
        return None

    evidence: list[StrategyEvidence] = [
        _evidence(
            reason_code=ReasonCode.INVENTORY_AVAILABLE,
            polarity=EvidencePolarity.INFORMATIONAL,
            source=EvidenceSource.INVENTORY,
            signal="units_on_hand",
            observed_value=inventory.units_on_hand,
            comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
            threshold_value=thresholds.units_on_hand_min,
            statement="Sellable inventory exists and is exposed to the identified stock risk.",
        )
    ]
    if risk_is_high:
        evidence.append(
            _evidence(
                reason_code=ReasonCode.INVENTORY_RISK_HIGH,
                polarity=EvidencePolarity.NEGATIVE,
                source=EvidenceSource.INVENTORY,
                signal="inventory_risk_score",
                observed_value=inventory.inventory_risk_score,
                comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
                threshold_value=thresholds.inventory_risk_min,
                statement="Inventory risk meets the clearance-watch threshold.",
            )
        )
    if cover_is_excessive:
        evidence.append(
            _evidence(
                reason_code=ReasonCode.STOCK_COVER_EXCESSIVE,
                polarity=EvidencePolarity.NEGATIVE,
                source=EvidenceSource.INVENTORY,
                signal="stock_cover_days",
                observed_value=inventory.stock_cover_days,
                comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
                threshold_value=thresholds.stock_cover_days_min,
                statement="Stock cover meets the excessive-inventory threshold.",
            )
        )
    return tuple(evidence)


def _avoid(context: StrategyContext, policy: StrategyPolicy) -> RuleEvidence | None:
    scores = context.scores
    thresholds = policy.thresholds.avoid
    evidence: list[StrategyEvidence] = []
    if scores.overall_opportunity <= thresholds.opportunity_max:
        evidence.append(
            _evidence(
                reason_code=ReasonCode.OPPORTUNITY_UNACCEPTABLE,
                polarity=EvidencePolarity.NEGATIVE,
                source=EvidenceSource.MARKET_SCORE,
                signal="overall_opportunity",
                observed_value=scores.overall_opportunity,
                comparison=EvidenceComparison.LESS_THAN_OR_EQUAL,
                threshold_value=thresholds.opportunity_max,
                statement="Overall opportunity is at or below the avoidance threshold.",
            )
        )
    if scores.demand <= thresholds.demand_max:
        evidence.append(
            _evidence(
                reason_code=ReasonCode.DEMAND_UNACCEPTABLE,
                polarity=EvidencePolarity.NEGATIVE,
                source=EvidenceSource.MARKET_SCORE,
                signal="demand",
                observed_value=scores.demand,
                comparison=EvidenceComparison.LESS_THAN_OR_EQUAL,
                threshold_value=thresholds.demand_max,
                statement="Demand is at or below the avoidance threshold.",
            )
        )
    if (
        scores.competition <= thresholds.competition_max
        and scores.price_stability <= thresholds.price_stability_max
    ):
        evidence.extend(
            (
                _evidence(
                    reason_code=ReasonCode.MARKET_RISK_COMBINATION,
                    polarity=EvidencePolarity.NEGATIVE,
                    source=EvidenceSource.MARKET_SCORE,
                    signal="competition",
                    observed_value=scores.competition,
                    comparison=EvidenceComparison.LESS_THAN_OR_EQUAL,
                    threshold_value=thresholds.competition_max,
                    statement="Competition quality is weak within a combined market-risk signal.",
                ),
                _evidence(
                    reason_code=ReasonCode.MARKET_RISK_COMBINATION,
                    polarity=EvidencePolarity.NEGATIVE,
                    source=EvidenceSource.MARKET_SCORE,
                    signal="price_stability",
                    observed_value=scores.price_stability,
                    comparison=EvidenceComparison.LESS_THAN_OR_EQUAL,
                    threshold_value=thresholds.price_stability_max,
                    statement="Price stability is weak within a combined market-risk signal.",
                ),
            )
        )

    economics = context.economics
    if economics is not None:
        if economics.profitability_score <= thresholds.profitability_max:
            evidence.append(
                _evidence(
                    reason_code=ReasonCode.ECONOMICS_UNACCEPTABLE,
                    polarity=EvidencePolarity.NEGATIVE,
                    source=EvidenceSource.ECONOMICS,
                    signal="profitability_score",
                    observed_value=economics.profitability_score,
                    comparison=EvidenceComparison.LESS_THAN_OR_EQUAL,
                    threshold_value=thresholds.profitability_max,
                    statement="Profitability is at or below the avoidance threshold.",
                )
            )
        if economics.contribution_margin_percent <= thresholds.contribution_margin_percent_max:
            evidence.append(
                _evidence(
                    reason_code=ReasonCode.NEGATIVE_CONTRIBUTION_MARGIN,
                    polarity=EvidencePolarity.NEGATIVE,
                    source=EvidenceSource.ECONOMICS,
                    signal="contribution_margin_percent",
                    observed_value=economics.contribution_margin_percent,
                    comparison=EvidenceComparison.LESS_THAN_OR_EQUAL,
                    threshold_value=thresholds.contribution_margin_percent_max,
                    statement="Contribution margin is non-positive.",
                )
            )

    if not evidence:
        return None
    if len(evidence) == 1:
        evidence.append(_confidence_sufficient(context, policy))
    return tuple(evidence)


def _cash_cow(context: StrategyContext, policy: StrategyPolicy) -> RuleEvidence | None:
    economics = context.economics
    thresholds = policy.thresholds.cash_cow
    scores = context.scores
    if economics is None or not (
        scores.demand >= thresholds.demand_min
        and scores.overall_opportunity >= thresholds.opportunity_min
        and scores.price_stability >= thresholds.price_stability_min
        and economics.profitability_score >= thresholds.profitability_min
        and economics.cash_efficiency_score >= thresholds.cash_efficiency_min
        and context.history_months >= thresholds.history_months_min
    ):
        return None
    return (
        _evidence(
            reason_code=ReasonCode.HISTORY_ESTABLISHED,
            polarity=EvidencePolarity.POSITIVE,
            source=EvidenceSource.HISTORY,
            signal="history_months",
            observed_value=context.history_months,
            comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
            threshold_value=thresholds.history_months_min,
            statement="The product has enough history for a repeatable-demand recommendation.",
        ),
        _evidence(
            reason_code=ReasonCode.DEMAND_STABLE,
            polarity=EvidencePolarity.POSITIVE,
            source=EvidenceSource.MARKET_SCORE,
            signal="demand",
            observed_value=scores.demand,
            comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
            threshold_value=thresholds.demand_min,
            statement="Demand meets the established-product threshold.",
        ),
        _evidence(
            reason_code=ReasonCode.PRICE_STABILITY_STRONG,
            polarity=EvidencePolarity.POSITIVE,
            source=EvidenceSource.MARKET_SCORE,
            signal="price_stability",
            observed_value=scores.price_stability,
            comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
            threshold_value=thresholds.price_stability_min,
            statement="Price stability supports predictable contribution.",
        ),
        _evidence(
            reason_code=ReasonCode.PROFITABILITY_HEALTHY,
            polarity=EvidencePolarity.POSITIVE,
            source=EvidenceSource.ECONOMICS,
            signal="profitability_score",
            observed_value=economics.profitability_score,
            comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
            threshold_value=thresholds.profitability_min,
            statement="Profitability meets the cash-cow threshold.",
        ),
        _evidence(
            reason_code=ReasonCode.CASH_EFFICIENCY_HEALTHY,
            polarity=EvidencePolarity.POSITIVE,
            source=EvidenceSource.ECONOMICS,
            signal="cash_efficiency_score",
            observed_value=economics.cash_efficiency_score,
            comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
            threshold_value=thresholds.cash_efficiency_min,
            statement="Cash efficiency meets the predictable-return threshold.",
        ),
    )


def _growth(context: StrategyContext, policy: StrategyPolicy) -> RuleEvidence | None:
    economics = context.economics
    thresholds = policy.thresholds.growth
    scores = context.scores
    if economics is None or not (
        scores.demand >= thresholds.demand_min
        and scores.overall_opportunity >= thresholds.opportunity_min
        and scores.competition >= thresholds.competition_min
        and scores.price_stability >= thresholds.price_stability_min
        and economics.profitability_score >= thresholds.profitability_min
        and economics.cash_efficiency_score >= thresholds.cash_efficiency_min
    ):
        return None
    return (
        _evidence(
            reason_code=ReasonCode.DEMAND_STRONG,
            polarity=EvidencePolarity.POSITIVE,
            source=EvidenceSource.MARKET_SCORE,
            signal="demand",
            observed_value=scores.demand,
            comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
            threshold_value=thresholds.demand_min,
            statement="Demand meets the growth threshold.",
        ),
        _evidence(
            reason_code=ReasonCode.OPPORTUNITY_STRONG,
            polarity=EvidencePolarity.POSITIVE,
            source=EvidenceSource.MARKET_SCORE,
            signal="overall_opportunity",
            observed_value=scores.overall_opportunity,
            comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
            threshold_value=thresholds.opportunity_min,
            statement="Overall opportunity meets the growth threshold.",
        ),
        _evidence(
            reason_code=ReasonCode.PROFITABILITY_HEALTHY,
            polarity=EvidencePolarity.POSITIVE,
            source=EvidenceSource.ECONOMICS,
            signal="profitability_score",
            observed_value=economics.profitability_score,
            comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
            threshold_value=thresholds.profitability_min,
            statement="Profitability supports additional investment.",
        ),
        _evidence(
            reason_code=ReasonCode.CASH_EFFICIENCY_HEALTHY,
            polarity=EvidencePolarity.POSITIVE,
            source=EvidenceSource.ECONOMICS,
            signal="cash_efficiency_score",
            observed_value=economics.cash_efficiency_score,
            comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
            threshold_value=thresholds.cash_efficiency_min,
            statement="Cash efficiency supports additional investment.",
        ),
    )


def _premium_margin(context: StrategyContext, policy: StrategyPolicy) -> RuleEvidence | None:
    economics = context.economics
    thresholds = policy.thresholds.premium_margin
    scores = context.scores
    if economics is None or not (
        thresholds.demand_min <= scores.demand <= thresholds.demand_max
        and scores.overall_opportunity >= thresholds.opportunity_min
        and scores.price_stability >= thresholds.price_stability_min
        and economics.profitability_score >= thresholds.profitability_min
        and economics.contribution_margin_percent >= thresholds.contribution_margin_percent_min
    ):
        return None
    return (
        _evidence(
            reason_code=ReasonCode.DEMAND_SELECTIVE,
            polarity=EvidencePolarity.INFORMATIONAL,
            source=EvidenceSource.MARKET_SCORE,
            signal="demand",
            observed_value=scores.demand,
            comparison=EvidenceComparison.BETWEEN_INCLUSIVE,
            threshold_value=thresholds.demand_min,
            threshold_upper_value=thresholds.demand_max,
            statement="Demand is within the selective-velocity range for a premium-margin item.",
        ),
        _evidence(
            reason_code=ReasonCode.PROFITABILITY_HEALTHY,
            polarity=EvidencePolarity.POSITIVE,
            source=EvidenceSource.ECONOMICS,
            signal="profitability_score",
            observed_value=economics.profitability_score,
            comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
            threshold_value=thresholds.profitability_min,
            statement="Profitability meets the premium-margin threshold.",
        ),
        _evidence(
            reason_code=ReasonCode.CONTRIBUTION_MARGIN_PREMIUM,
            polarity=EvidencePolarity.POSITIVE,
            source=EvidenceSource.ECONOMICS,
            signal="contribution_margin_percent",
            observed_value=economics.contribution_margin_percent,
            comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
            threshold_value=thresholds.contribution_margin_percent_min,
            statement="Contribution margin meets the premium threshold.",
        ),
    )


def _test_buy(context: StrategyContext, policy: StrategyPolicy) -> RuleEvidence | None:
    thresholds = policy.thresholds.test_buy
    scores = context.scores
    if not (
        scores.demand >= thresholds.demand_min
        and scores.overall_opportunity >= thresholds.opportunity_min
        and scores.competition >= thresholds.competition_min
        and scores.price_stability >= thresholds.price_stability_min
    ):
        return None
    return (
        _evidence(
            reason_code=ReasonCode.DEMAND_PROMISING,
            polarity=EvidencePolarity.POSITIVE,
            source=EvidenceSource.MARKET_SCORE,
            signal="demand",
            observed_value=scores.demand,
            comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
            threshold_value=thresholds.demand_min,
            statement="Demand is strong enough for a controlled test order.",
        ),
        _evidence(
            reason_code=ReasonCode.OPPORTUNITY_STRONG,
            polarity=EvidencePolarity.POSITIVE,
            source=EvidenceSource.MARKET_SCORE,
            signal="overall_opportunity",
            observed_value=scores.overall_opportunity,
            comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
            threshold_value=thresholds.opportunity_min,
            statement="Overall opportunity is strong enough for controlled validation.",
        ),
        _evidence(
            reason_code=ReasonCode.COMPETITION_ACCEPTABLE,
            polarity=EvidencePolarity.POSITIVE,
            source=EvidenceSource.MARKET_SCORE,
            signal="competition",
            observed_value=scores.competition,
            comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
            threshold_value=thresholds.competition_min,
            statement="Competition quality meets the test-buy threshold.",
        ),
        _evidence(
            reason_code=ReasonCode.PRICE_STABILITY_ACCEPTABLE,
            polarity=EvidencePolarity.POSITIVE,
            source=EvidenceSource.MARKET_SCORE,
            signal="price_stability",
            observed_value=scores.price_stability,
            comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
            threshold_value=thresholds.price_stability_min,
            statement="Price stability meets the test-buy threshold.",
        ),
    )


def _discovery(context: StrategyContext, policy: StrategyPolicy) -> RuleEvidence | None:
    thresholds = policy.thresholds.discovery
    if context.scores.overall_opportunity < thresholds.opportunity_min:
        return None
    limited_history = context.history_months < thresholds.minimum_history_months
    missing_economics = context.economics is None
    if not limited_history and not missing_economics:
        return None

    evidence: list[StrategyEvidence] = [
        _evidence(
            reason_code=ReasonCode.OPPORTUNITY_WORTH_INVESTIGATING,
            polarity=EvidencePolarity.POSITIVE,
            source=EvidenceSource.MARKET_SCORE,
            signal="overall_opportunity",
            observed_value=context.scores.overall_opportunity,
            comparison=EvidenceComparison.GREATER_THAN_OR_EQUAL,
            threshold_value=thresholds.opportunity_min,
            statement="The opportunity score warrants further investigation.",
        )
    ]
    if limited_history:
        evidence.append(
            _evidence(
                reason_code=ReasonCode.LIMITED_HISTORY,
                polarity=EvidencePolarity.INFORMATIONAL,
                source=EvidenceSource.HISTORY,
                signal="history_months",
                observed_value=context.history_months,
                comparison=EvidenceComparison.LESS_THAN,
                threshold_value=thresholds.minimum_history_months,
                statement="More monthly history is required before a stronger recommendation.",
            )
        )
    if missing_economics:
        evidence.append(
            _evidence(
                reason_code=ReasonCode.ECONOMICS_NOT_AVAILABLE,
                polarity=EvidencePolarity.INFORMATIONAL,
                source=EvidenceSource.ECONOMICS,
                signal="economics",
                observed_value=None,
                comparison=EvidenceComparison.MISSING,
                statement="Seller-specific economics are not available.",
            )
        )
    return tuple(evidence)


def _monitor(context: StrategyContext, policy: StrategyPolicy) -> RuleEvidence:
    return (
        _evidence(
            reason_code=ReasonCode.NO_STRATEGY_RULE_MATCHED,
            polarity=EvidencePolarity.INFORMATIONAL,
            source=EvidenceSource.POLICY,
            signal="strategy_rule",
            observed_value=policy.rules_version,
            comparison=EvidenceComparison.FALLBACK,
            statement="No action-oriented strategy rule matched the available evidence.",
        ),
        _confidence_sufficient(context, policy),
    )


RULE_EVALUATORS: dict[Strategy, RuleEvaluator] = {
    Strategy.CLEARANCE_WATCH: _clearance_watch,
    Strategy.AVOID: _avoid,
    Strategy.CASH_COW: _cash_cow,
    Strategy.GROWTH: _growth,
    Strategy.PREMIUM_MARGIN: _premium_margin,
    Strategy.TEST_BUY: _test_buy,
    Strategy.DISCOVERY: _discovery,
}


class StrategyClassifier:
    """Apply an immutable policy to typed inputs without I/O or mutable state."""

    def __init__(self, policy: StrategyPolicy | None = None) -> None:
        self._policy = policy or load_default_strategy_policy()

    @property
    def policy(self) -> StrategyPolicy:
        return self._policy

    def classify(self, context: StrategyContext) -> StrategyDecision:
        """Classify one context with explicit gating and priority conflict resolution."""

        gated = _low_confidence_decision(context, self._policy)
        if gated is not None:
            return gated

        matches: dict[Strategy, RuleEvidence] = {}
        for strategy, evaluator in RULE_EVALUATORS.items():
            evidence = evaluator(context, self._policy)
            if evidence is not None:
                matches[strategy] = evidence

        ordered_candidates = tuple(
            strategy
            for strategy in self._policy.priority
            if strategy is not self._policy.default_strategy and strategy in matches
        )
        if not ordered_candidates:
            return StrategyDecision(
                strategy=self._policy.default_strategy,
                rules_version=self._policy.rules_version,
                evidence=_monitor(context, self._policy),
                matched_candidates=(self._policy.default_strategy,),
            )

        selected = ordered_candidates[0]
        return StrategyDecision(
            strategy=selected,
            rules_version=self._policy.rules_version,
            evidence=matches[selected],
            matched_candidates=ordered_candidates,
        )
