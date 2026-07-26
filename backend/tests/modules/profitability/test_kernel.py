from dataclasses import replace
from decimal import Decimal
from typing import cast

import pytest

from app.modules.profitability import EconomicsInputs, calculate_unit_economics
from app.modules.profitability.config import load_default_economics_config
from app.modules.profitability.kernel import FeeStatus, SellingPriceTaxBasis


def _inputs(
    *,
    selling_price: Decimal | None = Decimal("100.00"),
    selling_price_tax_basis: SellingPriceTaxBasis | None = "tax_exclusive",
    purchase_cost: Decimal = Decimal("40.00"),
    gst_rate_percent: Decimal = Decimal("10.00"),
    gst_recoverable_percent: Decimal = Decimal("50.00"),
    freight_cost: Decimal = Decimal("3.00"),
    prep_cost: Decimal = Decimal("2.00"),
    packaging_cost: Decimal = Decimal("1.00"),
    advertising_rate_percent: Decimal = Decimal("5.00"),
    returns_rate_percent: Decimal = Decimal("2.00"),
    overhead_cost: Decimal = Decimal("2.00"),
    referral_fee_rate_percent: Decimal | None = Decimal("15.00"),
    fulfilment_fee: Decimal | None = Decimal("5.00"),
    closing_fee: Decimal | None = Decimal("1.00"),
    storage_fee: Decimal | None = Decimal("1.00"),
    fee_status: FeeStatus | None = "observed",
) -> EconomicsInputs:
    return EconomicsInputs(
        currency_code="INR",
        selling_price=selling_price,
        selling_price_tax_basis=selling_price_tax_basis,
        purchase_cost=purchase_cost,
        gst_rate_percent=gst_rate_percent,
        gst_recoverable_percent=gst_recoverable_percent,
        freight_cost=freight_cost,
        prep_cost=prep_cost,
        packaging_cost=packaging_cost,
        advertising_rate_percent=advertising_rate_percent,
        returns_rate_percent=returns_rate_percent,
        overhead_cost=overhead_cost,
        referral_fee_rate_percent=referral_fee_rate_percent,
        fulfilment_fee=fulfilment_fee,
        closing_fee=closing_fee,
        storage_fee=storage_fee,
        minimum_margin_percent=Decimal("10.00"),
        target_margin_percent=Decimal("20.00"),
        fee_status=fee_status,
    )


def test_fixed_example_traces_all_phase_2_outputs() -> None:
    result = calculate_unit_economics(_inputs())

    assert result.formula_version == "selleros.unit-economics.v2"
    assert len(result.configuration_checksum) == 64
    assert result.status == "calculated"
    assert result.outputs.landed_cost == Decimal("48.00")
    assert result.outputs.net_revenue == Decimal("100.00")
    assert result.outputs.output_gst == Decimal("0.00")
    assert result.outputs.amazon_fees == Decimal("22.00")
    assert result.outputs.contribution_profit == Decimal("21.00")
    assert result.outputs.margin_percent == Decimal("21.00")
    assert result.outputs.roi_percent == Decimal("43.75")
    assert result.outputs.break_even_price == Decimal("73.08")
    assert result.outputs.minimum_acceptable_price == Decimal("83.82")
    assert result.outputs.target_price == Decimal("98.28")
    assert set(result.formulas) == {
        "revenue_factor",
        "fixed_unit_cost",
        "total_variable_rate",
        "landed_cost",
        "net_revenue",
        "output_gst",
        "amazon_fees",
        "contribution_profit",
        "margin_percent",
        "roi_percent",
        "break_even_price",
        "minimum_acceptable_price",
        "target_price",
    }
    assert result.inputs["purchase_cost"] == "40.00"
    assert result.inputs["selling_price_tax_basis"] == "tax_exclusive"
    assert "selling_price_tax_basis" in result.formulas["revenue_factor"]
    assert "landed_cost" in result.formulas["fixed_unit_cost"]
    assert "referral_fee_rate_percent" in result.formulas["total_variable_rate"]


def test_tax_inclusive_price_uses_net_revenue_but_gross_fee_bases() -> None:
    result = calculate_unit_economics(
        _inputs(
            selling_price=Decimal("118.00"),
            selling_price_tax_basis="tax_inclusive",
            gst_rate_percent=Decimal("18.00"),
            gst_recoverable_percent=Decimal("100.00"),
        )
    )

    assert result.outputs.landed_cost == Decimal("46.00")
    assert result.outputs.net_revenue == Decimal("100.00")
    assert result.outputs.output_gst == Decimal("18.00")
    assert result.outputs.amazon_fees == Decimal("24.70")
    assert result.outputs.contribution_profit == Decimal("19.04")
    assert result.outputs.margin_percent == Decimal("19.04")
    assert result.outputs.roi_percent == Decimal("41.39")
    assert result.outputs.break_even_price == Decimal("87.66")
    assert result.outputs.minimum_acceptable_price == Decimal("101.34")
    assert result.outputs.target_price == Decimal("120.10")


