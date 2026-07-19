from decimal import Decimal

import pytest

from app.modules.sourcing import OfferTier, recommend_test_buy
from app.modules.sourcing import TestBuyInputs as BuyInputs


def _inputs(
    *,
    monthly_demand_units: int | None = 60,
    data_confidence_score: int | None = 80,
    lead_time_days: int = 20,
    minimum_order_quantity: int = 5,
    budget_amount: Decimal = Decimal("1000.00"),
    budget_currency_code: str = "INR",
    offer_currency_code: str = "INR",
    price_tiers: tuple[OfferTier, ...] = (
        OfferTier(minimum_quantity=5, unit_cost=Decimal("10.00")),
        OfferTier(minimum_quantity=50, unit_cost=Decimal("8.00")),
    ),
    offer_valid: bool = True,
) -> BuyInputs:
    return BuyInputs(
        monthly_demand_units=monthly_demand_units,
        data_confidence_score=data_confidence_score,
        lead_time_days=lead_time_days,
        minimum_order_quantity=minimum_order_quantity,
        budget_amount=budget_amount,
        budget_currency_code=budget_currency_code,
        offer_currency_code=offer_currency_code,
        price_tiers=price_tiers,
        offer_valid=offer_valid,
    )


def test_three_scenarios_apply_lead_time_tiers_budget_and_sell_through() -> None:
    result = recommend_test_buy(_inputs())

    assert result.formula_version == "selleros.test-buy.v1"
    assert len(result.configuration_checksum) == 64
    conservative, expected, aggressive = result.scenarios
    assert (conservative.quantity, conservative.unit_cost) == (38, Decimal("10.00"))
    assert conservative.required_investment == Decimal("380.00")
    assert conservative.expected_sell_through_days == Decimal("19.0")
    assert (expected.quantity, expected.unit_cost) == (80, Decimal("8.00"))
    assert expected.required_investment == Decimal("640.00")
    assert expected.expected_sell_through_days == Decimal("40.0")
    assert (aggressive.quantity, aggressive.unit_cost) == (125, Decimal("8.00"))
    assert aggressive.required_investment == Decimal("1000.00")
    assert aggressive.expected_sell_through_days == Decimal("62.5")
    assert "TEST_BUY_BUDGET_CAP_APPLIED" in aggressive.reason_codes
    assert result.advisory_only is True


def test_low_confidence_caps_every_scenario() -> None:
    result = recommend_test_buy(_inputs(data_confidence_score=40))

    assert [scenario.quantity for scenario in result.scenarios] == [28, 28, 28]
    assert all(
        "TEST_BUY_LOW_CONFIDENCE_CAP_APPLIED" in scenario.reason_codes
        for scenario in result.scenarios
    )


def test_low_confidence_never_promotes_moq_above_cap() -> None:
    result = recommend_test_buy(
        _inputs(
            data_confidence_score=40,
            minimum_order_quantity=30,
            price_tiers=(OfferTier(30, Decimal("10.00")),),
        )
    )

    assert [scenario.status for scenario in result.scenarios] == ["blocked"] * 3
    assert [scenario.quantity for scenario in result.scenarios] == [0, 0, 0]
    assert all(
        "TEST_BUY_MOQ_EXCEEDS_CONFIDENCE_CAP" in scenario.reason_codes
        for scenario in result.scenarios
    )


def test_missing_demand_zero_budget_and_expired_offer_fail_closed() -> None:
    for inputs, code in (
        (_inputs(monthly_demand_units=None), "TEST_BUY_MONTHLY_DEMAND_MISSING"),
        (_inputs(monthly_demand_units=0), "TEST_BUY_MONTHLY_DEMAND_ZERO"),
        (_inputs(budget_amount=Decimal("0")), "TEST_BUY_BUDGET_ZERO"),
        (_inputs(offer_valid=False), "TEST_BUY_OFFER_EXPIRED"),
    ):
        result = recommend_test_buy(inputs)
        assert all(scenario.status == "blocked" for scenario in result.scenarios)
        assert code in result.reason_codes


def test_budget_below_moq_blocks_without_placing_an_order() -> None:
    result = recommend_test_buy(_inputs(budget_amount=Decimal("49.99")))

    assert all(scenario.quantity == 0 for scenario in result.scenarios)
    assert all(
        "TEST_BUY_BUDGET_BELOW_MOQ" in scenario.reason_codes for scenario in result.scenarios
    )


def test_currency_mismatch_is_never_converted_or_inferred() -> None:
    with pytest.raises(ValueError, match="currency must match"):
        _inputs(budget_currency_code="USD", offer_currency_code="INR")
