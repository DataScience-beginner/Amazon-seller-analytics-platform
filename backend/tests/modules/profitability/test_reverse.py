from decimal import Decimal

from app.modules.profitability.reverse import (
    FORMULA_VERSION,
    TargetCostAssumptions,
    calculate_target_sourcing_cost,
)


def test_target_sourcing_cost_uses_explicit_decimal_assumptions() -> None:
    assumptions = TargetCostAssumptions()

    result = calculate_target_sourcing_cost(Decimal("1180.00"), assumptions)

    assert FORMULA_VERSION == "selleros.target-sourcing-cost.v1"
    assert result.net_revenue_ex_gst == Decimal("1000.00")
    assert result.output_gst == Decimal("180.00")
    assert result.amazon_fee == Decimal("177.00")
    assert result.shipping_allowance == Decimal("94.40")
    assert result.advertising_allowance == Decimal("59.00")
    assert result.returns_allowance == Decimal("35.40")
    assert result.target_profit == Decimal("150.00")
    assert result.maximum_wholesale_cost_ex_gst == Decimal("484.20")
    assert result.wholesale_cash_outlay_including_gst == Decimal("571.36")
    assert result.feasible is True
    assert len(assumptions.configuration_checksum) == 64


def test_target_sourcing_cost_fails_closed_when_allowances_exceed_revenue() -> None:
    result = calculate_target_sourcing_cost(
        Decimal("100"),
        TargetCostAssumptions(
            amazon_fee_percent=Decimal("50"),
            shipping_percent=Decimal("30"),
            advertising_percent=Decimal("20"),
            returns_percent=Decimal("20"),
            target_profit_percent=Decimal("50"),
        ),
    )

    assert result.feasible is False
    assert result.maximum_wholesale_cost_ex_gst == Decimal("0.00")
