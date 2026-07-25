from __future__ import annotations

from collections import Counter
from decimal import Decimal
from math import isfinite
from typing import Literal
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models.domain import (
    ImportBatch,
    ProductSnapshot,
    ScoreResult,
    StrategyRecommendation,
)
from app.modules.portfolio.repository import (
    DashboardCounts,
    DataQualityCounts,
    DatasetEvidenceRow,
    PortfolioRepository,
    PortfolioScope,
    ProductQuerySpec,
    ProductReadRecord,
)
from app.modules.portfolio.schemas import (
    AppliedProductQueryResponse,
    CategoryCostEstimateQuery,
    CategoryCostEstimateResponse,
    DashboardKpiResponse,
    DashboardResponse,
    DashboardRiskResponse,
    DataNoticeResponse,
    DataQualityAlertResponse,
    DatasetDistributionResponse,
    DatasetOverviewQuery,
    DatasetOverviewResponse,
    EmptyDashboardResponse,
    EvidenceCoverageResponse,
    LatestImportResponse,
    MarketMetricsResponse,
    PaginationResponse,
    PortfolioScopeQuery,
    ProductDetailResponse,
    ProductIdentityResponse,
    ProductListQuery,
    ProductListResponse,
    ProductSortField,
    ProductSummaryResponse,
    RecommendationEvidenceResponse,
    RecommendationResponse,
    ResearchAssessmentResponse,
    ResearchPriorityResponse,
    ResearchRankingComponentResponse,
    ResearchRankingProductResponse,
    ResearchRankingQuery,
    ResearchRankingResponse,
    ResearchRankingSortField,
    ResearchScreenResponse,
    ScopeResponse,
    ScoreResponse,
    SnapshotResponse,
    StrategyDistributionResponse,
    StrategyHistoryResponse,
    TargetCostAssumptionsRequest,
    TargetCostProductResponse,
)
from app.modules.profitability.reverse import (
    FORMULA_VERSION as TARGET_COST_FORMULA_VERSION,
)
from app.modules.profitability.reverse import (
    TargetCostAssumptions,
    calculate_target_sourcing_cost,
)
from app.modules.research import (
    ResearchAssessment,
    ResearchPolicy,
    ResearchScreenId,
    ResearchSignals,
    classify_research_product,
    load_default_research_policy,
)
from app.modules.research.ranking import (
    RankingSignals,
    ResearchPriorityRanking,
    load_default_ranking_config,
    rank_research_priority,
)
from app.modules.scoring.config import load_default_scoring_config
from app.modules.scoring.types import ScoreName
from app.modules.strategies.models import Strategy
from app.modules.strategies.policy import load_default_strategy_policy

_SCORE_ORDER = {
    "demand": 0,
    "competition": 1,
    "price_stability": 2,
    "data_confidence": 3,
    "overall_opportunity": 4,
}
_MONTHLY_BOUGHT_SOURCE_HEADER = "Monthly Sales Trends: Bought in past month"
_RESEARCH_RANKING_LIMIT = 10_000

_AMAZON_DOMAINS = {
    "AE": "www.amazon.ae",
    "AU": "www.amazon.com.au",
    "BE": "www.amazon.com.be",
    "BR": "www.amazon.com.br",
    "CA": "www.amazon.ca",
    "DE": "www.amazon.de",
    "EG": "www.amazon.eg",
    "ES": "www.amazon.es",
    "FR": "www.amazon.fr",
    "GB": "www.amazon.co.uk",
    "IN": "www.amazon.in",
    "IT": "www.amazon.it",
    "JP": "www.amazon.co.jp",
    "MX": "www.amazon.com.mx",
    "NL": "www.amazon.nl",
    "PL": "www.amazon.pl",
    "SA": "www.amazon.sa",
    "SE": "www.amazon.se",
    "SG": "www.amazon.sg",
    "TR": "www.amazon.com.tr",
    "UK": "www.amazon.co.uk",
    "US": "www.amazon.com",
}

_MISSING_METRIC_MESSAGES = {
    "buy_box_price": "Current Buy Box price is missing from the latest snapshot.",
    "currency_code": "Currency is missing, so the latest price cannot be interpreted safely.",
    "sales_rank": "Current sales rank is missing from the latest snapshot.",
    "sales_rank_90d": "The 90-day average sales rank is missing.",
    "sales_rank_drops_90d": "The 90-day sales-rank drop count is missing.",
    "monthly_sold": "The monthly-sold estimate is missing.",
    "offer_count": "Current offer count is missing.",
    "review_count": "Review count is missing.",
    "buy_box_winner_count_90d": "The 90-day Buy Box winner count is missing.",
    "buy_box_price_90d": "The 90-day average Buy Box price is missing.",
    "buy_box_oos_percentage_90d": "The 90-day Buy Box out-of-stock percentage is missing.",
}