def test_unknown_legacy_tax_basis_blocks_every_price_dependent_output() -> None:
    result = calculate_unit_economics(_inputs(selling_price_tax_basis=None))

    assert result.status == "partial"
    assert result.outputs.landed_cost == Decimal("48.00")
    assert result.outputs.net_revenue is None
    assert result.outputs.output_gst is None
    assert result.outputs.amazon_fees is None
    assert result.outputs.contribution_profit is None
    assert result.outputs.margin_percent is None
    assert result.outputs.roi_percent is None
    assert result.outputs.break_even_price is None
    assert result.outputs.minimum_acceptable_price is None
    assert result.outputs.target_price is None
    assert "ECONOMICS_SELLING_PRICE_TAX_BASIS_MISSING" in result.reason_codes


def test_kernel_rejects_mismatched_archived_formula_version() -> None:
    mismatched = replace(
        load_default_economics_config(), formula_version="selleros.unit-economics.v1"
    )

    with pytest.raises(ValueError, match="does not match this v2 decision kernel"):
        calculate_unit_economics(_inputs(), config=mismatched)


def test_money_rounding_is_decimal_half_up() -> None:
    result = calculate_unit_economics(
        _inputs(
            selling_price=None,
            purchase_cost=Decimal("1.0000"),
            gst_rate_percent=Decimal("0"),
            gst_recoverable_percent=Decimal("0"),
            freight_cost=Decimal("0.0050"),
            prep_cost=Decimal("0"),
            packaging_cost=Decimal("0"),
        )
    )

    assert result.outputs.landed_cost == Decimal("1.01")


def test_missing_fees_are_not_replaced_with_zero() -> None:
    result = calculate_unit_economics(
        _inputs(
            referral_fee_rate_percent=None,
            fulfilment_fee=None,
            closing_fee=None,
            storage_fee=None,
            fee_status=None,
        )
    )

    assert result.status == "partial"
    assert result.outputs.landed_cost == Decimal("48.00")
    assert result.outputs.amazon_fees is None
    assert result.outputs.contribution_profit is None
    assert result.outputs.break_even_price is None
    assert result.reason_codes == ("ECONOMICS_FEE_INPUTS_MISSING",)


def test_zero_denominators_are_disclosed_not_divided() -> None:
    result = calculate_unit_economics(
        _inputs(
            selling_price=Decimal("0"),
            purchase_cost=Decimal("0"),
            gst_rate_percent=Decimal("0"),
            freight_cost=Decimal("0"),
            prep_cost=Decimal("0"),
            packaging_cost=Decimal("0"),
            fulfilment_fee=Decimal("0"),
            closing_fee=Decimal("0"),
            storage_fee=Decimal("0"),
            overhead_cost=Decimal("0"),
        )
    )

    assert result.outputs.margin_percent is None
    assert result.outputs.roi_percent is None
    assert "ECONOMICS_MARGIN_PRICE_ZERO" in result.reason_codes
    assert "ECONOMICS_ROI_LANDED_COST_ZERO" in result.reason_codes


def test_binary_float_financial_input_is_rejected() -> None:
    with pytest.raises(TypeError, match="finite Decimal"):
        _inputs(purchase_cost=cast(Decimal, 1.25))


def test_fee_status_is_a_closed_evidence_contract() -> None:
    with pytest.raises(ValueError, match="supported evidence"):
        _inputs(fee_status=cast(FeeStatus, "guessed"))


def test_unachievable_price_denominators_are_explicit() -> None:
    result = calculate_unit_economics(
        _inputs(
            referral_fee_rate_percent=Decimal("90"),
            advertising_rate_percent=Decimal("10"),
            returns_rate_percent=Decimal("10"),
        )
    )

    assert result.outputs.break_even_price is None
    assert result.outputs.minimum_acceptable_price is None
    assert result.outputs.target_price is None
    assert {
        "ECONOMICS_BREAK_EVEN_RATE_INVALID",
        "ECONOMICS_MINIMUM_MARGIN_UNACHIEVABLE",
        "ECONOMICS_TARGET_MARGIN_UNACHIEVABLE",
    }.issubset(result.reason_codes)
