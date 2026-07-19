from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from importlib.resources import files


@dataclass(frozen=True, slots=True)
class ScenarioConfig:
    base_coverage_days: Decimal
    lead_time_factor: Decimal
    maximum_coverage_days: Decimal


@dataclass(frozen=True, slots=True)
class TestBuyConfig:
    formula_version: str
    days_per_month: Decimal
    low_confidence_below: int
    low_confidence_cap_days: Decimal
    money_quantum: Decimal
    sell_through_quantum: Decimal
    scenarios: dict[str, ScenarioConfig]
    configuration_checksum: str


def _decimal(value: object, name: str, *, allow_zero: bool = False) -> Decimal:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a valid decimal string") from exc
    if not parsed.is_finite() or parsed < 0 or (parsed == 0 and not allow_zero):
        raise ValueError(f"{name} is outside its allowed range")
    return parsed


def load_default_test_buy_config() -> TestBuyConfig:
    raw = files("app.modules.sourcing.configs").joinpath("v1.json").read_bytes()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Test-buy configuration must be an object")
    expected = {
        "schema_version",
        "formula_version",
        "days_per_month",
        "low_confidence_below",
        "low_confidence_cap_days",
        "money_quantum",
        "sell_through_quantum",
        "scenarios",
    }
    if set(payload) != expected or payload["schema_version"] != 1:
        raise ValueError("Test-buy configuration has missing, unknown or unsupported fields")
    version = payload["formula_version"]
    confidence = payload["low_confidence_below"]
    scenarios_payload = payload["scenarios"]
    if not isinstance(version, str) or not version.startswith("selleros.test-buy.v"):
        raise ValueError("Test-buy formula version is invalid")
    if (
        not isinstance(confidence, int)
        or isinstance(confidence, bool)
        or not 0 <= confidence <= 100
    ):
        raise ValueError("low_confidence_below must be an integer from 0 through 100")
    if not isinstance(scenarios_payload, dict) or set(scenarios_payload) != {
        "conservative",
        "expected",
        "aggressive",
    }:
        raise ValueError("Exactly three test-buy scenarios are required")
    scenarios: dict[str, ScenarioConfig] = {}
    for name, raw_scenario in scenarios_payload.items():
        if not isinstance(raw_scenario, dict) or set(raw_scenario) != {
            "base_coverage_days",
            "lead_time_factor",
            "maximum_coverage_days",
        }:
            raise ValueError(f"Scenario {name} has an invalid structure")
        scenario = ScenarioConfig(
            base_coverage_days=_decimal(
                raw_scenario["base_coverage_days"], f"{name}.base_coverage_days"
            ),
            lead_time_factor=_decimal(
                raw_scenario["lead_time_factor"], f"{name}.lead_time_factor", allow_zero=True
            ),
            maximum_coverage_days=_decimal(
                raw_scenario["maximum_coverage_days"], f"{name}.maximum_coverage_days"
            ),
        )
        if scenario.maximum_coverage_days < scenario.base_coverage_days:
            raise ValueError(f"Scenario {name} maximum is below its base")
        scenarios[name] = scenario
    return TestBuyConfig(
        formula_version=version,
        days_per_month=_decimal(payload["days_per_month"], "days_per_month"),
        low_confidence_below=confidence,
        low_confidence_cap_days=_decimal(
            payload["low_confidence_cap_days"], "low_confidence_cap_days"
        ),
        money_quantum=_decimal(payload["money_quantum"], "money_quantum"),
        sell_through_quantum=_decimal(payload["sell_through_quantum"], "sell_through_quantum"),
        scenarios=scenarios,
        configuration_checksum=hashlib.sha256(raw).hexdigest(),
    )
