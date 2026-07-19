from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import ROUND_HALF_UP, Decimal
from types import MappingProxyType
from typing import Literal, cast

from app.modules.profitability.config import EconomicsConfig, load_default_economics_config

CalculationStatus = Literal["calculated", "partial"]
FeeStatus = Literal["observed", "estimated", "user_confirmed"]
SellingPriceTaxBasis = Literal["tax_inclusive", "tax_exclusive"]

_HUNDRED = Decimal("100")
_SUPPORTED_FORMULA_VERSION = "selleros.unit-economics.v2"
_FORMULAS = MappingProxyType(
    {
        "revenue_factor": (
            "1 when selling_price_tax_basis = tax_exclusive; otherwise "
            "1 / (1 + gst_rate_percent / 100) when selling_price_tax_basis = tax_inclusive"
        ),
        "fixed_unit_cost": (
            "landed_cost + fulfilment_fee + closing_fee + storage_fee + overhead_cost"
        ),
        "total_variable_rate": (
            "(referral_fee_rate_percent + advertising_rate_percent + " "returns_rate_percent) / 100"
        ),
        "landed_cost": (
            "purchase_cost + purchase_cost * gst_rate_percent / 100 * "
            "(1 - gst_recoverable_percent / 100) + freight_cost + prep_cost + packaging_cost"
        ),
        "net_revenue": "selling_price * revenue_factor",
        "output_gst": "selling_price - net_revenue",
        "amazon_fees": (
            "selling_price * referral_fee_rate_percent / 100 + fulfilment_fee + "
            "closing_fee + storage_fee"
        ),
        "contribution_profit": (
            "net_revenue - landed_cost - amazon_fees - selling_price * "
            "(advertising_rate_percent + returns_rate_percent) / 100 - overhead_cost"
        ),
        "margin_percent": "contribution_profit / net_revenue * 100",
        "roi_percent": "contribution_profit / landed_cost * 100",
        "break_even_price": "fixed_unit_cost / (revenue_factor - total_variable_rate)",
        "minimum_acceptable_price": (
            "fixed_unit_cost / (revenue_factor * (1 - minimum_margin_percent / 100) - "
            "total_variable_rate)"
        ),
        "target_price": (
            "fixed_unit_cost / (revenue_factor * (1 - target_margin_percent / 100) - "
            "total_variable_rate)"
        ),
    }
)


def _validate_decimal(name: str, value: Decimal | None, *, maximum: Decimal | None = None) -> None:
    if value is None:
        return
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TypeError(f"{name} must be a finite Decimal")
    if value < 0:
        raise ValueError(f"{name} cannot be negative")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} cannot be greater than {maximum}")


@dataclass(frozen=True, slots=True)
class EconomicsInputs:
    currency_code: str
    selling_price: Decimal | None
    selling_price_tax_basis: SellingPriceTaxBasis | None
    purchase_cost: Decimal
    gst_rate_percent: Decimal
    gst_recoverable_percent: Decimal
    freight_cost: Decimal
    prep_cost: Decimal
    packaging_cost: Decimal
    advertising_rate_percent: Decimal
    returns_rate_percent: Decimal
    overhead_cost: Decimal
    referral_fee_rate_percent: Decimal | None
    fulfilment_fee: Decimal | None
    closing_fee: Decimal | None
    storage_fee: Decimal | None
    minimum_margin_percent: Decimal
    target_margin_percent: Decimal
    fee_status: FeeStatus | None = None

    def __post_init__(self) -> None:
        if len(self.currency_code) != 3 or not self.currency_code.isalpha():
            raise ValueError("currency_code must be a three-letter code")
        decimal_names = {
            field.name
            for field in fields(self)
            if field.name not in {"currency_code", "selling_price_tax_basis", "fee_status"}
        }
        for name in decimal_names:
            maximum = _HUNDRED if name.endswith("_percent") else None
            _validate_decimal(name, cast(Decimal | None, getattr(self, name)), maximum=maximum)
        if self.minimum_margin_percent >= _HUNDRED or self.target_margin_percent >= _HUNDRED:
            raise ValueError("margin percentages must be less than 100")
        if self.target_margin_percent < self.minimum_margin_percent:
            raise ValueError("target margin cannot be below minimum margin")
        if self.fee_status not in {None, "observed", "estimated", "user_confirmed"}:
            raise ValueError("fee_status is outside the supported evidence labels")
        if self.selling_price_tax_basis not in {None, "tax_inclusive", "tax_exclusive"}:
            raise ValueError("selling_price_tax_basis is outside the supported tax bases")


