from __future__ import annotations

from decimal import Decimal
from math import isfinite
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.models.domain import (
    ImportBatch,
    ProductSnapshot,
    ScoreResult,
    StrategyRecommendation,
)
from app.modules.portfolio.repository import (
    DashboardCounts,
    DataQualityCounts,
    PortfolioRepository,
    PortfolioScope,
    ProductQuerySpec,
    ProductReadRecord,
)
from app.modules.portfolio.schemas import (
    AppliedProductQueryResponse,
    DashboardKpiResponse,
    DashboardResponse,
    DashboardRiskResponse,
    DataNoticeResponse,
    DataQualityAlertResponse,
    EmptyDashboardResponse,
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
    ScopeResponse,
    ScoreResponse,
    SnapshotResponse,
    StrategyDistributionResponse,
    StrategyHistoryResponse,
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
        self._confidence_threshold = strategy_policy.low_confidence_threshold
        self._weak_score_threshold = scoring_config.score_bands.weak_below

    def list_products(self, query: ProductListQuery) -> ProductListResponse:
        scope = _scope(query)
        marketplace = self._repository.ensure_scope(scope)
        spec = ProductQuerySpec(
            scope=scope,
            search=query.search,
            strategy=query.strategy,
            category=query.category,
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
                _product_summary(record, marketplace.code, self._confidence_threshold)
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
                search=query.search,
                strategy=query.strategy,
                category=query.category,
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
        return ProductDetailResponse(
            scope=_scope_response(scope),
            product=ProductIdentityResponse(
                product_id=product.id,
                asin=product.asin,
                title=product.title or (latest_snapshot.title if latest_snapshot else None),
                brand=product.brand or (latest_snapshot.brand if latest_snapshot else None),
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
        latest_import = self._repository.latest_import(scope)
        distribution = self._repository.strategy_distribution(scope)
        opportunity_page = self._repository.list_products(
            ProductQuerySpec(
                scope=scope,
                min_confidence=self._confidence_threshold,
                sort_by=ProductSortField.overall_opportunity,
                page=1,
                page_size=5,
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
                _product_summary(record, marketplace.code, self._confidence_threshold)
                for record in opportunity_page.items
            ],
            top_risks=[
                DashboardRiskResponse(
                    product=_product_summary(record, marketplace.code, self._confidence_threshold),
                    reason_codes=_risk_reason_codes(
                        record,
                        confidence_threshold=self._confidence_threshold,
                        weak_score_threshold=self._weak_score_threshold,
                    ),
                )
                for record in risk_records
            ],
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
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username:
        return None
    return value


def _amazon_url(marketplace_code: str, asin: str) -> str | None:
    normalized_code = marketplace_code.strip().upper()
    domain = _AMAZON_DOMAINS.get(normalized_code)
    normalized_asin = asin.strip().upper()
    if domain is None or len(normalized_asin) != 10 or not normalized_asin.isalnum():
        return None
    return f"https://{domain}/dp/{normalized_asin}"


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
        metrics=_market_metrics(snapshot),
        scores=_ordered_scores(scores),
        recommendation=_recommendation_response(recommendation),
    )


def _product_summary(
    record: ProductReadRecord, marketplace_code: str, confidence_threshold: int
) -> ProductSummaryResponse:
    product = record.product
    snapshot = record.snapshot
    recommendation = _recommendation_response(record.recommendation)
    codes: list[str] = []
    if snapshot is None:
        codes.append("snapshot_missing")
    if snapshot is not None and snapshot.buy_box_price is None:
        codes.append("buy_box_price_missing")
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
        buy_box_price=snapshot.buy_box_price if snapshot else None,
        currency_code=snapshot.currency_code if snapshot else None,
        offer_count=record.offer_count,
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
        data_quality_codes=codes,
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