class PortfolioService:
    """Application service that converts bounded read records into stable API contracts."""

    def __init__(self, session: Session) -> None:
        self._repository = PortfolioRepository(session)
        strategy_policy = load_default_strategy_policy()
        scoring_config = load_default_scoring_config()
        self._research_policy = load_default_research_policy()
        self._confidence_threshold = strategy_policy.low_confidence_threshold
        self._weak_score_threshold = scoring_config.score_bands.weak_below

    def list_products(self, query: ProductListQuery) -> ProductListResponse:
        scope = _scope(query)
        marketplace = self._repository.ensure_scope(scope)
        spec = ProductQuerySpec(
            scope=scope,
            import_batch_id=query.import_batch_id,
            search=query.search,
            research_screen=self._research_policy.screens[query.screen],
            brand_classification=query.brand_classification,
            generic_brand_markers=self._research_policy.generic_brand_markers,
            strategy=query.strategy,
            category=query.category,
            subcategory=query.subcategory,
            min_score=query.min_score,
            max_score=query.max_score,
            min_offer_count=query.min_offer_count,
            max_offer_count=query.max_offer_count,
            min_price=query.min_price,
            max_price=query.max_price,
            min_confidence=query.min_confidence,
            max_confidence=query.max_confidence,
            sort_by=query.sort_by,
            sort_direction=query.sort_direction,
            page=query.page,
            page_size=query.page_size,
            require_confirmed_observation=query.screen is not ResearchScreenId.all,
        )
        result = self._repository.list_products(spec)
        total_pages = (
            (result.total_items + query.page_size - 1) // query.page_size
            if result.total_items
            else 0
        )
        return ProductListResponse(
            scope=_scope_response(scope),
            items=[
                _product_summary(
                    record,
                    marketplace.code,
                    self._confidence_threshold,
                    self._research_policy,
                )
                for record in result.items
            ],
            pagination=PaginationResponse(
                page=query.page,
                page_size=query.page_size,
                total_items=result.total_items,
                total_pages=total_pages,
                has_previous=query.page > 1 and result.total_items > 0,
                has_next=query.page < total_pages,
            ),
            query=AppliedProductQueryResponse(
                import_batch_id=query.import_batch_id,
                search=query.search,
                screen=query.screen,
                brand_classification=query.brand_classification,
                strategy=query.strategy,
                category=query.category,
                subcategory=query.subcategory,
                min_score=query.min_score,
                max_score=query.max_score,
                min_offer_count=query.min_offer_count,
                max_offer_count=query.max_offer_count,
                min_price=query.min_price,
                max_price=query.max_price,
                min_confidence=query.min_confidence,
                max_confidence=query.max_confidence,
                sort_by=query.sort_by,
                sort_direction=query.sort_direction,
            ),
            research_policy_version=self._research_policy.policy_version,
            research_configuration_checksum=self._research_policy.configuration_checksum,
            screens=[
                ResearchScreenResponse(
                    id=screen.id,
                    label=screen.label,
                    description=screen.description,
                )
                for screen in self._research_policy.screens.values()
            ],
        )

    def research_ranking(self, query: ResearchRankingQuery) -> ResearchRankingResponse:
        scope = _scope(query)
        marketplace = self._repository.ensure_scope(scope)
        records = self._repository.list_products_for_ranking(
            ProductQuerySpec(
                scope=scope,
                import_batch_id=query.import_batch_id,
                subcategory=query.subcategory,
                require_confirmed_observation=True,
            ),
            limit=_RESEARCH_RANKING_LIMIT + 1,
        )
        if len(records) > _RESEARCH_RANKING_LIMIT:
            raise ConflictError(
                "research_ranking_scope_too_large",
                "The selected subcategory exceeds the bounded research-ranking limit",
                details={"limit": _RESEARCH_RANKING_LIMIT},
            )
        config = load_default_ranking_config()
        ranked = [
            (
                record,
                rank_research_priority(_ranking_signals(record), config),
            )
            for record in records
        ]
        canonical = sorted(
            ranked,
            key=lambda item: (
                -item[1].score,
                (item[0].product.title or "").casefold(),
                item[0].product.asin,
                item[0].product.id,
            ),
        )
        rank_by_product_id = {
            record.product.id: index for index, (record, _) in enumerate(canonical, start=1)
        }
        if query.sort_by is ResearchRankingSortField.product_title:
            ranked = list(canonical)
            ranked.sort(
                key=lambda item: (item[0].product.title or "").casefold(),
                reverse=query.sort_direction.value == "desc",
            )
        else:
            available = [
                item
                for item in canonical
                if _research_ranking_numeric_sort_value(item, query.sort_by) is not None
            ]
            missing = [
                item
                for item in canonical
                if _research_ranking_numeric_sort_value(item, query.sort_by) is None
            ]
            available.sort(
                key=lambda item: _required_research_ranking_numeric_sort_value(item, query.sort_by),
                reverse=query.sort_direction.value == "desc",
            )
            ranked = available + missing
        total_items = len(ranked)
        total_pages = (total_items + query.page_size - 1) // query.page_size if total_items else 0
        start = (query.page - 1) * query.page_size
        page_items = ranked[start : start + query.page_size]
        return ResearchRankingResponse(
            scope=_scope_response(scope),
            subcategory=query.subcategory,
            sort_by=query.sort_by,
            sort_direction=query.sort_direction,
            formula_version=config.formula_version,
            configuration_checksum=config.configuration_checksum,
            weights=config.weights,
            items=[
                ResearchRankingProductResponse(
                    product=_product_summary(
                        record,
                        marketplace.code,
                        self._confidence_threshold,
                        self._research_policy,
                    ),
                    ranking=_ranking_response(rank_by_product_id[record.product.id], ranking),
                )
                for record, ranking in page_items
            ],
            pagination=PaginationResponse(
                page=query.page,
                page_size=query.page_size,
                total_items=total_items,
                total_pages=total_pages,
                has_previous=query.page > 1 and total_items > 0,
                has_next=query.page < total_pages,
            ),
        )

    def get_product(
        self, scope_query: PortfolioScopeQuery, product_id: str
    ) -> ProductDetailResponse:
        scope = _scope(scope_query)
        marketplace = self._repository.ensure_scope(scope)
        product = self._repository.get_product(scope, product_id)
        latest_snapshot = self._repository.get_latest_snapshot(product)
        history = self._repository.get_snapshot_history(product.id, limit=24)

        snapshot_ids = list(dict.fromkeys(snapshot.id for snapshot in history))
        if latest_snapshot is not None and latest_snapshot.id not in snapshot_ids:
            snapshot_ids.append(latest_snapshot.id)
        scores = self._repository.get_latest_scores(snapshot_ids)
        recommendations = self._repository.get_latest_recommendations(snapshot_ids)

        snapshot_history = [
            _snapshot_response(
                snapshot,
                scores.get(snapshot.id, {}),
                recommendations.get(snapshot.id),
            )
            for snapshot in history
        ]
        latest_response = (
            _snapshot_response(
                latest_snapshot,
                scores.get(latest_snapshot.id, {}),
                recommendations.get(latest_snapshot.id),
            )
            if latest_snapshot is not None
            else None
        )
        strategy_history = [
            StrategyHistoryResponse(
                snapshot_id=snapshot.id,
                snapshot_at=snapshot.snapshot_at,
                observed_on=snapshot.observed_on,
                strategy=recommendation.strategy,
                confidence=recommendation.confidence,
                rules_version=recommendation.rules_version,
                evidence=recommendation.evidence,
            )
            for snapshot in history
            if (recommendation := _recommendation_response(recommendations.get(snapshot.id)))
            is not None
        ]
        latest_scores = scores.get(latest_snapshot.id, {}) if latest_snapshot else {}
        raw_recommendation = recommendations.get(latest_snapshot.id) if latest_snapshot else None
        display_brand = product.brand or (latest_snapshot.brand if latest_snapshot else None)
        return ProductDetailResponse(
            scope=_scope_response(scope),
            product=ProductIdentityResponse(
                product_id=product.id,
                asin=product.asin,
                title=product.title or (latest_snapshot.title if latest_snapshot else None),
                brand=display_brand,
                category=product.category
                or (latest_snapshot.category if latest_snapshot else None),
                subcategory=product.subcategory
                or (latest_snapshot.subcategory if latest_snapshot else None),
                image_url=_safe_http_url(
                    product.image_url or (latest_snapshot.image_url if latest_snapshot else None)
                ),
                amazon_url=_amazon_url(marketplace.code, product.asin),
                created_at=product.created_at,
            ),
            research=(
                _research_assessment_response(
                    classify_research_product(
                        _research_signals_from_scores(
                            latest_snapshot,
                            display_brand,
                            latest_scores,
                        ),
                        self._research_policy,
                    )
                )
                if latest_snapshot is not None and latest_snapshot.observed_on is not None
                else None
            ),
            latest_snapshot=latest_response,
            notices=_data_notices(
                latest_snapshot,
                latest_scores,
                raw_recommendation,
                confidence_threshold=self._confidence_threshold,
            ),
            snapshot_history=snapshot_history,
            strategy_history=strategy_history,
        )

    def dashboard(self, query: PortfolioScopeQuery) -> DashboardResponse:
        scope = _scope(query)
        marketplace = self._repository.ensure_scope(scope)
        counts = self._repository.dashboard_counts(
            scope, confidence_threshold=self._confidence_threshold
        )

        quality_counts = self._repository.data_quality_counts(scope)
        dataset_rows = self._repository.dataset_evidence_rows(scope)
        latest_import = self._repository.latest_import(scope)
        distribution = self._repository.strategy_distribution(scope)
        opportunity_page = self._repository.list_products(
            ProductQuerySpec(
                scope=scope,
                min_confidence=self._confidence_threshold,
                sort_by=ProductSortField.overall_opportunity,
                page=1,
                page_size=5,
                require_confirmed_observation=True,
            )
        )
        risk_records = self._repository.list_risk_products(
            scope,
            confidence_threshold=self._confidence_threshold,
            weak_score_threshold=self._weak_score_threshold,
            limit=5,
        )
        return DashboardResponse(
            scope=_scope_response(scope),
            tracked_product_count=counts.tracked_products,
            kpis=_dashboard_kpis(counts),
            latest_import=_latest_import_response(latest_import),
            strategy_distribution=[
                StrategyDistributionResponse(strategy=strategy, count=distribution.get(strategy, 0))
                for strategy in Strategy
            ],
            data_quality_alerts=_quality_alerts(quality_counts, latest_import),
            top_opportunities=[
                _product_summary(
                    record,
                    marketplace.code,
                    self._confidence_threshold,
                    self._research_policy,
                )
                for record in opportunity_page.items
            ],
            top_risks=[
                DashboardRiskResponse(
                    product=_product_summary(
                        record,
                        marketplace.code,
                        self._confidence_threshold,
                        self._research_policy,
                    ),
                    reason_codes=_risk_reason_codes(
                        record,
                        confidence_threshold=self._confidence_threshold,
                        weak_score_threshold=self._weak_score_threshold,
                    ),
                )
                for record in risk_records
            ],
            dataset_overview=_dataset_overview(dataset_rows),
            empty_state=(
                EmptyDashboardResponse(
                    title="Import your first product file",
                    message=(
                        "Upload a Keepa Excel export to create immutable snapshots, scores, "
                        "and portfolio recommendations."
                    ),
                )
                if counts.tracked_products == 0
                else None
            ),
        )

    def dataset_overview(self, query: DatasetOverviewQuery) -> DatasetOverviewResponse | None:
        scope = _scope(query)
        self._repository.ensure_scope(scope)
        return _dataset_overview(
            self._repository.dataset_evidence_rows(
                scope,
                category=query.category,
                import_batch_id=query.import_batch_id,
            )
        )

    def category_cost_estimate(
        self,
        query: CategoryCostEstimateQuery,
        request: TargetCostAssumptionsRequest,
    ) -> CategoryCostEstimateResponse:
        scope = _scope(query)
        marketplace = self._repository.ensure_scope(scope)
        assumptions = TargetCostAssumptions(
            gst_rate_percent=request.gst_rate_percent,
            amazon_fee_percent=request.amazon_fee_percent,
            shipping_percent=request.shipping_percent,
            advertising_percent=request.advertising_percent,
            returns_percent=request.returns_percent,
            target_profit_percent=request.target_profit_percent,
        )
        page = self._repository.list_products(
            ProductQuerySpec(
                scope=scope,
                import_batch_id=query.import_batch_id,
                subcategory=query.subcategory,
                sort_by=ProductSortField.overall_opportunity,
                page=query.page,
                page_size=query.page_size,
                require_confirmed_observation=True,
            )
        )
        total_pages = (
            (page.total_items + query.page_size - 1) // query.page_size if page.total_items else 0
        )
        items: list[TargetCostProductResponse] = []
        for record in page.items:
            snapshot = record.snapshot
            price = (
                snapshot.buy_box_price_90d
                if snapshot is not None and snapshot.buy_box_price_90d is not None
                else snapshot.buy_box_price
                if snapshot is not None
                else None
            )
            source: Literal["buy_box_90d_average", "current_buy_box", "unavailable"] = "unavailable"
            if snapshot is not None and snapshot.buy_box_price_90d is not None:
                source = "buy_box_90d_average"
            elif price is not None:
                source = "current_buy_box"
            result = (
                calculate_target_sourcing_cost(price, assumptions) if price is not None else None
            )
            items.append(
                TargetCostProductResponse(
                    product_id=record.product.id,
                    asin=record.product.asin,
                    title=record.product.title,
                    brand=record.product.brand,
                    image_url=_safe_http_url(
                        record.product.image_url
                        or (snapshot.image_url if snapshot is not None else None)
                    ),
                    amazon_url=_amazon_url(marketplace.code, record.product.asin),
                    currency_code=snapshot.currency_code if snapshot is not None else None,
                    selling_price=price,
                    selling_price_source=source,
                    maximum_wholesale_cost_ex_gst=(
                        result.maximum_wholesale_cost_ex_gst if result else None
                    ),
                    wholesale_cash_outlay_including_gst=(
                        result.wholesale_cash_outlay_including_gst if result else None
                    ),
                    target_profit=result.target_profit if result else None,
                    amazon_fee=result.amazon_fee if result else None,
                    shipping_allowance=result.shipping_allowance if result else None,
                    advertising_allowance=result.advertising_allowance if result else None,
                    returns_allowance=result.returns_allowance if result else None,
                    feasible=result.feasible if result else False,
                )
            )
        return CategoryCostEstimateResponse(
            scope=_scope_response(scope),
            subcategory=query.subcategory,
            formula_version=TARGET_COST_FORMULA_VERSION,
            configuration_checksum=assumptions.configuration_checksum,
            assumptions=request,
            items=items,
            pagination=PaginationResponse(
                page=query.page,
                page_size=query.page_size,
                total_items=page.total_items,
                total_pages=total_pages,
                has_previous=query.page > 1 and page.total_items > 0,
                has_next=query.page < total_pages,
            ),
        )