@dataclass(frozen=True, slots=True)
class EconomicsOutputs:
    landed_cost: Decimal
    net_revenue: Decimal | None
    output_gst: Decimal | None
    amazon_fees: Decimal | None
    contribution_profit: Decimal | None
    margin_percent: Decimal | None
    roi_percent: Decimal | None
    break_even_price: Decimal | None
    minimum_acceptable_price: Decimal | None
    target_price: Decimal | None


@dataclass(frozen=True, slots=True)
class EconomicsResult:
    formula_version: str
    configuration_checksum: str
    status: CalculationStatus
    selling_price_tax_basis: SellingPriceTaxBasis | None
    outputs: EconomicsOutputs
    inputs: dict[str, str | None]
    formulas: dict[str, str]
    reason_codes: tuple[str, ...]


def _money(value: Decimal, config: EconomicsConfig) -> Decimal:
    return value.quantize(config.money_quantum, rounding=ROUND_HALF_UP)


def _percentage(value: Decimal, config: EconomicsConfig) -> Decimal:
    return value.quantize(config.percentage_quantum, rounding=ROUND_HALF_UP)


def _input_trace(inputs: EconomicsInputs) -> dict[str, str | None]:
    trace: dict[str, str | None] = {}
    for field in fields(inputs):
        value = getattr(inputs, field.name)
        trace[field.name] = str(value) if value is not None else None
    return trace


