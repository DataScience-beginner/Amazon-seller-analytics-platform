from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql.elements import ColumnElement

from app.core.errors import NotFoundError
from app.models.domain import (
    ImportBatch,
    Marketplace,
    Product,
    ProductSnapshot,
    ScoreResult,
    StrategyRecommendation,
)
from app.modules.portfolio.schemas import ProductSortField, SortDirection
from app.modules.strategies.models import Strategy


@dataclass(frozen=True, slots=True)
class PortfolioScope:
    organisation_id: str
    marketplace_id: str


@dataclass(frozen=True, slots=True)
class ProductQuerySpec:
    scope: PortfolioScope
    search: str | None = None
    strategy: Strategy | None = None
    category: str | None = None
    min_score: int | None = None
    max_score: int | None = None
    min_offer_count: int | None = None
    max_offer_count: int | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    min_confidence: int | None = None
    max_confidence: int | None = None
    sort_by: ProductSortField = ProductSortField.overall_opportunity
    sort_direction: SortDirection = SortDirection.descending
    page: int = 1
    page_size: int = 25


@dataclass(frozen=True, slots=True)
class ProductReadRecord:
    product: Product
    snapshot: ProductSnapshot | None
    overall_score: ScoreResult | None
    confidence_score: ScoreResult | None
    recommendation: StrategyRecommendation | None
    offer_count: int | None


@dataclass(frozen=True, slots=True)
class ProductPage:
    items: list[ProductReadRecord]
    total_items: int


@dataclass(frozen=True, slots=True)
class DashboardCounts:
    tracked_products: int
    classified_products: int
    average_opportunity_score: int | None
    low_confidence_products: int


@dataclass(frozen=True, slots=True)
class DataQualityCounts:
    products_without_snapshot: int
    missing_buy_box_price: int
    missing_opportunity_score: int
    missing_recommendation: int


