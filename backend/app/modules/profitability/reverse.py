from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal

FORMULA_VERSION = "selleros.target-sourcing-cost.v1"
_HUNDRED = Decimal("100")
_MONEY = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class TargetCostAssumptions:
    gst_rate_percent: Decimal = Decimal("18")
    amazon_fee_percent: Decimal = Decimal("15")
    shipping_percent: Decimal = Decimal("8")
    advertising_percent: Decimal = Decimal("5")
    returns_percent: Decimal = Decimal("3")
    target_profit_percent: Decimal = Decimal("15")

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0 or value > 100:
                raise ValueError(f"{name} must be a Decimal between 0 and 100")
        if self.gst_rate_percent >= 100:
            raise ValueError("gst_rate_percent must be below 100")

    @property
    def configuration_checksum(self) -> str:
        payload = json.dumps(
            {name: str(value) for name, value in asdict(self).items()},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class TargetCostResult:
    selling_price: Decimal
    net_revenue_ex_gst: Decimal
    output_gst: Decimal
    amazon_fee: Decimal
    shipping_allowance: Decimal
    advertising_allowance: Decimal
    returns_allowance: Decimal
    target_profit: Decimal
    maximum_wholesale_cost_ex_gst: Decimal
    wholesale_cash_outlay_including_gst: Decimal
    feasible: bool


def calculate_target_sourcing_cost(
    selling_price: Decimal, assumptions: TargetCostAssumptions
) -> TargetCostResult:
    if not selling_price.is_finite() or selling_price < 0:
        raise ValueError("selling_price must be a non-negative finite Decimal")
    gst_rate = assumptions.gst_rate_percent / _HUNDRED
    net_revenue = selling_price / (Decimal("1") + gst_rate)
    output_gst = selling_price - net_revenue
    amazon_fee = selling_price * assumptions.amazon_fee_percent / _HUNDRED
    shipping = selling_price * assumptions.shipping_percent / _HUNDRED
    advertising = selling_price * assumptions.advertising_percent / _HUNDRED
    returns = selling_price * assumptions.returns_percent / _HUNDRED
    target_profit = net_revenue * assumptions.target_profit_percent / _HUNDRED
    maximum_cost = net_revenue - amazon_fee - shipping - advertising - returns - target_profit
    feasible = maximum_cost > 0
    safe_cost = max(maximum_cost, Decimal("0"))
    return TargetCostResult(
        selling_price=_money(selling_price),
        net_revenue_ex_gst=_money(net_revenue),
        output_gst=_money(output_gst),
        amazon_fee=_money(amazon_fee),
        shipping_allowance=_money(shipping),
        advertising_allowance=_money(advertising),
        returns_allowance=_money(returns),
        target_profit=_money(target_profit),
        maximum_wholesale_cost_ex_gst=_money(safe_cost),
        wholesale_cash_outlay_including_gst=_money(safe_cost * (Decimal("1") + gst_rate)),
        feasible=feasible,
    )


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY, rounding=ROUND_HALF_UP)
