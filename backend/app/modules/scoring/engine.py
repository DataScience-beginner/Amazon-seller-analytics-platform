from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from app.modules.scoring.config import (
    COMPONENT_NAMES,
    METRIC_NAMES,
    ComponentRule,
    ScoringConfig,
    load_default_scoring_config,
)
from app.modules.scoring.types import (
    InputState,
    MarketMetrics,
    MetricInput,
    NumericInput,
    ScoreCard,
    ScoreComponent,
    ScoreName,
    ScoreReason,
    ScoreReasonCode,
    ScoreResult,
)

_ZERO = Decimal("0")
_ONE_HUNDRED = Decimal("100")
_WEIGHT_QUANTUM = Decimal("0.0001")
_MISSING_TEXT = frozenset({"", "-", "--", "n/a", "na", "none", "null"})
_CURRENCY_SYMBOLS = frozenset({"$", "£", "€", "₹", "¥"})

_SCORE_INPUT_NAMES: Mapping[ScoreName, tuple[str, ...]] = {
    ScoreName.demand: (
        "sales_rank_current",
        "sales_rank_90_day_average",
        "rank_drops_90_days",
        "monthly_sold",
    ),
    ScoreName.competition: (
        "offer_count",
        "review_count",
        "buy_box_winner_count_90_days",
    ),
    ScoreName.price_stability: (
        "buy_box_price",
        "buy_box_price_90_day_average",
        "buy_box_oos_percent",
    ),
}


def _raw_metric_items(metrics: MarketMetrics) -> tuple[tuple[str, NumericInput], ...]:
    return (
        ("sales_rank_current", metrics.sales_rank_current),
        ("sales_rank_90_day_average", metrics.sales_rank_90_day_average),
        ("rank_drops_90_days", metrics.rank_drops_90_days),
        ("monthly_sold", metrics.monthly_sold),
        ("offer_count", metrics.offer_count),
        ("review_count", metrics.review_count),
        ("buy_box_winner_count_90_days", metrics.buy_box_winner_count_90_days),
        ("buy_box_price", metrics.buy_box_price),
        ("buy_box_price_90_day_average", metrics.buy_box_price_90_day_average),
        ("buy_box_oos_percent", metrics.buy_box_oos_percent),
    )


def _raw_value_text(value: NumericInput) -> str | None:
    if value is None:
        return None
    return str(value)


def _parse_decimal(value: NumericInput) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        parsed = value
    elif isinstance(value, int | float):
        try:
            parsed = Decimal(str(value))
        except InvalidOperation:
            return None
    else:
        text = value.strip()
        if text.casefold() in _MISSING_TEXT:
            return None
        if text and text[0] in _CURRENCY_SYMBOLS:
            text = text[1:].strip()
        if text.endswith("%"):
            text = text[:-1].strip()
        text = text.replace(",", "")
        try:
            parsed = Decimal(text)
        except InvalidOperation:
            return None
    return parsed if parsed.is_finite() else None


def _parse_inputs(metrics: MarketMetrics, config: ScoringConfig) -> tuple[MetricInput, ...]:
    parsed_inputs: list[MetricInput] = []
    for name, raw_value in _raw_metric_items(metrics):
        raw_text = _raw_value_text(raw_value)
        if raw_value is None or (
            isinstance(raw_value, str) and raw_value.strip().casefold() in _MISSING_TEXT
        ):
            parsed_inputs.append(
                MetricInput(
                    name=name,
                    raw_value=raw_text,
                    parsed_value=None,
                    state=InputState.missing,
                )
            )
            continue

        parsed_value = _parse_decimal(raw_value)
        if parsed_value is None:
            parsed_inputs.append(
                MetricInput(
                    name=name,
                    raw_value=raw_text,
                    parsed_value=None,
                    state=InputState.invalid,
                )
            )
            continue

        bounds = config.metric_bounds[name]
        state = (
            InputState.valid
            if bounds.minimum <= parsed_value <= bounds.maximum
            else InputState.outlier
        )
        parsed_inputs.append(
            MetricInput(
                name=name,
                raw_value=raw_text,
                parsed_value=parsed_value,
                state=state,
            )
        )
    return tuple(parsed_inputs)


def _round_score(value: Decimal) -> int:
    bounded = min(_ONE_HUNDRED, max(_ZERO, value))
    return int(bounded.to_integral_value(rounding=ROUND_HALF_UP))


def _linear_component_score(value: Decimal, rule: ComponentRule) -> Decimal:
    fraction = (value - rule.zero_score_at) / (rule.full_score_at - rule.zero_score_at)
    return min(_ONE_HUNDRED, max(_ZERO, fraction * _ONE_HUNDRED))