@dataclass(frozen=True, slots=True)
class _ProjectionBundle:
    statement: Select[Any]
    snapshot: Any
    overall_score: Any
    confidence_score: Any
    recommendation: Any
    offer_count: ColumnElement[int | None]


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class PortfolioRepository:
    """All bounded, tenant-scoped database reads used by the portfolio module."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_scope(self, scope: PortfolioScope) -> Marketplace:
        marketplace = self._session.scalar(
            select(Marketplace).where(
                Marketplace.id == scope.marketplace_id,
                Marketplace.organisation_id == scope.organisation_id,
            )
        )
        if marketplace is None:
            # A single non-disclosing response prevents cross-tenant enumeration.
            raise NotFoundError("Marketplace")
        return marketplace

    def list_products(self, spec: ProductQuerySpec) -> ProductPage:
        bundle = self._build_product_projection(spec.scope)
        statement = self._apply_filters(bundle, spec)
        total_items = int(
            self._session.scalar(
                select(func.count()).select_from(statement.order_by(None).subquery())
            )
            or 0
        )
        statement = self._apply_sort(bundle, statement, spec.sort_by, spec.sort_direction)
        statement = statement.offset((spec.page - 1) * spec.page_size).limit(spec.page_size)
        return ProductPage(
            items=self._records(self._session.execute(statement).all()),
            total_items=total_items,
        )

    def list_risk_products(
        self,
        scope: PortfolioScope,
        *,
        confidence_threshold: int,
        weak_score_threshold: int,
        limit: int,
    ) -> list[ProductReadRecord]:
        bundle = self._build_product_projection(scope)
        recommendation = bundle.recommendation
        overall_score = bundle.overall_score
        confidence_score = bundle.confidence_score
        risk_priority = case(
            (recommendation.strategy == Strategy.CLEARANCE_WATCH.value, 0),
            (recommendation.strategy == Strategy.AVOID.value, 1),
            (
                and_(
                    confidence_score.id.is_not(None),
                    confidence_score.score_value < confidence_threshold,
                ),
                2,
            ),
            (
                and_(
                    overall_score.id.is_not(None),
                    overall_score.score_value < weak_score_threshold,
                ),
                3,
            ),
            else_=4,
        )
        statement = (
            bundle.statement.where(
                or_(
                    recommendation.strategy.in_(
                        [Strategy.CLEARANCE_WATCH.value, Strategy.AVOID.value]
                    ),
                    confidence_score.score_value < confidence_threshold,
                    overall_score.score_value < weak_score_threshold,
                )
            )
            .order_by(
                risk_priority.asc(),
                overall_score.score_value.is_(None).asc(),
                overall_score.score_value.asc(),
                confidence_score.score_value.is_(None).asc(),
                confidence_score.score_value.asc(),
                Product.id.asc(),
            )
            .limit(limit)
        )
        return self._records(self._session.execute(statement).all())

    def get_product(self, scope: PortfolioScope, product_id: str) -> Product:
        product = self._session.scalar(
            select(Product).where(
                Product.id == product_id,
                Product.organisation_id == scope.organisation_id,
                Product.marketplace_id == scope.marketplace_id,
            )
        )
        if product is None:
            raise NotFoundError("Product")
        return product

    def get_latest_snapshot(self, product: Product) -> ProductSnapshot | None:
        if product.latest_snapshot_id is None:
            return None
        return self._session.scalar(
            select(ProductSnapshot).where(
                ProductSnapshot.id == product.latest_snapshot_id,
                ProductSnapshot.product_id == product.id,
            )
        )

    def get_snapshot_history(self, product_id: str, *, limit: int = 24) -> list[ProductSnapshot]:
        return list(
            self._session.scalars(
                select(ProductSnapshot)
                .where(ProductSnapshot.product_id == product_id)
                .order_by(ProductSnapshot.snapshot_at.desc(), ProductSnapshot.id.desc())
                .limit(limit)
            ).all()
        )

    def get_latest_scores(self, snapshot_ids: list[str]) -> dict[str, dict[str, ScoreResult]]:
        if not snapshot_ids:
            return {}
        rows = self._session.scalars(
            select(ScoreResult)
            .where(ScoreResult.snapshot_id.in_(snapshot_ids))
            .order_by(
                ScoreResult.snapshot_id,
                ScoreResult.score_name,
                ScoreResult.created_at.desc(),
                ScoreResult.formula_version.desc(),
                ScoreResult.id.desc(),
            )
        ).all()
        latest: dict[str, dict[str, ScoreResult]] = {}
        for score in rows:
            scores_for_snapshot = latest.setdefault(score.snapshot_id, {})
            scores_for_snapshot.setdefault(score.score_name, score)
        return latest

    def get_latest_recommendations(
        self, snapshot_ids: list[str]
    ) -> dict[str, StrategyRecommendation]:
        if not snapshot_ids:
            return {}
        rows = self._session.scalars(
            select(StrategyRecommendation)
            .where(StrategyRecommendation.snapshot_id.in_(snapshot_ids))
            .order_by(
                StrategyRecommendation.snapshot_id,
                StrategyRecommendation.created_at.desc(),
                StrategyRecommendation.rules_version.desc(),
                StrategyRecommendation.id.desc(),
            )
        ).all()
        latest: dict[str, StrategyRecommendation] = {}
        for recommendation in rows:
            latest.setdefault(recommendation.snapshot_id, recommendation)
        return latest

    def latest_import(self, scope: PortfolioScope) -> ImportBatch | None:
        return self._session.scalar(
            select(ImportBatch)
            .where(
                ImportBatch.organisation_id == scope.organisation_id,
                ImportBatch.marketplace_id == scope.marketplace_id,
            )
            .order_by(ImportBatch.uploaded_at.desc(), ImportBatch.id.desc())
            .limit(1)
        )

    def strategy_distribution(self, scope: PortfolioScope) -> dict[str, int]:
        bundle = self._build_product_projection(scope)
        recommendation = bundle.recommendation
        rows = self._session.execute(
            select(recommendation.strategy, func.count(Product.id))
            .select_from(Product)
            .outerjoin(
                bundle.snapshot,
                and_(
                    bundle.snapshot.id == Product.latest_snapshot_id,
                    bundle.snapshot.product_id == Product.id,
                ),
            )
            .outerjoin(
                recommendation,
                recommendation.id == self._latest_recommendation_id(Product.latest_snapshot_id),
            )
            .where(
                Product.organisation_id == scope.organisation_id,
                Product.marketplace_id == scope.marketplace_id,
                recommendation.id.is_not(None),
            )
            .group_by(recommendation.strategy)
        ).all()
        return {str(strategy): int(count) for strategy, count in rows}

    def dashboard_counts(
        self, scope: PortfolioScope, *, confidence_threshold: int
    ) -> DashboardCounts:
        bundle = self._build_product_projection(scope)
        row = self._session.execute(
            bundle.statement.with_only_columns(
                func.count(Product.id),
                func.count(bundle.recommendation.id),
                func.avg(bundle.overall_score.score_value),
                func.sum(
                    case(
                        (
                            bundle.confidence_score.score_value < confidence_threshold,
                            1,
                        ),
                        else_=0,
                    )
                ),
            ).order_by(None)
        ).one()
        average = row[2]
        average_score = int(Decimal(str(average)).quantize(Decimal("1"))) if average else None
        return DashboardCounts(
            tracked_products=int(row[0] or 0),
            classified_products=int(row[1] or 0),
            average_opportunity_score=average_score,
            low_confidence_products=int(row[3] or 0),
        )

    def data_quality_counts(self, scope: PortfolioScope) -> DataQualityCounts:
        bundle = self._build_product_projection(scope)
        row = self._session.execute(
            bundle.statement.with_only_columns(
                func.sum(case((bundle.snapshot.id.is_(None), 1), else_=0)),
                func.sum(
                    case(
                        (
                            and_(
                                bundle.snapshot.id.is_not(None),
                                bundle.snapshot.buy_box_price.is_(None),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                func.sum(
                    case(
                        (
                            and_(
                                bundle.snapshot.id.is_not(None),
                                bundle.overall_score.id.is_(None),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                func.sum(
                    case(
                        (
                            and_(
                                bundle.snapshot.id.is_not(None),
                                bundle.recommendation.id.is_(None),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
            ).order_by(None)
        ).one()
        return DataQualityCounts(
            products_without_snapshot=int(row[0] or 0),
            missing_buy_box_price=int(row[1] or 0),
            missing_opportunity_score=int(row[2] or 0),
            missing_recommendation=int(row[3] or 0),
        )

    def _build_product_projection(self, scope: PortfolioScope) -> _ProjectionBundle:
        snapshot = aliased(ProductSnapshot, name="latest_snapshot")
        overall_score = aliased(ScoreResult, name="latest_overall_score")
        confidence_score = aliased(ScoreResult, name="latest_confidence_score")
        recommendation = aliased(StrategyRecommendation, name="latest_recommendation")
        offer_count = func.coalesce(snapshot.new_offer_count, snapshot.total_offer_count).label(
            "offer_count"
        )
        statement = (
            select(
                Product,
                snapshot,
                overall_score,
                confidence_score,
                recommendation,
                offer_count,
            )
            .select_from(Product)
            .outerjoin(
                snapshot,
                and_(
                    snapshot.id == Product.latest_snapshot_id,
                    snapshot.product_id == Product.id,
                ),
            )
            .outerjoin(
                overall_score,
                overall_score.id
                == self._latest_score_id(Product.latest_snapshot_id, "overall_opportunity"),
            )
            .outerjoin(
                confidence_score,
                confidence_score.id
                == self._latest_score_id(Product.latest_snapshot_id, "data_confidence"),
            )
            .outerjoin(
                recommendation,
                recommendation.id == self._latest_recommendation_id(Product.latest_snapshot_id),
            )
            .where(
                Product.organisation_id == scope.organisation_id,
                Product.marketplace_id == scope.marketplace_id,
            )
        )
        return _ProjectionBundle(
            statement=statement,
            snapshot=snapshot,
            overall_score=overall_score,
            confidence_score=confidence_score,
            recommendation=recommendation,
            offer_count=offer_count,
        )

    @staticmethod
    def _latest_score_id(snapshot_id: Any, score_name: str) -> ColumnElement[str | None]:
        return (
            select(ScoreResult.id)
            .where(
                ScoreResult.snapshot_id == snapshot_id,
                ScoreResult.score_name == score_name,
            )
            .order_by(
                ScoreResult.created_at.desc(),
                ScoreResult.formula_version.desc(),
                ScoreResult.id.desc(),
            )
            .limit(1)
            .correlate(Product)
            .scalar_subquery()
        )

    @staticmethod
    def _latest_recommendation_id(
        snapshot_id: Any,
    ) -> ColumnElement[str | None]:
        return (
            select(StrategyRecommendation.id)
            .where(StrategyRecommendation.snapshot_id == snapshot_id)
            .order_by(
                StrategyRecommendation.created_at.desc(),
                StrategyRecommendation.rules_version.desc(),
                StrategyRecommendation.id.desc(),
            )
            .limit(1)
            .correlate(Product)
            .scalar_subquery()
        )

    @staticmethod
    def _apply_filters(bundle: _ProjectionBundle, spec: ProductQuerySpec) -> Select[Any]:
        statement = bundle.statement
        if spec.search:
            pattern = f"%{_escape_like(spec.search)}%"
            statement = statement.where(
                or_(
                    Product.asin.ilike(pattern, escape="\\"),
                    Product.title.ilike(pattern, escape="\\"),
                    Product.brand.ilike(pattern, escape="\\"),
                )
            )
        if spec.strategy is not None:
            statement = statement.where(bundle.recommendation.strategy == spec.strategy.value)
        if spec.category is not None:
            statement = statement.where(func.lower(Product.category) == spec.category.casefold())
        if spec.min_score is not None:
            statement = statement.where(bundle.overall_score.score_value >= spec.min_score)
        if spec.max_score is not None:
            statement = statement.where(bundle.overall_score.score_value <= spec.max_score)
        if spec.min_offer_count is not None:
            statement = statement.where(bundle.offer_count >= spec.min_offer_count)
        if spec.max_offer_count is not None:
            statement = statement.where(bundle.offer_count <= spec.max_offer_count)
        if spec.min_price is not None:
            statement = statement.where(bundle.snapshot.buy_box_price >= spec.min_price)
        if spec.max_price is not None:
            statement = statement.where(bundle.snapshot.buy_box_price <= spec.max_price)
        if spec.min_confidence is not None:
            statement = statement.where(bundle.confidence_score.score_value >= spec.min_confidence)
        if spec.max_confidence is not None:
            statement = statement.where(bundle.confidence_score.score_value <= spec.max_confidence)
        return statement

    @staticmethod
    def _apply_sort(
        bundle: _ProjectionBundle,
        statement: Select[Any],
        sort_by: ProductSortField,
        direction: SortDirection,
    ) -> Select[Any]:
        expressions: dict[ProductSortField, ColumnElement[Any]] = {
            ProductSortField.overall_opportunity: bundle.overall_score.score_value,
            ProductSortField.data_confidence: bundle.confidence_score.score_value,
            ProductSortField.price: bundle.snapshot.buy_box_price,
            ProductSortField.offer_count: bundle.offer_count,
            ProductSortField.snapshot_at: bundle.snapshot.snapshot_at,
            ProductSortField.asin: func.lower(Product.asin),
            ProductSortField.product_title: func.lower(Product.title),
            ProductSortField.brand: func.lower(Product.brand),
            ProductSortField.category: func.lower(Product.category),
            ProductSortField.strategy: func.lower(bundle.recommendation.strategy),
        }
        expression = expressions[sort_by]
        value_order = (
            expression.asc() if direction is SortDirection.ascending else expression.desc()
        )
        return statement.order_by(expression.is_(None).asc(), value_order, Product.id.asc())

    @staticmethod
    def _records(rows: Sequence[Any]) -> list[ProductReadRecord]:
        return [
            ProductReadRecord(
                product=cast(Product, row[0]),
                snapshot=cast(ProductSnapshot | None, row[1]),
                overall_score=cast(ScoreResult | None, row[2]),
                confidence_score=cast(ScoreResult | None, row[3]),
                recommendation=cast(StrategyRecommendation | None, row[4]),
                offer_count=cast(int | None, row[5]),
            )
            for row in rows
        ]