def _dataset_overview(rows: list[DatasetEvidenceRow]) -> DatasetOverviewResponse | None:
    if not rows:
        return None
    if len(rows) > 10_000:
        raise ValueError("dataset overview exceeds the supported 10,000-product bound")

    total = len(rows)
    categories: Counter[str] = Counter()
    subcategories: Counter[str] = Counter()
    brands: Counter[str] = Counter()
    coverage_counts: Counter[str] = Counter()
    estimated_units = 0
    known_revenue = Decimal("0")
    revenue_products = 0
    currencies: set[str] = set()
    price_currencies: set[str] = set()
    price_ranges: Counter[str] = Counter()

    for row in rows:
        snapshot = row.snapshot
        categories[(row.category or "Unknown category").strip() or "Unknown category"] += 1
        subcategories[
            (row.subcategory or "Unknown subcategory").strip() or "Unknown subcategory"
        ] += 1
        brands[(row.brand or "Unknown brand").strip() or "Unknown brand"] += 1
        values = {
            "buy_box_price": snapshot.buy_box_price,
            "sales_rank": snapshot.sales_rank,
            "sales_rank_90d": snapshot.sales_rank_90d,
            "offer_count": snapshot.new_offer_count
            if snapshot.new_offer_count is not None
            else snapshot.total_offer_count,
            "review_count": snapshot.review_count,
            "brand": row.brand,
        }
        for key, value in values.items():
            if value is not None and (not isinstance(value, str) or value.strip()):
                coverage_counts[key] += 1
        monthly_bought = _estimated_monthly_bought(snapshot)
        if snapshot.buy_box_price is None:
            price_ranges["Price unavailable"] += 1
        else:
            price_ranges[_price_range_label(snapshot.buy_box_price)] += 1
            if snapshot.currency_code:
                price_currencies.add(snapshot.currency_code)
        if monthly_bought is not None:
            coverage_counts["monthly_demand"] += 1
            estimated_units += monthly_bought
            if snapshot.buy_box_price is not None:
                revenue_products += 1
                known_revenue += snapshot.buy_box_price * monthly_bought
                if snapshot.currency_code:
                    currencies.add(snapshot.currency_code)

    demand_coverage = _percentage(coverage_counts["monthly_demand"], total)
    revenue_coverage = _percentage(revenue_products, total)
    relative_evidence_ready = all(
        _percentage(coverage_counts[key], total) >= Decimal("80")
        for key in ("buy_box_price", "sales_rank", "sales_rank_90d", "offer_count")
    )
    revenue_ready = revenue_coverage >= Decimal("70") and len(currencies) == 1
    readiness: Literal["revenue_ready", "relative_research_only", "insufficient_evidence"]
    if revenue_ready:
        readiness = "revenue_ready"
        title = "Ready for estimated revenue analysis"
        message = (
            "Monthly-demand and price evidence cover at least 70% of products. "
            "Revenue remains a Keepa-derived marketplace estimate."
        )
    elif relative_evidence_ready:
        readiness = "relative_research_only"
        title = "Ready for relative product research"
        message = (
            "Rank, price and seller evidence are usable, but monthly-demand coverage is too low "
            "for a responsible revenue chart."
        )
    else:
        readiness = "insufficient_evidence"
        title = "Dataset evidence is incomplete"
        message = "Key market fields do not cover enough products for reliable comparisons."

    labels = {
        "buy_box_price": "Current Buy Box price",
        "sales_rank": "Current sales rank",
        "sales_rank_90d": "90-day average sales rank",
        "offer_count": "Seller offers",
        "review_count": "Review count",
        "brand": "Brand",
        "monthly_demand": "Bought in past month",
    }
    conclusions = ["revenue_blocked_low_monthly_demand"] if not revenue_ready else []
    if brands and brands.most_common(1)[0][1] / total >= 0.1:
        conclusions.append("brand_concentration_requires_review")
    if categories and len(categories) == 1:
        conclusions.append("single_root_category_dataset")

    return DatasetOverviewResponse(
        readiness=readiness,
        readiness_title=title,
        readiness_message=message,
        product_count=total,
        category_count=len(categories),
        subcategory_count=len(subcategories),
        brand_count=len(brands),
        monthly_demand_coverage_percentage=demand_coverage,
        revenue_coverage_percentage=revenue_coverage,
        estimated_monthly_units=estimated_units if revenue_ready else None,
        estimated_monthly_revenue=known_revenue if revenue_ready else None,
        currency_code=next(iter(currencies)) if revenue_ready else None,
        price_range_currency_code=(
            next(iter(price_currencies)) if len(price_currencies) == 1 else None
        ),
        coverage=[
            EvidenceCoverageResponse(
                id=key,
                label=label,
                populated_products=coverage_counts[key],
                total_products=total,
                coverage_percentage=_percentage(coverage_counts[key], total),
            )
            for key, label in labels.items()
        ],
        top_categories=_distribution(categories, total),
        top_subcategories=_distribution(subcategories, total),
        top_brands=_distribution(brands, total),
        price_ranges=_ordered_price_distribution(price_ranges, total),
        conclusion_codes=conclusions,
    )