def calculate_unit_economics(
    inputs: EconomicsInputs,
    config: EconomicsConfig | None = None,
) -> EconomicsResult:
    active_config = config or load_default_economics_config()
    if active_config.formula_version != _SUPPORTED_FORMULA_VERSION:
        raise ValueError(
            "Economics configuration formula_version does not match this v2 decision kernel"
        )
    reasons: list[str] = []
    gst_rate = inputs.gst_rate_percent / _HUNDRED
    recoverable_rate = inputs.gst_recoverable_percent / _HUNDRED
    unrecoverable_gst = inputs.purchase_cost * gst_rate * (Decimal("1") - recoverable_rate)
    landed_unrounded = (
        inputs.purchase_cost
        + unrecoverable_gst
        + inputs.freight_cost
        + inputs.prep_cost
        + inputs.packaging_cost
    )

    fee_values = (
        inputs.referral_fee_rate_percent,
        inputs.fulfilment_fee,
        inputs.closing_fee,
        inputs.storage_fee,
    )
    fees_complete = all(value is not None for value in fee_values)
    if not fees_complete:
        reasons.append("ECONOMICS_FEE_INPUTS_MISSING")
    elif inputs.fee_status == "estimated":
        reasons.append("ECONOMICS_FEES_ESTIMATED")

    amazon_fees: Decimal | None = None
    net_revenue: Decimal | None = None
    output_gst: Decimal | None = None
    contribution: Decimal | None = None
    margin: Decimal | None = None
    roi: Decimal | None = None
    break_even: Decimal | None = None
    minimum_price: Decimal | None = None
    target_price: Decimal | None = None

    revenue_factor: Decimal | None = None
    if inputs.selling_price_tax_basis == "tax_exclusive":
        revenue_factor = Decimal("1")
    elif inputs.selling_price_tax_basis == "tax_inclusive":
        revenue_factor = Decimal("1") / (Decimal("1") + gst_rate)
    else:
        reasons.append("ECONOMICS_SELLING_PRICE_TAX_BASIS_MISSING")

    if inputs.selling_price is None:
        reasons.append("ECONOMICS_SELLING_PRICE_MISSING")

    if fees_complete and revenue_factor is not None:
        referral_rate = cast(Decimal, inputs.referral_fee_rate_percent) / _HUNDRED
        fulfilment_fee = cast(Decimal, inputs.fulfilment_fee)
        closing_fee = cast(Decimal, inputs.closing_fee)
        storage_fee = cast(Decimal, inputs.storage_fee)
        fixed_cost = (
            landed_unrounded + fulfilment_fee + closing_fee + storage_fee + inputs.overhead_cost
        )
        variable_rate = (
            referral_rate
            + inputs.advertising_rate_percent / _HUNDRED
            + inputs.returns_rate_percent / _HUNDRED
        )

        break_even_denominator = revenue_factor - variable_rate
        minimum_denominator = (
            revenue_factor * (Decimal("1") - inputs.minimum_margin_percent / _HUNDRED)
            - variable_rate
        )
        target_denominator = (
            revenue_factor * (Decimal("1") - inputs.target_margin_percent / _HUNDRED)
            - variable_rate
        )
        if break_even_denominator > 0:
            break_even = _money(fixed_cost / break_even_denominator, active_config)
        else:
            reasons.append("ECONOMICS_BREAK_EVEN_RATE_INVALID")
        if minimum_denominator > 0:
            minimum_price = _money(fixed_cost / minimum_denominator, active_config)
        else:
            reasons.append("ECONOMICS_MINIMUM_MARGIN_UNACHIEVABLE")
        if target_denominator > 0:
            target_price = _money(fixed_cost / target_denominator, active_config)
        else:
            reasons.append("ECONOMICS_TARGET_MARGIN_UNACHIEVABLE")

        if inputs.selling_price is not None:
            net_revenue_unrounded = inputs.selling_price * revenue_factor
            output_gst_unrounded = inputs.selling_price - net_revenue_unrounded
            amazon_fees_unrounded = (
                inputs.selling_price * referral_rate + fulfilment_fee + closing_fee + storage_fee
            )
            allowances = (
                inputs.selling_price
                * (inputs.advertising_rate_percent + inputs.returns_rate_percent)
                / _HUNDRED
            )
            contribution_unrounded = (
                net_revenue_unrounded
                - landed_unrounded
                - amazon_fees_unrounded
                - allowances
                - inputs.overhead_cost
            )
            net_revenue = _money(net_revenue_unrounded, active_config)
            output_gst = _money(output_gst_unrounded, active_config)
            amazon_fees = _money(amazon_fees_unrounded, active_config)
            contribution = _money(contribution_unrounded, active_config)
            if net_revenue_unrounded > 0:
                margin = _percentage(
                    contribution_unrounded / net_revenue_unrounded * _HUNDRED,
                    active_config,
                )
            else:
                reasons.append("ECONOMICS_MARGIN_PRICE_ZERO")
            if landed_unrounded > 0:
                roi = _percentage(
                    contribution_unrounded / landed_unrounded * _HUNDRED,
                    active_config,
                )
            else:
                reasons.append("ECONOMICS_ROI_LANDED_COST_ZERO")
    elif revenue_factor is not None and inputs.selling_price is not None:
        net_revenue_unrounded = inputs.selling_price * revenue_factor
        net_revenue = _money(net_revenue_unrounded, active_config)
        output_gst = _money(inputs.selling_price - net_revenue_unrounded, active_config)

    outputs = EconomicsOutputs(
        landed_cost=_money(landed_unrounded, active_config),
        net_revenue=net_revenue,
        output_gst=output_gst,
        amazon_fees=amazon_fees,
        contribution_profit=contribution,
        margin_percent=margin,
        roi_percent=roi,
        break_even_price=break_even,
        minimum_acceptable_price=minimum_price,
        target_price=target_price,
    )
    return EconomicsResult(
        formula_version=active_config.formula_version,
        configuration_checksum=active_config.configuration_checksum,
        status=(
            "calculated"
            if all(getattr(outputs, field.name) is not None for field in fields(outputs))
            else "partial"
        ),
        selling_price_tax_basis=inputs.selling_price_tax_basis,
        outputs=outputs,
        inputs=_input_trace(inputs),
        formulas=dict(_FORMULAS),
        reason_codes=tuple(dict.fromkeys(reasons)),
    )
