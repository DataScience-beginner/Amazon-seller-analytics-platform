from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.modules.strategies.models import Strategy

ScopeId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=36)]
SearchText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
CategoryText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
ScoreValue = Annotated[int, Field(ge=0, le=100)]
NonNegativeInteger = Annotated[int, Field(ge=0)]
NonNegativeDecimal = Annotated[Decimal, Field(ge=0)]


class ProductSortField(StrEnum):
    overall_opportunity = "overall_opportunity"
    data_confidence = "data_confidence"
    price = "price"
    offer_count = "offer_count"
    snapshot_at = "snapshot_at"
    observed_on = "observed_on"
    asin = "asin"
    product_title = "title"
    brand = "brand"
    category = "category"
    strategy = "strategy"


class SortDirection(StrEnum):
    ascending = "asc"
    descending = "desc"


class PortfolioScopeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organisation_id: ScopeId
    marketplace_id: ScopeId


class ProductListQuery(PortfolioScopeQuery):
    search: SearchText | None = None
    strategy: Strategy | None = None
    category: CategoryText | None = None
    min_score: ScoreValue | None = None
    max_score: ScoreValue | None = None
    min_offer_count: NonNegativeInteger | None = None
    max_offer_count: NonNegativeInteger | None = None
    min_price: NonNegativeDecimal | None = None
    max_price: NonNegativeDecimal | None = None
    min_confidence: ScoreValue | None = None
    max_confidence: ScoreValue | None = None
    sort_by: ProductSortField = ProductSortField.overall_opportunity
    sort_direction: SortDirection = SortDirection.descending
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=100)] = 25

    @model_validator(mode="after")
    def validate_ranges(self) -> ProductListQuery:
        for minimum_name, maximum_name in (
            ("min_score", "max_score"),
            ("min_offer_count", "max_offer_count"),
            ("min_price", "max_price"),
            ("min_confidence", "max_confidence"),
        ):
            minimum = getattr(self, minimum_name)
            maximum = getattr(self, maximum_name)
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError(f"{minimum_name} cannot be greater than {maximum_name}")
        return self


class ScopeResponse(BaseModel):
    organisation_id: str
    marketplace_id: str


class ScoreResponse(BaseModel):
    id: str
    name: str
    value: ScoreValue
    formula_version: str
    configuration_checksum: str
    inputs: dict[str, JsonValue] = Field(default_factory=dict)
    reason_codes: list[str] = Field(default_factory=list)
    calculated_at: datetime


EvidenceScalar = str | int | Decimal | bool | None


class RecommendationEvidenceResponse(BaseModel):
    reason_code: str
    polarity: Literal["positive", "negative", "informational"]
    source: str
    signal: str
    observed_value: EvidenceScalar = None
    comparison: str
    threshold_value: EvidenceScalar = None
    threshold_upper_value: EvidenceScalar = None
    statement: str


class RecommendationResponse(BaseModel):
    id: str
    strategy: Strategy
    rules_version: str
    configuration_checksum: str
    confidence: ScoreValue
    evidence: list[RecommendationEvidenceResponse]
    calculated_at: datetime


class MarketMetricsResponse(BaseModel):
    buy_box_price: Decimal | None
    buy_box_price_90d: Decimal | None
    currency_code: str | None
    sales_rank: int | None
    sales_rank_90d: int | None
    sales_rank_drops_90d: int | None
    review_rating: Decimal | None
    review_count: int | None
    new_offer_count: int | None
    total_offer_count: int | None
    buy_box_winner_count_90d: int | None
    buy_box_oos_percentage_90d: Decimal | None
    monthly_sold: int | None
    is_fba: bool | None


class SnapshotResponse(BaseModel):
    id: str
    import_batch_id: str | None
    snapshot_kind: str
    snapshot_at: datetime
    observed_on: date | None
    metrics: MarketMetricsResponse
    scores: list[ScoreResponse] = Field(default_factory=list)
    recommendation: RecommendationResponse | None = None