def _percentage(value: int, total: int) -> Decimal:
    if total == 0:
        return Decimal("0")
    return (Decimal(value) * Decimal("100") / Decimal(total)).quantize(Decimal("0.1"))


def _distribution(values: Counter[str], total: int) -> list[DatasetDistributionResponse]:
    return [
        DatasetDistributionResponse(
            label=label,
            product_count=count,
            product_percentage=_percentage(count, total),
        )
        for label, count in values.most_common(10)
    ]


def _price_range_label(price: Decimal) -> str:
    if price < Decimal("500"):
        return "Under 500"
    if price < Decimal("1000"):
        return "500–999"
    if price < Decimal("2000"):
        return "1,000–1,999"
    if price < Decimal("5000"):
        return "2,000–4,999"
    return "5,000 and above"


def _ordered_price_distribution(
    values: Counter[str], total: int
) -> list[DatasetDistributionResponse]:
    order = (
        "Under 500",
        "500–999",
        "1,000–1,999",
        "2,000–4,999",
        "5,000 and above",
        "Price unavailable",
    )
    return [
        DatasetDistributionResponse(
            label=label,
            product_count=values[label],
            product_percentage=_percentage(values[label], total),
        )
        for label in order
        if values[label] > 0
    ]


def _scope(query: PortfolioScopeQuery) -> PortfolioScope:
    return PortfolioScope(
        organisation_id=query.organisation_id,
        marketplace_id=query.marketplace_id,
    )


