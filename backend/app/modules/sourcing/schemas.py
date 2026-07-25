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

from app.modules.economics.schemas import (
    CurrencyCode,
    EconomicsScopeQuery,
    ProductReferenceResponse,
    ScopeId,
    ScopeResponse,
)

SupplierName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)]


class SupplierOfferTierCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_quantity: Annotated[int, Field(ge=1, le=10_000_000)]
    unit_cost: Money

    @field_validator("unit_cost", mode="before")
    @classmethod
    def reject_binary_float(cls, value: object) -> object:
        if isinstance(value, bool | int | float):
            raise ValueError("financial values must be sent as decimal strings")
        return value


class SupplierOfferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: ScopeId
    supplier_name: SupplierName
    currency_code: CurrencyCode
    unit_cost: Money
    minimum_order_quantity: Annotated[int, Field(ge=1, le=10_000_000)]
    lead_time_days: Annotated[int, Field(ge=0, le=3_650)]
    quotation_date: date
    valid_until: date | None = None
    notes: Annotated[
        str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)
    ] = None
    price_tiers: Annotated[list[SupplierOfferTierCreate], Field(max_length=25)] = Field(
        default_factory=list
    )

    @field_validator("unit_cost", mode="before")
    @classmethod
    def reject_binary_float(cls, value: object) -> object:
        if isinstance(value, bool | int | float):
            raise ValueError("financial values must be sent as decimal strings")
        return value

    @field_validator("currency_code", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_offer(self) -> SupplierOfferCreate:
        if self.valid_until is not None and self.valid_until < self.quotation_date:
            raise ValueError("valid_until cannot be before quotation_date")
        if self.price_tiers:
            quantities = [tier.minimum_quantity for tier in self.price_tiers]
            if quantities != sorted(set(quantities)):
                raise ValueError("price tiers must use unique increasing minimum quantities")
            if quantities[0] <= self.minimum_order_quantity:
                raise ValueError("additional price tiers must begin above minimum_order_quantity")
        return self


class SupplierOfferListQuery(EconomicsScopeQuery):
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=100)] = 25


class SupplierResponse(BaseModel):
    id: str
    name: str


class SupplierOfferTierResponse(BaseModel):
    minimum_quantity: int
    unit_cost: Decimal


class SupplierOfferResponse(BaseModel):
    id: str
    supplier: SupplierResponse
    product_id: str
    currency_code: str
    unit_cost: Decimal
    minimum_order_quantity: int
    lead_time_days: int
    quotation_date: date
    valid_until: date | None
    notes: str | None
    price_tiers: list[SupplierOfferTierResponse]
    created_at: datetime
    evidence_label: Literal["user_confirmed"] = "user_confirmed"


class PaginationResponse(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_previous: bool
    has_next: bool


class SupplierOfferListResponse(BaseModel):
    scope: ScopeResponse
    product: ProductReferenceResponse
    items: list[SupplierOfferResponse]
    pagination: PaginationResponse
    comparison_dimensions: list[Literal["unit_cost", "minimum_order_quantity", "lead_time_days"]]
    selection_note: str


class TestBuyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_offer_id: ScopeId
    budget_amount: Annotated[Decimal, Field(ge=0, max_digits=16, decimal_places=2)]
    budget_currency_code: CurrencyCode

    @field_validator("budget_amount", mode="before")
    @classmethod
    def reject_binary_float(cls, value: object) -> object:
        if isinstance(value, bool | int | float):
            raise ValueError("financial values must be sent as decimal strings")
        return value

    @field_validator("budget_currency_code", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class TestBuyScenarioResponse(BaseModel):
    scenario: Literal["conservative", "expected", "aggressive"]
    quantity: int
    unit_cost: Decimal | None
    required_investment: Decimal
    expected_sell_through_days: Decimal | None
    status: Literal["recommended", "blocked"]
    reason_codes: list[str]


class TestBuyEvidenceResponse(BaseModel):
    source_snapshot_id: str | None
    monthly_demand_units: int | None
    monthly_demand_label: Literal["estimated"] | None
    monthly_demand_source: Literal["keepa_monthly_sold"] | None
    market_snapshot_at: datetime | None
    market_observed_on: date | None
    data_confidence_score_result_id: str | None
    data_confidence_score: int | None
    data_confidence_label: Literal["calculated"] | None
    data_confidence_formula_version: str | None
    supplier_offer_label: Literal["user_confirmed"] = "user_confirmed"
    budget_label: Literal["user_confirmed"] = "user_confirmed"


class TestBuyNoticeResponse(BaseModel):
    code: str
    severity: Literal["missing", "warning"]
    message: str
    evidence_label: Literal["estimated", "calculated", "recommended", "user_confirmed"]


class TestBuyResponse(BaseModel):
    id: str
    scope: ScopeResponse
    product: ProductReferenceResponse
    supplier_offer_id: str
    budget_amount: Decimal
    budget_currency_code: str
    formula_version: str
    configuration_checksum: str
    inputs: dict[str, str | int | None]
    evidence: TestBuyEvidenceResponse
    scenarios: list[TestBuyScenarioResponse]
    notices: list[TestBuyNoticeResponse]
    outcome: Literal["recommended", "blocked"]
    advisory_only: Literal[True] = True
    decision_label: Literal["recommended"] | None
    created_at: datetime
