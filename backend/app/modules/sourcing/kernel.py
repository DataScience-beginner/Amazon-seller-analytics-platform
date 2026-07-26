from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Literal

from app.modules.sourcing.config import TestBuyConfig, load_default_test_buy_config

ScenarioName = Literal["conservative", "expected", "aggressive"]
ScenarioStatus = Literal["recommended", "blocked"]


@dataclass(frozen=True, slots=True)
class OfferTier:
    minimum_quantity: int
    unit_cost: Decimal

    def __post_init__(self) -> None:
        if self.minimum_quantity < 1:
            raise ValueError("Tier minimum quantity must be positive")
        if not isinstance(self.unit_cost, Decimal) or not self.unit_cost.is_finite():
            raise TypeError("Tier cost must be a finite Decimal")
        if self.unit_cost < 0:
            raise ValueError("Tier cost cannot be negative")


@dataclass(frozen=True, slots=True)
class TestBuyInputs:
    monthly_demand_units: int | None
    data_confidence_score: int | None
    lead_time_days: int
    minimum_order_quantity: int
    budget_amount: Decimal
    budget_currency_code: str
    offer_currency_code: str
    price_tiers: tuple[OfferTier, ...]
    offer_valid: bool = True

    def __post_init__(self) -> None:
        if self.monthly_demand_units is not None and self.monthly_demand_units < 0:
            raise ValueError("Monthly demand cannot be negative")
        if self.data_confidence_score is not None and not 0 <= self.data_confidence_score <= 100:
            raise ValueError("Data confidence must be from 0 through 100")
        if self.lead_time_days < 0 or self.minimum_order_quantity < 1:
            raise ValueError("Lead time and MOQ are outside their allowed ranges")
        if not isinstance(self.budget_amount, Decimal) or not self.budget_amount.is_finite():
            raise TypeError("Budget must be a finite Decimal")
        if self.budget_amount < 0:
            raise ValueError("Budget cannot be negative")
        if self.budget_currency_code != self.offer_currency_code:
            raise ValueError("Budget and offer currency must match; currency is never inferred")
        if not self.price_tiers:
            raise ValueError("At least one price tier is required")
        if not isinstance(self.offer_valid, bool):
            raise TypeError("offer_valid must be a boolean")
        quantities = [tier.minimum_quantity for tier in self.price_tiers]
        if quantities != sorted(set(quantities)):
            raise ValueError("Price tiers must have unique increasing quantities")
        if quantities[0] != self.minimum_order_quantity:
            raise ValueError("The first price tier must start at MOQ")


@dataclass(frozen=True, slots=True)
class TestBuyScenario:
    scenario: ScenarioName
    quantity: int
    unit_cost: Decimal | None
    required_investment: Decimal
    expected_sell_through_days: Decimal | None
    status: ScenarioStatus
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TestBuyResult:
    formula_version: str
    configuration_checksum: str
    inputs: dict[str, str | int | None]
    scenarios: tuple[TestBuyScenario, TestBuyScenario, TestBuyScenario]
    reason_codes: tuple[str, ...]
    advisory_only: bool = True