def _scope_response(scope: PortfolioScope) -> ScopeResponse:
    return ScopeResponse(
        organisation_id=scope.organisation_id,
        marketplace_id=scope.marketplace_id,
    )


def _safe_http_url(value: str | None) -> str | None:
    if not value:
        return None
    for candidate in (part.strip() for part in value.split(";")):
        parsed = urlsplit(candidate)
        if parsed.scheme in {"http", "https"} and parsed.netloc and not parsed.username:
            return candidate
    return None


def _amazon_url(marketplace_code: str, asin: str) -> str | None:
    normalized_code = marketplace_code.strip().upper()
    domain = _AMAZON_DOMAINS.get(normalized_code)
    normalized_asin = asin.strip().upper()
    if domain is None or len(normalized_asin) != 10 or not normalized_asin.isalnum():
        return None
    return f"https://{domain}/dp/{normalized_asin}"


def _ranking_signals(record: ProductReadRecord) -> RankingSignals:
    snapshot = record.snapshot
    return RankingSignals(
        demand_score=record.demand_score.score_value if record.demand_score else None,
        price_stability_score=(
            record.price_stability_score.score_value if record.price_stability_score else None
        ),
        competition_score=(
            record.competition_score.score_value if record.competition_score else None
        ),
        data_confidence_score=(
            record.confidence_score.score_value if record.confidence_score else None
        ),
        sales_rank=snapshot.sales_rank if snapshot else None,
        sales_rank_90d=snapshot.sales_rank_90d if snapshot else None,
        offer_count=record.offer_count,
        buy_box_price_available=bool(snapshot and snapshot.buy_box_price is not None),
        buy_box_oos_percentage_90d=(snapshot.buy_box_oos_percentage_90d if snapshot else None),
    )


def _ranking_component_score(ranking: ResearchPriorityRanking, component_id: str) -> int:
    return next(component.score for component in ranking.components if component.id == component_id)


def _research_ranking_numeric_sort_value(
    item: tuple[ProductReadRecord, ResearchPriorityRanking],
    sort_by: ResearchRankingSortField,
) -> Decimal | None:
    record, ranking = item
    snapshot = record.snapshot
    numeric: dict[ResearchRankingSortField, int | Decimal | None] = {
        ResearchRankingSortField.research_priority: ranking.score,
        ResearchRankingSortField.demand: _ranking_component_score(ranking, "demand"),
        ResearchRankingSortField.price_stability: _ranking_component_score(
            ranking, "price_stability"
        ),
        ResearchRankingSortField.competition_quality: _ranking_component_score(
            ranking, "competition_quality"
        ),
        ResearchRankingSortField.data_confidence: _ranking_component_score(
            ranking, "data_confidence"
        ),
        ResearchRankingSortField.sales_rank_trend: _ranking_component_score(
            ranking, "sales_rank_trend"
        ),
        ResearchRankingSortField.buy_box_availability: _ranking_component_score(
            ranking, "buy_box_availability"
        ),
        ResearchRankingSortField.price: snapshot.buy_box_price if snapshot else None,
        ResearchRankingSortField.offer_count: record.offer_count,
        ResearchRankingSortField.monthly_demand: (
            _estimated_monthly_bought(snapshot) if snapshot else None
        ),
        ResearchRankingSortField.product_title: None,
    }
    value = numeric[sort_by]
    return Decimal(value) if isinstance(value, int) else value


def _required_research_ranking_numeric_sort_value(
    item: tuple[ProductReadRecord, ResearchPriorityRanking],
    sort_by: ResearchRankingSortField,
) -> Decimal:
    value = _research_ranking_numeric_sort_value(item, sort_by)
    if value is None:
        raise ValueError("A missing ranking sort value entered the available partition")
    return value


def _ranking_response(rank: int, ranking: ResearchPriorityRanking) -> ResearchPriorityResponse:
    return ResearchPriorityResponse(
        rank=rank,
        score=ranking.score,
        formula_version=ranking.formula_version,
        configuration_checksum=ranking.configuration_checksum,
        components=[
            ResearchRankingComponentResponse(
                id=component.id,
                label=component.label,
                weight=component.weight,
                score=component.score,
                reason_code=component.reason_code,
            )
            for component in ranking.components
        ],
        warning_codes=list(ranking.warning_codes),
    )


