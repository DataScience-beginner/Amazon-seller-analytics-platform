from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from importlib.resources import files
from typing import Any


@dataclass(frozen=True, slots=True)
class EconomicsConfig:
    schema_version: int
    formula_version: str
    money_quantum: Decimal
    percentage_quantum: Decimal
    rounding_mode: str
    configuration_checksum: str


def _decimal(value: object, field: str) -> Decimal:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field} must be a valid decimal string") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"{field} must be finite and positive")
    return parsed


def _require_keys(payload: dict[str, Any]) -> None:
    expected = {
        "schema_version",
        "formula_version",
        "money_quantum",
        "percentage_quantum",
        "rounding_mode",
    }
    if set(payload) != expected:
        raise ValueError("Economics configuration has missing or unknown keys")


def load_default_economics_config() -> EconomicsConfig:
    raw = files("app.modules.profitability.configs").joinpath("v2.json").read_bytes()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Economics configuration must be a JSON object")
    _require_keys(payload)
    if payload["schema_version"] != 1:
        raise ValueError("Unsupported economics configuration schema")
    formula_version = payload["formula_version"]
    if not isinstance(formula_version, str) or not formula_version.startswith(
        "selleros.unit-economics.v"
    ):
        raise ValueError("Economics formula version is invalid")
    if payload["rounding_mode"] != "ROUND_HALF_UP":
        raise ValueError("Unsupported economics rounding mode")
    return EconomicsConfig(
        schema_version=1,
        formula_version=formula_version,
        money_quantum=_decimal(payload["money_quantum"], "money_quantum"),
        percentage_quantum=_decimal(payload["percentage_quantum"], "percentage_quantum"),
        rounding_mode="ROUND_HALF_UP",
        configuration_checksum=hashlib.sha256(raw).hexdigest(),
    )
