from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models.domain import FeeInputStatus, SellingPriceTaxBasis

ScopeId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=36)]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
NonNegativeMoney = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)]
OptionalNonNegativeMoney = Annotated[Decimal | None, Field(ge=0, max_digits=14, decimal_places=4)]
Percentage = Annotated[Decimal, Field(ge=0, le=100, max_digits=7, decimal_places=4)]
MarginPercentage = Annotated[Decimal, Field(ge=0, lt=100, max_digits=7, decimal_places=4)]

_DECIMAL_FIELDS = (
    "purchase_cost",
    "gst_rate_percent",
    "gst_recoverable_percent",
    "freight_cost",
    "prep_cost",
    "packaging_cost",
    "advertising_rate_percent",
    "returns_rate_percent",
    "overhead_cost",
    "referral_fee_rate_percent",
    "fulfilment_fee",
    "closing_fee",
    "storage_fee",
    "minimum_margin_percent",
    "target_margin_percent",
)


class EconomicsScopeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organisation_id: ScopeId
    marketplace_id: ScopeId


class CostProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: ScopeId | None = None
    currency_code: CurrencyCode
    selling_price_tax_basis: SellingPriceTaxBasis
    purchase_cost: NonNegativeMoney
    gst_rate_percent: Percentage
    gst_recoverable_percent: Percentage
    freight_cost: NonNegativeMoney
    prep_cost: NonNegativeMoney
    packaging_cost: NonNegativeMoney
    advertising_rate_percent: Percentage
    returns_rate_percent: Percentage
    overhead_cost: NonNegativeMoney
    referral_fee_rate_percent: Percentage | None = None
    fulfilment_fee: OptionalNonNegativeMoney = None
    closing_fee: OptionalNonNegativeMoney = None
    storage_fee: OptionalNonNegativeMoney = None
    fee_source: Annotated[
        str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ] = None
    fee_effective_at: datetime | None = None
    fee_status: FeeInputStatus | None = None
    minimum_margin_percent: MarginPercentage
    target_margin_percent: MarginPercentage
    effective_from: datetime

    @field_validator(*_DECIMAL_FIELDS, mode="before")
    @classmethod
    def reject_binary_float(cls, value: object) -> object:
        if isinstance(value, bool | int | float):
            raise ValueError("financial values must be sent as decimal strings")
        return value

    @field_validator("currency_code", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("effective_from", "fee_effective_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamps must include a UTC offset")
        return value

    @model_validator(mode="after")
    def validate_business_rules(self) -> CostProfileCreate:
        if self.target_margin_percent < self.minimum_margin_percent:
            raise ValueError("target_margin_percent cannot be below minimum_margin_percent")
        fee_values = (
            self.referral_fee_rate_percent,
            self.fulfilment_fee,
            self.closing_fee,
            self.storage_fee,
        )
        metadata = (self.fee_source, self.fee_effective_at, self.fee_status)
        if any(value is not None for value in fee_values) and any(
            value is None for value in metadata
        ):
            raise ValueError(
                "fee_source, fee_effective_at and fee_status are required when fee inputs exist"
            )
        if not any(value is not None for value in fee_values) and any(
            value is not None for value in metadata
        ):
            raise ValueError("fee metadata cannot be supplied without fee inputs")
        return self


class ScopeResponse(BaseModel):
    organisation_id: str
    marketplace_id: str


class ProductReferenceResponse(BaseModel):
    product_id: str
    asin: str
    title: str | None


class ObservedPriceResponse(BaseModel):
    amount: Decimal
    currency_code: str
    evidence_label: Literal["observed"] = "observed"
    source: Literal["keepa_import"] = "keepa_import"
    source_at: datetime
    observed_on: date | None


class CostProfileResponse(BaseModel):
    id: str
    organisation_id: str
    marketplace_id: str
    product_id: str | None
    scope: Literal["product", "marketplace_default"]
    version: int
    supersedes_profile_id: str | None
    currency_code: str
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
    fee_source: str | None
    fee_effective_at: datetime | None
    fee_status: FeeInputStatus | None
    minimum_margin_percent: Decimal
    target_margin_percent: Decimal
    configuration_checksum: str
    effective_from: datetime
    effective_to: datetime | None
    created_at: datetime
    evidence_label: Literal["user_confirmed"] = "user_confirmed"


class EconomicsOutputsResponse(BaseModel):
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


class FeeEvidenceResponse(BaseModel):
    status: FeeInputStatus | None
    source: str | None
    effective_at: datetime | None


class EconomicsCalculationResponse(BaseModel):
    formula_version: str
    configuration_checksum: str
    status: Literal["calculated", "partial"]
    selling_price_tax_basis: SellingPriceTaxBasis | None
    decision_label: Literal["calculated"] = "calculated"
    inputs: dict[str, str | None]
    formulas: dict[str, str]
    outputs: EconomicsOutputsResponse
    reason_codes: list[str]
    fee_evidence: FeeEvidenceResponse


EvidenceLabel = Literal["observed", "calculated", "estimated", "user_confirmed"]


class EconomicsNoticeResponse(BaseModel):
    code: str
    severity: Literal["missing", "warning"]
    message: str
    evidence_label: EvidenceLabel


class CostProfileAuditResponse(BaseModel):
    id: str
    event_type: str
    profile_id: str
    profile_version: int
    occurred_at: datetime


class ProfilesByScopeResponse(BaseModel):
    product: CostProfileResponse | None
    marketplace_default: CostProfileResponse | None


class ProductEconomicsResponse(BaseModel):
    scope: ScopeResponse
    product: ProductReferenceResponse
    observed_price: ObservedPriceResponse | None
    currency_code: str
    profile_source: Literal["product", "marketplace_default"] | None
    active_profile: CostProfileResponse | None
    profiles_by_scope: ProfilesByScopeResponse
    profile_history: list[CostProfileResponse]
    calculation: EconomicsCalculationResponse | None
    notices: list[EconomicsNoticeResponse]
    audit_history: list[CostProfileAuditResponse]