def _evidence_scalar(value: object) -> str | int | Decimal | bool | None:
    if value is None or isinstance(value, str | bool | int | Decimal):
        return value
    if isinstance(value, float) and isfinite(value):
        return Decimal(str(value))
    return None


def _recommendation_evidence(value: object) -> list[RecommendationEvidenceResponse]:
    if not isinstance(value, list):
        return []
    evidence: list[RecommendationEvidenceResponse] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        reason_code = item.get("reason_code")
        polarity = item.get("polarity")
        source = item.get("source")
        signal = item.get("signal")
        comparison = item.get("comparison")
        statement = item.get("statement")
        if not all(
            isinstance(field, str) and field
            for field in (reason_code, polarity, source, signal, comparison, statement)
        ) or polarity not in {"positive", "negative", "informational"}:
            continue
        evidence.append(
            RecommendationEvidenceResponse.model_validate(
                {
                    "reason_code": reason_code,
                    "polarity": polarity,
                    "source": source,
                    "signal": signal,
                    "observed_value": _evidence_scalar(item.get("observed_value")),
                    "comparison": comparison,
                    "threshold_value": _evidence_scalar(item.get("threshold_value")),
                    "threshold_upper_value": _evidence_scalar(item.get("threshold_upper_value")),
                    "statement": statement,
                }
            )
        )
    return evidence


def _recommendation_response(
    recommendation: StrategyRecommendation | None,
) -> RecommendationResponse | None:
    if recommendation is None:
        return None
    evidence = _recommendation_evidence(recommendation.evidence)
    if not evidence:
        return None
    try:
        strategy = Strategy(recommendation.strategy)
    except ValueError:
        return None
    return RecommendationResponse(
        id=recommendation.id,
        strategy=strategy,
        rules_version=recommendation.rules_version,
        configuration_checksum=recommendation.configuration_checksum,
        confidence=recommendation.confidence_score,
        evidence=evidence,
        calculated_at=recommendation.created_at,
    )


def _score_response(score: ScoreResult) -> ScoreResponse:
    inputs = score.inputs if isinstance(score.inputs, dict) else {}
    reason_codes = [str(value) for value in score.reason_codes if isinstance(value, str)]
    return ScoreResponse(
        id=score.id,
        name=score.score_name,
        value=score.score_value,
        formula_version=score.formula_version,
        configuration_checksum=score.configuration_checksum,
        inputs=inputs,
        reason_codes=reason_codes,
        calculated_at=score.created_at,
    )


def _ordered_scores(scores: dict[str, ScoreResult]) -> list[ScoreResponse]:
    return [
        _score_response(score)
        for score in sorted(
            scores.values(),
            key=lambda item: (
                _SCORE_ORDER.get(item.score_name, len(_SCORE_ORDER)),
                item.score_name,
            ),
        )
    ]


def _source_value(snapshot: ProductSnapshot, header: str) -> object | None:
    if not isinstance(snapshot.source_payload, list):
        return None
    for item in snapshot.source_payload:
        if isinstance(item, dict) and item.get("header") == header:
            return item.get("value")
    return None


def _non_negative_integer(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value).replace(",", "").strip())
    except Exception:
        return None
    if not parsed.is_finite() or parsed < 0 or parsed != parsed.to_integral_value():
        return None
    return int(parsed)


def _estimated_monthly_bought(snapshot: ProductSnapshot) -> int | None:
    return _non_negative_integer(_source_value(snapshot, _MONTHLY_BOUGHT_SOURCE_HEADER))


def _market_metrics(snapshot: ProductSnapshot) -> MarketMetricsResponse:
    return MarketMetricsResponse(
        buy_box_price=snapshot.buy_box_price,
        buy_box_price_90d=snapshot.buy_box_price_90d,
        currency_code=snapshot.currency_code,
        sales_rank=snapshot.sales_rank,
        sales_rank_90d=snapshot.sales_rank_90d,
        sales_rank_drops_90d=snapshot.sales_rank_drops_90d,
        review_rating=snapshot.review_rating,
        review_count=snapshot.review_count,
        new_offer_count=snapshot.new_offer_count,
        total_offer_count=snapshot.total_offer_count,
        buy_box_winner_count_90d=snapshot.buy_box_winner_count_90d,
        buy_box_oos_percentage_90d=snapshot.buy_box_oos_percentage_90d,
        monthly_sold=snapshot.monthly_sold,
        estimated_monthly_bought=_estimated_monthly_bought(snapshot),
        is_fba=snapshot.is_fba,
    )


def _snapshot_response(
    snapshot: ProductSnapshot,
    scores: dict[str, ScoreResult],
    recommendation: StrategyRecommendation | None,
) -> SnapshotResponse:
    return SnapshotResponse(
        id=snapshot.id,
        import_batch_id=snapshot.import_batch_id,
        snapshot_kind=snapshot.snapshot_kind.value,
        snapshot_at=snapshot.snapshot_at,
        observed_on=snapshot.observed_on,
        metrics=_market_metrics(snapshot),
        scores=_ordered_scores(scores),
        recommendation=_recommendation_response(recommendation),
    )