def _input_reason(item: MetricInput) -> ScoreReason | None:
    codes = {
        InputState.missing: ScoreReasonCode.input_missing,
        InputState.invalid: ScoreReasonCode.input_invalid,
        InputState.outlier: ScoreReasonCode.input_outlier,
    }
    code = codes.get(item.state)
    return ScoreReason(code=code, metric=item.name) if code is not None else None


def _band_reason(score_value: int, config: ScoringConfig) -> ScoreReason:
    if score_value < config.score_bands.weak_below:
        code = ScoreReasonCode.score_weak
    elif score_value >= config.score_bands.strong_at_or_above:
        code = ScoreReasonCode.score_strong
    else:
        code = ScoreReasonCode.score_moderate
    return ScoreReason(code=code)


def _confidence_band_reason(score_value: int, config: ScoringConfig) -> ScoreReason:
    if score_value < config.score_bands.weak_below:
        code = ScoreReasonCode.confidence_low
    elif score_value >= config.score_bands.strong_at_or_above:
        code = ScoreReasonCode.confidence_high
    else:
        code = ScoreReasonCode.confidence_medium
    return ScoreReason(code=code)


def _valid_value(inputs_by_name: Mapping[str, MetricInput], name: str) -> Decimal | None:
    item = inputs_by_name[name]
    return item.parsed_value if item.state is InputState.valid else None


def _component_values(
    score_name: ScoreName,
    inputs_by_name: Mapping[str, MetricInput],
) -> dict[str, Decimal | None]:
    if score_name is ScoreName.demand:
        current_rank = _valid_value(inputs_by_name, "sales_rank_current")
        average_rank = _valid_value(inputs_by_name, "sales_rank_90_day_average")
        rank_trend_ratio = (
            current_rank / average_rank
            if current_rank is not None and average_rank is not None and average_rank != 0
            else None
        )
        return {
            "sales_rank_current": current_rank,
            "rank_drops_90_days": _valid_value(inputs_by_name, "rank_drops_90_days"),
            "monthly_sold": _valid_value(inputs_by_name, "monthly_sold"),
            "rank_trend_ratio": rank_trend_ratio,
        }

    if score_name is ScoreName.competition:
        return {
            "offer_count": _valid_value(inputs_by_name, "offer_count"),
            "review_count": _valid_value(inputs_by_name, "review_count"),
            "buy_box_winner_count_90_days": _valid_value(
                inputs_by_name, "buy_box_winner_count_90_days"
            ),
        }

    current_price = _valid_value(inputs_by_name, "buy_box_price")
    average_price = _valid_value(inputs_by_name, "buy_box_price_90_day_average")
    price_deviation_ratio = (
        abs((current_price / average_price) - Decimal("1"))
        if current_price is not None and average_price is not None and average_price != 0
        else None
    )
    return {
        "price_deviation_ratio": price_deviation_ratio,
        "buy_box_oos_percent": _valid_value(inputs_by_name, "buy_box_oos_percent"),
    }


def _selected_inputs(
    inputs_by_name: Mapping[str, MetricInput], names: Iterable[str]
) -> tuple[MetricInput, ...]:
    return tuple(inputs_by_name[name] for name in names)


def _market_score(
    score_name: ScoreName,
    inputs_by_name: Mapping[str, MetricInput],
    config: ScoringConfig,
) -> ScoreResult:
    selected_inputs = _selected_inputs(inputs_by_name, _SCORE_INPUT_NAMES[score_name])
    reasons = [reason for item in selected_inputs if (reason := _input_reason(item)) is not None]
    values = _component_values(score_name, inputs_by_name)
    rules = config.component_scores[score_name]
    available_weight = sum(
        (rules[name].weight for name, value in values.items() if value is not None),
        _ZERO,
    )

    weighted_total = _ZERO
    components: list[ScoreComponent] = []
    for component_name in COMPONENT_NAMES[score_name]:
        component_value = values[component_name]
        rule = rules[component_name]
        if component_value is None:
            components.append(
                ScoreComponent(
                    name=component_name,
                    value=None,
                    configured_weight=rule.weight,
                    effective_weight=_ZERO,
                )
            )
            reasons.append(
                ScoreReason(
                    code=ScoreReasonCode.component_unavailable,
                    metric=component_name,
                )
            )
            continue

        raw_component_score = _linear_component_score(component_value, rule)
        effective_weight = rule.weight / available_weight if available_weight > 0 else _ZERO
        weighted_total += raw_component_score * rule.weight
        components.append(
            ScoreComponent(
                name=component_name,
                value=_round_score(raw_component_score),
                configured_weight=rule.weight,
                effective_weight=effective_weight.quantize(_WEIGHT_QUANTUM, rounding=ROUND_HALF_UP),
            )
        )

    if available_weight == 0:
        score_value = 0
        reasons.append(ScoreReason(code=ScoreReasonCode.no_usable_inputs))
    else:
        score_value = _round_score(weighted_total / available_weight)
        if available_weight != Decimal("1"):
            reasons.append(ScoreReason(code=ScoreReasonCode.available_components_reweighted))
    reasons.append(_band_reason(score_value, config))

    return ScoreResult(
        name=score_name,
        value=score_value,
        formula_version=config.formula_version,
        inputs=selected_inputs,
        components=tuple(components),
        reasons=tuple(reasons),
    )