def _ceil_units(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def _unit_cost(quantity: int, tiers: tuple[OfferTier, ...]) -> Decimal:
    applicable = tiers[0].unit_cost
    for tier in tiers:
        if quantity < tier.minimum_quantity:
            break
        applicable = tier.unit_cost
    return applicable


def _maximum_affordable_quantity(
    *, target: int, budget: Decimal, tiers: tuple[OfferTier, ...]
) -> int:
    best = 0
    for index, tier in enumerate(tiers):
        next_minimum = tiers[index + 1].minimum_quantity if index + 1 < len(tiers) else None
        upper = target if next_minimum is None else min(target, next_minimum - 1)
        if upper < tier.minimum_quantity:
            continue
        if tier.unit_cost == 0:
            affordable = upper
        else:
            affordable = int((budget / tier.unit_cost).to_integral_value(rounding="ROUND_FLOOR"))
        candidate = min(upper, affordable)
        if candidate >= tier.minimum_quantity:
            best = max(best, candidate)
    return best


def _blocked(
    name: ScenarioName, reason_codes: tuple[str, ...], config: TestBuyConfig
) -> TestBuyScenario:
    return TestBuyScenario(
        scenario=name,
        quantity=0,
        unit_cost=None,
        required_investment=Decimal("0").quantize(config.money_quantum, rounding=ROUND_HALF_UP),
        expected_sell_through_days=None,
        status="blocked",
        reason_codes=reason_codes,
    )


def recommend_test_buy(inputs: TestBuyInputs, config: TestBuyConfig | None = None) -> TestBuyResult:
    active_config = config or load_default_test_buy_config()
    shared_reasons: list[str] = []
    if inputs.monthly_demand_units is None:
        shared_reasons.append("TEST_BUY_MONTHLY_DEMAND_MISSING")
    elif inputs.monthly_demand_units == 0:
        shared_reasons.append("TEST_BUY_MONTHLY_DEMAND_ZERO")
    if inputs.data_confidence_score is None:
        shared_reasons.append("TEST_BUY_DATA_CONFIDENCE_MISSING")
    if inputs.budget_amount == 0:
        shared_reasons.append("TEST_BUY_BUDGET_ZERO")
    if not inputs.offer_valid:
        shared_reasons.append("TEST_BUY_OFFER_EXPIRED")

    scenario_names: tuple[ScenarioName, ScenarioName, ScenarioName] = (
        "conservative",
        "expected",
        "aggressive",
    )
    if shared_reasons:
        blocked = tuple(
            _blocked(name, tuple(shared_reasons), active_config) for name in scenario_names
        )
        return TestBuyResult(
            formula_version=active_config.formula_version,
            configuration_checksum=active_config.configuration_checksum,
            inputs=_trace(inputs),
            scenarios=(blocked[0], blocked[1], blocked[2]),
            reason_codes=tuple(shared_reasons),
        )

    demand = Decimal(inputs.monthly_demand_units or 0)
    confidence = inputs.data_confidence_score or 0
    low_confidence = confidence < active_config.low_confidence_below
    confidence_cap = _ceil_units(
        demand * active_config.low_confidence_cap_days / active_config.days_per_month
    )
    scenarios: list[TestBuyScenario] = []
    aggregate_reasons: list[str] = []
    for name in scenario_names:
        scenario_config = active_config.scenarios[name]
        coverage_days = min(
            scenario_config.base_coverage_days
            + Decimal(inputs.lead_time_days) * scenario_config.lead_time_factor,
            scenario_config.maximum_coverage_days,
        )
        target = max(
            inputs.minimum_order_quantity,
            _ceil_units(demand * coverage_days / active_config.days_per_month),
        )
        reasons = ["TEST_BUY_DEMAND_AND_LEAD_TIME_APPLIED"]
        if low_confidence:
            reasons.append("TEST_BUY_LOW_CONFIDENCE_CAP_APPLIED")
            if inputs.minimum_order_quantity > confidence_cap:
                reasons.append("TEST_BUY_MOQ_EXCEEDS_CONFIDENCE_CAP")
                aggregate_reasons.extend(reasons)
                scenarios.append(_blocked(name, tuple(reasons), active_config))
                continue
            target = min(target, confidence_cap)

        quantity = _maximum_affordable_quantity(
            target=target,
            budget=inputs.budget_amount,
            tiers=inputs.price_tiers,
        )
        if quantity < inputs.minimum_order_quantity:
            reasons.append("TEST_BUY_BUDGET_BELOW_MOQ")
            aggregate_reasons.extend(reasons)
            scenarios.append(_blocked(name, tuple(reasons), active_config))
            continue
        if quantity < target:
            reasons.append("TEST_BUY_BUDGET_CAP_APPLIED")
        unit_cost = _unit_cost(quantity, inputs.price_tiers)
        investment = (Decimal(quantity) * unit_cost).quantize(
            active_config.money_quantum, rounding=ROUND_HALF_UP
        )
        sell_through = (Decimal(quantity) / demand * active_config.days_per_month).quantize(
            active_config.sell_through_quantum, rounding=ROUND_HALF_UP
        )
        aggregate_reasons.extend(reasons)
        scenarios.append(
            TestBuyScenario(
                scenario=name,
                quantity=quantity,
                unit_cost=unit_cost,
                required_investment=investment,
                expected_sell_through_days=sell_through,
                status="recommended",
                reason_codes=tuple(reasons),
            )
        )

    return TestBuyResult(
        formula_version=active_config.formula_version,
        configuration_checksum=active_config.configuration_checksum,
        inputs=_trace(inputs),
        scenarios=(scenarios[0], scenarios[1], scenarios[2]),
        reason_codes=tuple(dict.fromkeys(aggregate_reasons)),
    )


def _trace(inputs: TestBuyInputs) -> dict[str, str | int | None]:
    return {
        "monthly_demand_units": inputs.monthly_demand_units,
        "data_confidence_score": inputs.data_confidence_score,
        "lead_time_days": inputs.lead_time_days,
        "minimum_order_quantity": inputs.minimum_order_quantity,
        "budget_amount": str(inputs.budget_amount),
        "budget_currency_code": inputs.budget_currency_code,
        "offer_currency_code": inputs.offer_currency_code,
        "offer_valid": str(inputs.offer_valid).lower(),
        "price_tiers": ",".join(
            f"{tier.minimum_quantity}:{tier.unit_cost}" for tier in inputs.price_tiers
        ),
    }