def _product_summary(
    record: ProductReadRecord,
    marketplace_code: str,
    confidence_threshold: int,
    research_policy: ResearchPolicy,
) -> ProductSummaryResponse:
    product = record.product
    snapshot = record.snapshot
    recommendation = (
        _recommendation_response(record.recommendation)
        if snapshot is not None and snapshot.observed_on is not None
        else None
    )
    codes: list[str] = []
    if snapshot is None:
        codes.append("snapshot_missing")
    if snapshot is not None and snapshot.buy_box_price is None:
        codes.append("buy_box_price_missing")
    if snapshot is not None and snapshot.observed_on is None:
        codes.append("observation_date_unconfirmed")
    if record.overall_score is None:
        codes.append("overall_opportunity_score_missing")
    if record.confidence_score is None:
        codes.append("data_confidence_score_missing")
    elif record.confidence_score.score_value < confidence_threshold:
        codes.append("low_data_confidence")
    if recommendation is None:
        codes.append(
            "recommendation_evidence_missing"
            if record.recommendation is not None
            else "recommendation_missing"
        )
    research = (
        _research_assessment_response(
            classify_research_product(
                _research_signals_from_record(
                    record, product.brand or (snapshot.brand if snapshot else None)
                ),
                research_policy,
            )
        )
        if snapshot is not None and snapshot.observed_on is not None
        else None
    )
    return ProductSummaryResponse(
        product_id=product.id,
        asin=product.asin,
        title=product.title or (snapshot.title if snapshot else None),
        brand=product.brand or (snapshot.brand if snapshot else None),
        category=product.category or (snapshot.category if snapshot else None),
        subcategory=product.subcategory or (snapshot.subcategory if snapshot else None),
        image_url=_safe_http_url(product.image_url or (snapshot.image_url if snapshot else None)),
        amazon_url=_amazon_url(marketplace_code, product.asin),
        latest_snapshot_id=snapshot.id if snapshot else None,
        latest_snapshot_at=snapshot.snapshot_at if snapshot else None,
        latest_observed_on=snapshot.observed_on if snapshot else None,
        buy_box_price=snapshot.buy_box_price if snapshot else None,
        buy_box_price_90d=snapshot.buy_box_price_90d if snapshot else None,
        currency_code=snapshot.currency_code if snapshot else None,
        offer_count=record.offer_count,
        sales_rank=snapshot.sales_rank if snapshot else None,
        sales_rank_90d=snapshot.sales_rank_90d if snapshot else None,
        estimated_monthly_bought=_estimated_monthly_bought(snapshot) if snapshot else None,
        buy_box_winner_count_90d=snapshot.buy_box_winner_count_90d if snapshot else None,
        buy_box_oos_percentage_90d=(snapshot.buy_box_oos_percentage_90d if snapshot else None),
        demand_score=record.demand_score.score_value if record.demand_score else None,
        competition_score=(
            record.competition_score.score_value if record.competition_score else None
        ),
        price_stability_score=(
            record.price_stability_score.score_value if record.price_stability_score else None
        ),
        overall_opportunity_score=(
            record.overall_score.score_value if record.overall_score else None
        ),
        data_confidence_score=(
            record.confidence_score.score_value if record.confidence_score else None
        ),
        strategy=recommendation.strategy if recommendation else None,
        recommendation_confidence=recommendation.confidence if recommendation else None,
        score_formula_version=(
            record.overall_score.formula_version if record.overall_score else None
        ),
        strategy_rules_version=recommendation.rules_version if recommendation else None,
        research=research,
        data_quality_codes=codes,
    )


def _score_value(scores: dict[str, ScoreResult], name: str) -> int | None:
    score = scores.get(name)
    return score.score_value if score is not None else None


def _research_signals_from_scores(
    snapshot: ProductSnapshot,
    brand: str | None,
    scores: dict[str, ScoreResult],
) -> ResearchSignals:
    return ResearchSignals(
        demand_score=_score_value(scores, "demand"),
        competition_score=_score_value(scores, "competition"),
        price_stability_score=_score_value(scores, "price_stability"),
        data_confidence_score=_score_value(scores, "data_confidence"),
        overall_opportunity_score=_score_value(scores, "overall_opportunity"),
        current_offer_count=(
            snapshot.new_offer_count
            if snapshot.new_offer_count is not None
            else snapshot.total_offer_count
        ),
        buy_box_price=snapshot.buy_box_price,
        buy_box_price_90d=snapshot.buy_box_price_90d,
        estimated_monthly_bought=_estimated_monthly_bought(snapshot),
        brand=brand,
    )


def _research_signals_from_record(
    record: ProductReadRecord,
    brand: str | None,
) -> ResearchSignals:
    snapshot = record.snapshot
    return ResearchSignals(
        demand_score=record.demand_score.score_value if record.demand_score else None,
        competition_score=(
            record.competition_score.score_value if record.competition_score else None
        ),
        price_stability_score=(
            record.price_stability_score.score_value if record.price_stability_score else None
        ),
        data_confidence_score=(
            record.confidence_score.score_value if record.confidence_score else None
        ),
        overall_opportunity_score=(
            record.overall_score.score_value if record.overall_score else None
        ),
        current_offer_count=record.offer_count,
        buy_box_price=snapshot.buy_box_price if snapshot else None,
        buy_box_price_90d=snapshot.buy_box_price_90d if snapshot else None,
        estimated_monthly_bought=_estimated_monthly_bought(snapshot) if snapshot else None,
        brand=brand,
    )


def _research_assessment_response(
    assessment: ResearchAssessment,
) -> ResearchAssessmentResponse:
    return ResearchAssessmentResponse(
        status=assessment.status,
        brand_classification=assessment.brand_classification,
        policy_version=assessment.policy_version,
        configuration_checksum=assessment.configuration_checksum,
        reason_codes=list(assessment.reason_codes),
        positive_signals=list(assessment.positive_signals),
        risk_signals=list(assessment.risk_signals),
        missing_evidence=list(assessment.missing_evidence),
    )


