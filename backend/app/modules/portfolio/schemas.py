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

from app.modules.research.models import (
    BrandClassification,
    ResearchScreenId,
    ResearchStatus,
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
    demand = "demand"
    competition = "competition"
    price_stability = "price_stability"
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


class ResearchRankingSortField(StrEnum):
    research_priority = "research_priority"
    demand = "demand"
    price_stability = "price_stability"
    competition_quality = "competition_quality"
    data_confidence = "data_confidence"
    sales_rank_trend = "sales_rank_trend"
    buy_box_availability = "buy_box_availability"
    price = "price"
    sales_rank = "sales_rank"
    offer_count = "offer_count"
    monthly_demand = "monthly_demand"
    product_title = "title"


class PortfolioScopeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organisation_id: ScopeId
    marketplace_id: ScopeId


class DatasetOverviewQuery(PortfolioScopeQuery):
    category: CategoryText | None = None
    import_batch_id: ScopeId | None = None


class ResearchRankingQuery(PortfolioScopeQuery):
    subcategory: CategoryText
    import_batch_id: ScopeId | None = None
    sort_by: ResearchRankingSortField = ResearchRankingSortField.research_priority
    sort_direction: SortDirection = SortDirection.descending
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=100)] = 25


class ProductListQuery(PortfolioScopeQuery):
    import_batch_id: ScopeId | None = None
    search: SearchText | None = None
    screen: ResearchScreenId = ResearchScreenId.all
    brand_classification: BrandClassification | None = None
    strategy: Strategy | None = None
    category: CategoryText | None = None
    subcategory: CategoryText | None = None
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
    estimated_monthly_bought: int | None
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


class ResearchAssessmentResponse(BaseModel):
    status: ResearchStatus
    brand_classification: BrandClassification
    policy_version: str
    configuration_checksum: str
    reason_codes: list[str] = Field(default_factory=list)
    positive_signals: list[str] = Field(default_factory=list)
    risk_signals: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class ResearchScreenResponse(BaseModel):
    id: ResearchScreenId
    label: str
    description: str


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
    buy_box_price_90d: Decimal | None
    currency_code: str | None
    offer_count: int | None
    sales_rank: int | None
    sales_rank_90d: int | None
    estimated_monthly_bought: int | None
    buy_box_winner_count_90d: int | None
    buy_box_oos_percentage_90d: Decimal | None
    demand_score: ScoreValue | None
    competition_score: ScoreValue | None
    price_stability_score: ScoreValue | None
    overall_opportunity_score: ScoreValue | None
    data_confidence_score: ScoreValue | None
    strategy: Strategy | None
    recommendation_confidence: ScoreValue | None
    score_formula_version: str | None
    strategy_rules_version: str | None
    research: ResearchAssessmentResponse | None
    data_quality_codes: list[str] = Field(default_factory=list)


class PaginationResponse(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_previous: bool
    has_next: bool


class AppliedProductQueryResponse(BaseModel):
    import_batch_id: str | None
    search: str | None
    screen: ResearchScreenId
    brand_classification: BrandClassification | None
    strategy: Strategy | None
    category: str | None
    subcategory: str | None
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
    research_policy_version: str
    research_configuration_checksum: str
    screens: list[ResearchScreenResponse]


class ResearchRankingComponentResponse(BaseModel):
    id: str
    label: str
    weight: int
    score: ScoreValue
    reason_code: str


class ResearchPriorityResponse(BaseModel):
    rank: int
    score: ScoreValue
    formula_version: str
    configuration_checksum: str
    components: list[ResearchRankingComponentResponse]
    warning_codes: list[str]


class ResearchRankingProductResponse(BaseModel):
    product: ProductSummaryResponse
    ranking: ResearchPriorityResponse


class ResearchRankingResponse(BaseModel):
    scope: ScopeResponse
    subcategory: str
    sort_by: ResearchRankingSortField
    sort_direction: SortDirection
    formula_version: str
    configuration_checksum: str
    weights: dict[str, int]
    items: list[ResearchRankingProductResponse]
    pagination: PaginationResponse


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
    research: ResearchAssessmentResponse | None
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


class EvidenceCoverageResponse(BaseModel):
    id: str
    label: str
    populated_products: int
    total_products: int
    coverage_percentage: Decimal


class DatasetDistributionResponse(BaseModel):
    label: str
    product_count: int
    product_percentage: Decimal


class DatasetOverviewResponse(BaseModel):
    readiness: Literal["revenue_ready", "relative_research_only", "insufficient_evidence"]
    readiness_title: str
    readiness_message: str
    product_count: int
    category_count: int
    subcategory_count: int
    brand_count: int
    monthly_demand_coverage_percentage: Decimal
    revenue_coverage_percentage: Decimal
    estimated_monthly_units: int | None
    estimated_monthly_revenue: Decimal | None
    currency_code: str | None
    price_range_currency_code: str | None
    coverage: list[EvidenceCoverageResponse]
    top_categories: list[DatasetDistributionResponse]
    top_subcategories: list[DatasetDistributionResponse]
    top_brands: list[DatasetDistributionResponse]
    price_ranges: list[DatasetDistributionResponse]
    conclusion_codes: list[str]


class DashboardResponse(BaseModel):
    scope: ScopeResponse
    tracked_product_count: int
    kpis: list[DashboardKpiResponse]
    latest_import: LatestImportResponse | None
    strategy_distribution: list[StrategyDistributionResponse]
    data_quality_alerts: list[DataQualityAlertResponse]
    top_opportunities: list[ProductSummaryResponse]
    top_risks: list[DashboardRiskResponse]
    dataset_overview: DatasetOverviewResponse | None
    empty_state: EmptyDashboardResponse | None


class TargetCostAssumptionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gst_rate_percent: Annotated[Decimal, Field(ge=0, lt=100)] = Decimal("18")
    amazon_fee_percent: Annotated[Decimal, Field(ge=0, le=100)] = Decimal("15")
    shipping_percent: Annotated[Decimal, Field(ge=0, le=100)] = Decimal("8")
    advertising_percent: Annotated[Decimal, Field(ge=0, le=100)] = Decimal("5")
    returns_percent: Annotated[Decimal, Field(ge=0, le=100)] = Decimal("3")
    target_profit_percent: Annotated[Decimal, Field(ge=0, le=100)] = Decimal("15")


class CategoryCostEstimateQuery(PortfolioScopeQuery):
    subcategory: CategoryText
    import_batch_id: ScopeId | None = None
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=100)] = 25


class TargetCostProductResponse(BaseModel):
    product_id: str
    asin: str
    title: str | None
    brand: str | None
    image_url: str | None
    amazon_url: str | None
    currency_code: str | None
    selling_price: Decimal | None
    selling_price_source: Literal["buy_box_90d_average", "current_buy_box", "unavailable"]
    maximum_wholesale_cost_ex_gst: Decimal | None
    wholesale_cash_outlay_including_gst: Decimal | None
    target_profit: Decimal | None
    amazon_fee: Decimal | None
    shipping_allowance: Decimal | None
    advertising_allowance: Decimal | None
    returns_allowance: Decimal | None
    feasible: bool


class CategoryCostEstimateResponse(BaseModel):
    scope: ScopeResponse
    subcategory: str
    formula_version: str
    configuration_checksum: str
    assumptions: TargetCostAssumptionsRequest
    items: list[TargetCostProductResponse]
    pagination: PaginationResponse


class ProductPath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: ScopeId

    @field_validator("product_id")
    @classmethod
    def reject_path_separators(cls, value: str) -> str:
        if "/" in value or "\\" in value:
            raise ValueError("product_id cannot contain path separators")
        return value