class ProductSummaryResponse(BaseModel):
    product_id: str
    asin: str
    title: str | None
    brand: str | None
    category: str | None
    subcategory: str | None
    image_url: str | None
    amazon_url: str | None
    latest_snapshot_id: str | None
    latest_snapshot_at: datetime | None
    latest_observed_on: date | None
    buy_box_price: Decimal | None
    currency_code: str | None
    offer_count: int | None
    overall_opportunity_score: ScoreValue | None
    data_confidence_score: ScoreValue | None
    strategy: Strategy | None
    recommendation_confidence: ScoreValue | None
    score_formula_version: str | None
    strategy_rules_version: str | None
    data_quality_codes: list[str] = Field(default_factory=list)


class PaginationResponse(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_previous: bool
    has_next: bool


class AppliedProductQueryResponse(BaseModel):
    search: str | None
    strategy: Strategy | None
    category: str | None
    min_score: int | None
    max_score: int | None
    min_offer_count: int | None
    max_offer_count: int | None
    min_price: Decimal | None
    max_price: Decimal | None
    min_confidence: int | None
    max_confidence: int | None
    sort_by: ProductSortField
    sort_direction: SortDirection


class ProductListResponse(BaseModel):
    scope: ScopeResponse
    items: list[ProductSummaryResponse]
    pagination: PaginationResponse
    query: AppliedProductQueryResponse


class DataNoticeResponse(BaseModel):
    code: str
    severity: Literal["missing", "warning"]
    field: str | None = None
    message: str


class ProductIdentityResponse(BaseModel):
    product_id: str
    asin: str
    title: str | None
    brand: str | None
    category: str | None
    subcategory: str | None
    image_url: str | None
    amazon_url: str | None
    created_at: datetime


class StrategyHistoryResponse(BaseModel):
    snapshot_id: str
    snapshot_at: datetime
    observed_on: date | None
    strategy: Strategy
    confidence: ScoreValue
    rules_version: str
    evidence: list[RecommendationEvidenceResponse]


class ProductDetailResponse(BaseModel):
    scope: ScopeResponse
    product: ProductIdentityResponse
    latest_snapshot: SnapshotResponse | None
    notices: list[DataNoticeResponse]
    snapshot_history: list[SnapshotResponse]
    strategy_history: list[StrategyHistoryResponse]


class LatestImportResponse(BaseModel):
    id: str
    original_filename: str
    status: str
    uploaded_at: datetime
    completed_at: datetime | None
    observed_on: date | None
    period_month: date | None
    revision: int | None
    total_rows: int
    created_rows: int
    matched_rows: int
    skipped_rows: int
    failed_rows: int


class DashboardKpiResponse(BaseModel):
    id: str
    label: str
    value: int | None
    unit: str
    definition: str


class StrategyDistributionResponse(BaseModel):
    strategy: Strategy
    count: int


class DataQualityAlertResponse(BaseModel):
    id: str
    severity: Literal["warning", "error"]
    count: int
    title: str
    description: str


class DashboardRiskResponse(BaseModel):
    product: ProductSummaryResponse
    reason_codes: list[str]


class EmptyDashboardResponse(BaseModel):
    code: Literal["upload_required"] = "upload_required"
    title: str
    message: str
    primary_action: Literal["open_imports"] = "open_imports"


class DashboardResponse(BaseModel):
    scope: ScopeResponse
    tracked_product_count: int
    kpis: list[DashboardKpiResponse]
    latest_import: LatestImportResponse | None
    strategy_distribution: list[StrategyDistributionResponse]
    data_quality_alerts: list[DataQualityAlertResponse]
    top_opportunities: list[ProductSummaryResponse]
    top_risks: list[DashboardRiskResponse]
    empty_state: EmptyDashboardResponse | None


class ProductPath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: ScopeId

    @field_validator("product_id")
    @classmethod
    def reject_path_separators(cls, value: str) -> str:
        if "/" in value or "\\" in value:
            raise ValueError("product_id cannot contain path separators")
        return value