def _data_notices(
    snapshot: ProductSnapshot | None,
    scores: dict[str, ScoreResult],
    recommendation: StrategyRecommendation | None,
    *,
    confidence_threshold: int,
) -> list[DataNoticeResponse]:
    if snapshot is None:
        return [
            DataNoticeResponse(
                code="snapshot_missing",
                severity="missing",
                field="latest_snapshot",
                message="No immutable market snapshot is available for this product.",
            )
        ]

    values: dict[str, object] = {
        "buy_box_price": snapshot.buy_box_price,
        "currency_code": snapshot.currency_code,
        "sales_rank": snapshot.sales_rank,
        "sales_rank_90d": snapshot.sales_rank_90d,
        "sales_rank_drops_90d": snapshot.sales_rank_drops_90d,
        "monthly_sold": snapshot.monthly_sold,
        "offer_count": (
            snapshot.new_offer_count
            if snapshot.new_offer_count is not None
            else snapshot.total_offer_count
        ),
        "review_count": snapshot.review_count,
        "buy_box_winner_count_90d": snapshot.buy_box_winner_count_90d,
        "buy_box_price_90d": snapshot.buy_box_price_90d,
        "buy_box_oos_percentage_90d": snapshot.buy_box_oos_percentage_90d,
    }
    notices = [
        DataNoticeResponse(
            code="market_metric_missing",
            severity="missing",
            field=field,
            message=_MISSING_METRIC_MESSAGES[field],
        )
        for field, value in values.items()
        if value is None
    ]
    if snapshot.observed_on is None:
        notices.append(
            DataNoticeResponse(
                code="observation_date_unconfirmed",
                severity="missing",
                field="latest_snapshot.observed_on",
                message=(
                    "This legacy snapshot has no user-confirmed market observation date; "
                    "its recommendation is historical evidence, not a current decision."
                ),
            )
        )
    for score_name in ScoreName:
        if score_name.value not in scores:
            notices.append(
                DataNoticeResponse(
                    code="score_missing",
                    severity="missing",
                    field=score_name.value,
                    message=f"The {score_name.value.replace('_', ' ')} score is unavailable.",
                )
            )
    confidence_score = scores.get(ScoreName.data_confidence.value)
    if confidence_score and confidence_score.score_value < confidence_threshold:
        notices.append(
            DataNoticeResponse(
                code="low_data_confidence",
                severity="warning",
                field=ScoreName.data_confidence.value,
                message=(
                    "Data confidence is below the strategy policy threshold; aggressive "
                    "recommendations are blocked."
                ),
            )
        )
    if recommendation is None:
        notices.append(
            DataNoticeResponse(
                code="recommendation_missing",
                severity="missing",
                field="recommendation",
                message="No strategy recommendation is available for the latest snapshot.",
            )
        )
    elif _recommendation_response(recommendation) is None:
        notices.append(
            DataNoticeResponse(
                code="recommendation_evidence_missing",
                severity="warning",
                field="recommendation.evidence",
                message=(
                    "The stored recommendation is hidden because valid supporting evidence "
                    "is unavailable."
                ),
            )
        )
    return notices


def _latest_import_response(import_batch: ImportBatch | None) -> LatestImportResponse | None:
    if import_batch is None:
        return None
    return LatestImportResponse(
        id=import_batch.id,
        original_filename=import_batch.original_filename,
        status=import_batch.status.value,
        uploaded_at=import_batch.uploaded_at,
        completed_at=import_batch.completed_at,
        observed_on=import_batch.observed_on,
        period_month=import_batch.period_month,
        revision=import_batch.dataset_revision,
        total_rows=import_batch.total_rows,
        created_rows=import_batch.created_rows,
        matched_rows=import_batch.matched_rows,
        skipped_rows=import_batch.skipped_rows,
        failed_rows=import_batch.failed_rows,
    )


def _dashboard_kpis(counts: DashboardCounts) -> list[DashboardKpiResponse]:
    return [
        DashboardKpiResponse(
            id="tracked_products",
            label="Tracked products",
            value=counts.tracked_products,
            unit="products",
            definition=("Distinct products owned by the selected organisation and marketplace."),
        ),
        DashboardKpiResponse(
            id="classified_products",
            label="Classified products",
            value=counts.classified_products,
            unit="products",
            definition="Products whose latest snapshot has a stored strategy recommendation.",
        ),
        DashboardKpiResponse(
            id="average_opportunity_score",
            label="Average opportunity",
            value=counts.average_opportunity_score,
            unit="score_0_100",
            definition=(
                "Arithmetic mean of available latest overall-opportunity scores, rounded to "
                "the nearest whole score. Products without a score are excluded."
            ),
        ),
        DashboardKpiResponse(
            id="low_confidence_products",
            label="Low-confidence products",
            value=counts.low_confidence_products,
            unit="products",
            definition=(
                "Products with a latest data-confidence score below the active strategy-policy "
                "threshold."
            ),
        ),
    ]


def _quality_alerts(
    counts: DataQualityCounts, latest_import: ImportBatch | None
) -> list[DataQualityAlertResponse]:
    candidates = [
        DataQualityAlertResponse(
            id="products_without_snapshot",
            severity="error",
            count=counts.products_without_snapshot,
            title="Products without snapshots",
            description="Tracked products do not have a valid latest immutable snapshot.",
        ),
        DataQualityAlertResponse(
            id="observation_date_unconfirmed",
            severity="error",
            count=counts.unconfirmed_observation_date,
            title="Unconfirmed observation date",
            description=(
                "Legacy snapshots without a confirmed market date are excluded from current "
                "portfolio decisions."
            ),
        ),
        DataQualityAlertResponse(
            id="missing_buy_box_price",
            severity="warning",
            count=counts.missing_buy_box_price,
            title="Missing Buy Box price",
            description="Latest snapshots are missing the current Buy Box price.",
        ),
        DataQualityAlertResponse(
            id="missing_opportunity_score",
            severity="warning",
            count=counts.missing_opportunity_score,
            title="Missing opportunity score",
            description="Latest snapshots have not produced an overall-opportunity score.",
        ),
        DataQualityAlertResponse(
            id="missing_recommendation",
            severity="warning",
            count=counts.missing_recommendation,
            title="Missing recommendation",
            description="Latest snapshots have not produced a strategy recommendation.",
        ),
    ]
    if latest_import is not None:
        candidates.append(
            DataQualityAlertResponse(
                id="latest_import_failed_rows",
                severity="error",
                count=latest_import.failed_rows,
                title="Failed rows in latest import",
                description="Rows in the latest import could not be converted into snapshots.",
            )
        )
    return [alert for alert in candidates if alert.count > 0]


def _risk_reason_codes(
    record: ProductReadRecord, *, confidence_threshold: int, weak_score_threshold: int
) -> list[str]:
    reasons: list[str] = []
    recommendation = _recommendation_response(record.recommendation)
    if recommendation and recommendation.strategy is Strategy.CLEARANCE_WATCH:
        reasons.append("clearance_watch_strategy")
    if recommendation and recommendation.strategy is Strategy.AVOID:
        reasons.append("avoid_strategy")
    if record.confidence_score and record.confidence_score.score_value < confidence_threshold:
        reasons.append("low_data_confidence")
    if record.overall_score and record.overall_score.score_value < weak_score_threshold:
        reasons.append("weak_overall_opportunity")
    return reasons