def _data_confidence_score(
    parsed_inputs: tuple[MetricInput, ...], config: ScoringConfig
) -> ScoreResult:
    weighted_validity = sum(
        (
            config.data_confidence_weights[item.name]
            for item in parsed_inputs
            if item.state is InputState.valid
        ),
        _ZERO,
    )
    score_value = _round_score(weighted_validity * _ONE_HUNDRED)
    reasons = [reason for item in parsed_inputs if (reason := _input_reason(item)) is not None]
    reasons.append(_confidence_band_reason(score_value, config))
    components = tuple(
        ScoreComponent(
            name=item.name,
            value=100 if item.state is InputState.valid else 0,
            configured_weight=config.data_confidence_weights[item.name],
            effective_weight=config.data_confidence_weights[item.name],
        )
        for item in parsed_inputs
    )
    return ScoreResult(
        name=ScoreName.data_confidence,
        value=score_value,
        formula_version=config.formula_version,
        inputs=parsed_inputs,
        components=components,
        reasons=tuple(reasons),
    )


def _derived_input(name: str, value: int) -> MetricInput:
    parsed = Decimal(value)
    return MetricInput(
        name=name,
        raw_value=str(value),
        parsed_value=parsed,
        state=InputState.valid,
    )


def _overall_score(
    demand: ScoreResult,
    competition: ScoreResult,
    price_stability: ScoreResult,
    data_confidence: ScoreResult,
    config: ScoringConfig,
) -> ScoreResult:
    market_scores = {
        ScoreName.demand: demand,
        ScoreName.competition: competition,
        ScoreName.price_stability: price_stability,
    }
    base_score = sum(
        (
            Decimal(result.value) * config.overall_weights[score_name]
            for score_name, result in market_scores.items()
        ),
        _ZERO,
    )
    confidence_factor = Decimal(data_confidence.value) / _ONE_HUNDRED
    adjusted_score = base_score * confidence_factor
    score_value = _round_score(adjusted_score)

    inputs = tuple(
        _derived_input(f"{score_name.value}_score", market_scores[score_name].value)
        for score_name in (
            ScoreName.demand,
            ScoreName.competition,
            ScoreName.price_stability,
        )
    ) + (_derived_input("data_confidence_score", data_confidence.value),)
    components = tuple(
        ScoreComponent(
            name=score_name.value,
            value=market_scores[score_name].value,
            configured_weight=config.overall_weights[score_name],
            effective_weight=config.overall_weights[score_name],
        )
        for score_name in (
            ScoreName.demand,
            ScoreName.competition,
            ScoreName.price_stability,
        )
    )
    reasons = (
        ScoreReason(code=ScoreReasonCode.overall_confidence_adjusted),
        _band_reason(score_value, config),
    )
    return ScoreResult(
        name=ScoreName.overall_opportunity,
        value=score_value,
        formula_version=config.formula_version,
        inputs=inputs,
        components=components,
        reasons=reasons,
    )


def score_market_metrics(
    metrics: MarketMetrics,
    config: ScoringConfig | None = None,
) -> ScoreCard:
    """Calculate the complete deterministic Phase 1 market score card."""

    active_config = config or load_default_scoring_config()
    parsed_inputs = _parse_inputs(metrics, active_config)
    if tuple(item.name for item in parsed_inputs) != METRIC_NAMES:
        raise RuntimeError("Market metric order does not match the scoring contract")
    inputs_by_name = {item.name: item for item in parsed_inputs}

    demand = _market_score(ScoreName.demand, inputs_by_name, active_config)
    competition = _market_score(ScoreName.competition, inputs_by_name, active_config)
    price_stability = _market_score(ScoreName.price_stability, inputs_by_name, active_config)
    data_confidence = _data_confidence_score(parsed_inputs, active_config)
    overall_opportunity = _overall_score(
        demand,
        competition,
        price_stability,
        data_confidence,
        active_config,
    )
    return ScoreCard(
        demand=demand,
        competition=competition,
        price_stability=price_stability,
        data_confidence=data_confidence,
        overall_opportunity=overall_opportunity,
    )
