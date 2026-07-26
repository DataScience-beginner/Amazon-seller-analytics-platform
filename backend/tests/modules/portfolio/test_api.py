from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.errors import ApplicationError
from app.db.session import get_db
from app.models.domain import (
    ImportBatch,
    Marketplace,
    Organisation,
    Product,
    ProductSnapshot,
    ScoreResult,
    StrategyRecommendation,
)
from app.modules.portfolio.api import router as portfolio_router
from app.modules.portfolio.schemas import (
    ResearchRankingQuery,
    ResearchRankingSortField,
    SortDirection,
)
from app.modules.portfolio.service import PortfolioService


@contextmanager
def _api_client(session: Session) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(portfolio_router, prefix="/api/v1")

    @app.exception_handler(ApplicationError)
    async def application_error_handler(_request: Request, error: ApplicationError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": error.code, "message": error.message}},
        )

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client


def _add_workspace(
    session: Session, *, organisation_id: str, marketplace_id: str, code: str
) -> tuple[Organisation, Marketplace]:
    organisation = Organisation(id=organisation_id, name=f"Synthetic {organisation_id}")
    marketplace = Marketplace(
        id=marketplace_id,
        organisation=organisation,
        code=code,
        name=f"Amazon {code}",
        default_currency_code="INR" if code == "IN" else "USD",
    )
    session.add_all([organisation, marketplace])
    session.flush()
    return organisation, marketplace


def _evidence() -> list[dict[str, object]]:
    return [
        {
            "reason_code": "demand_strong",
            "polarity": "positive",
            "source": "market_score",
            "signal": "demand",
            "observed_value": 82,
            "comparison": "gte",
            "threshold_value": 65,
            "threshold_upper_value": None,
            "statement": "Demand meets the configured threshold.",
        },
        {
            "reason_code": "data_confidence_sufficient",
            "polarity": "informational",
            "source": "market_score",
            "signal": "data_confidence",
            "observed_value": 80,
            "comparison": "gte",
            "threshold_value": 50,
            "threshold_upper_value": None,
            "statement": "Data confidence permits this recommendation.",
        },
    ]


def _add_score(
    session: Session,
    snapshot: ProductSnapshot,
    *,
    name: str,
    value: int,
    version: str = "selleros.market-opportunity.v1",
    created_at: datetime | None = None,
) -> ScoreResult:
    score = ScoreResult(
        snapshot=snapshot,
        score_name=name,
        formula_version=version,
        configuration_checksum="score-config-checksum",
        score_value=value,
        inputs={"source": "synthetic"},
        reason_codes=[],
        created_at=created_at or datetime(2026, 1, 1, tzinfo=UTC),
    )
    session.add(score)
    return score


def _add_product(
    session: Session,
    *,
    product_id: str,
    organisation_id: str,
    marketplace_id: str,
    asin: str,
    title: str,
    brand: str,
    category: str,
    subcategory: str | None = None,
    price: str,
    offers: int,
    overall_score: int,
    confidence: int,
    strategy: str,
    demand_score: int = 85,
    competition_score: int = 85,
    price_stability_score: int = 85,
    sales_rank: int = 10_000,
    monthly_bought: int | None = None,
    image_url: str | None = None,
    amazon_url: str | None = None,
    url_slug: str | None = None,
    observed_on: date | None = date(2026, 1, 1),
    import_batch: ImportBatch | None = None,
) -> Product:
    product = Product(
        id=product_id,
        organisation_id=organisation_id,
        marketplace_id=marketplace_id,
        asin=asin,
        title=title,
        brand=brand,
        category=category,
        subcategory=subcategory,
    )
    session.add(product)
    session.flush()
    snapshot = ProductSnapshot(
        id=f"snapshot-{product_id}",
        product=product,
        snapshot_at=datetime(2026, 1, 1, tzinfo=UTC),
        observed_on=observed_on,
        observed_on_source="user_confirmed" if observed_on is not None else None,
        import_batch=import_batch,
        buy_box_price=Decimal(price),
        buy_box_price_90d=Decimal(price),
        currency_code="INR",
        sales_rank=sales_rank,
        sales_rank_90d=12_000,
        sales_rank_drops_90d=80,
        monthly_sold=200,
        new_offer_count=offers,
        review_count=120,
        buy_box_winner_count_90d=2,
        buy_box_oos_percentage_90d=Decimal("2.5"),
        image_url=image_url,
        amazon_url=amazon_url,
        source_payload=[
            {
                "ordinal": 11,
                "header": "Monthly Sales Trends: Bought in past month",
                "value": monthly_bought,
            },
            *([{"ordinal": 101, "header": "URL: URL slug", "value": url_slug}] if url_slug else []),
        ],
    )
    session.add(snapshot)
    session.flush()
    product.latest_snapshot_id = snapshot.id
    _add_score(session, snapshot, name="demand", value=demand_score)
    _add_score(session, snapshot, name="competition", value=competition_score)
    _add_score(session, snapshot, name="price_stability", value=price_stability_score)
    _add_score(session, snapshot, name="overall_opportunity", value=overall_score)
    _add_score(session, snapshot, name="data_confidence", value=confidence)
    session.add(
        StrategyRecommendation(
            snapshot=snapshot,
            strategy=strategy,
            rules_version="strategy-v1.0.0",
            configuration_checksum="strategy-config-checksum",
            confidence_score=confidence,
            evidence=_evidence(),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    session.flush()
    return product


def test_research_ranking_is_global_transparent_and_marketplace_safe(
    db_session: Session,
) -> None:
    organisation, marketplace = _add_workspace(
        db_session,
        organisation_id="organisation-ranking",
        marketplace_id="marketplace-ranking",
        code="IN",
    )
    stronger = _add_product(
        db_session,
        product_id="product-ranking-strong",
        organisation_id=organisation.id,
        marketplace_id=marketplace.id,
        asin="B000RANK01",
        title="Stronger candidate",
        brand="Synthetic",
        category="Toys",
        subcategory="Cars",
        price="999",
        offers=3,
        overall_score=80,
        confidence=90,
        strategy="test_buy",
        demand_score=95,
        competition_score=85,
        price_stability_score=90,
        sales_rank=5_000,
        monthly_bought=300,
        image_url=("https://m.media-amazon.com/first.jpg;" "https://m.media-amazon.com/second.jpg"),
        url_slug="Stronger-Candidate-Toy",
    )
    weaker = _add_product(
        db_session,
        product_id="product-ranking-weak",
        organisation_id=organisation.id,
        marketplace_id=marketplace.id,
        asin="B000RANK02",
        title="Weaker candidate",
        brand="Synthetic",
        category="Toys",
        subcategory="Cars",
        price="499",
        offers=1,
        overall_score=70,
        confidence=80,
        strategy="monitor",
        demand_score=65,
        competition_score=100,
        price_stability_score=70,
        sales_rank=20_000,
        monthly_bought=100,
    )
    db_session.commit()

    response = PortfolioService(db_session).research_ranking(
        ResearchRankingQuery(
            organisation_id=organisation.id,
            marketplace_id=marketplace.id,
            subcategory="Cars",
            sort_by=ResearchRankingSortField.sales_rank,
            sort_direction=SortDirection.ascending,
        )
    )

    payload = response.model_dump(mode="json")
    assert payload["weights"]["demand"] == 30
    assert payload["formula_version"] == "selleros.research-priority.v1"
    assert payload["sort_by"] == "sales_rank"
    assert [item["product"]["sales_rank"] for item in payload["items"]] == [
        5_000,
        20_000,
    ]
    assert payload["items"][0]["product"]["product_id"] == stronger.id
    assert payload["items"][0]["ranking"]["rank"] == 1
    assert payload["items"][0]["product"]["image_url"] == ("https://m.media-amazon.com/first.jpg")
    assert payload["items"][0]["product"]["amazon_url"] == (
        "https://www.amazon.in/Stronger-Candidate-Toy/dp/B000RANK01"
    )
    weak_payload = next(
        item for item in payload["items"] if item["product"]["product_id"] == weaker.id
    )
    competition = next(
        component
        for component in weak_payload["ranking"]["components"]
        if component["id"] == "competition_quality"
    )
    assert competition["score"] == 50
    assert "single_seller_control_risk" in weak_payload["ranking"]["warning_codes"]


def test_research_screens_brand_filter_and_critical_metrics(db_session: Session) -> None:
    organisation, marketplace = _add_workspace(
        db_session,
        organisation_id="organisation-research",
        marketplace_id="marketplace-research",
        code="IN",
    )
    priority = _add_product(
        db_session,
        product_id="product-priority",
        organisation_id=organisation.id,
        marketplace_id=marketplace.id,
        asin="B000PRIO01",
        title="Synthetic priority candidate",
        brand="Declared Brand",
        category="Home",
        price="1499.00",
        offers=2,
        overall_score=86,
        confidence=90,
        strategy="test_buy",
        demand_score=90,
        competition_score=92,
        price_stability_score=88,
        monthly_bought=700,
    )
    _add_product(
        db_session,
        product_id="product-generic",
        organisation_id=organisation.id,
        marketplace_id=marketplace.id,
        asin="B000GENE01",
        title="Synthetic generic monitor",
        brand="Generic",
        category="Home",
        price="499.00",
        offers=8,
        overall_score=60,
        confidence=80,
        strategy="monitor",
        demand_score=65,
        competition_score=60,
        price_stability_score=75,
    )
    db_session.commit()
    scope = {
        "organisation_id": organisation.id,
        "marketplace_id": marketplace.id,
    }

    with _api_client(db_session) as client:
        screened = client.get(
            "/api/v1/products",
            params={**scope, "screen": "priority_research"},
        )
        generic = client.get(
            "/api/v1/products",
            params={
                **scope,
                "screen": "all",
                "brand_classification": "likely_generic",
            },
        )

    assert screened.status_code == 200
    payload = screened.json()
    assert payload["pagination"]["total_items"] == 1
    assert payload["items"][0]["product_id"] == priority.id
    assert payload["items"][0]["research"]["status"] == "priority_research"
    assert payload["items"][0]["research"]["brand_classification"] == "declared_brand"
    assert payload["items"][0]["estimated_monthly_bought"] == 700
    assert payload["items"][0]["demand_score"] == 90
    assert payload["research_policy_version"] == "product-research-v1.0.0"
    assert len(payload["research_configuration_checksum"]) == 64
    assert {screen["id"] for screen in payload["screens"]} == {
        "priority_research",
        "promising",
        "low_competition",
        "stable_pricing",
        "needs_evidence",
        "all",
    }
    assert generic.json()["pagination"]["total_items"] == 1
    assert generic.json()["items"][0]["research"]["brand_classification"] == "likely_generic"


def test_dashboard_summarises_dataset_evidence_without_inventing_revenue(
    db_session: Session,
) -> None:
    organisation, marketplace = _add_workspace(
        db_session,
        organisation_id="organisation-overview",
        marketplace_id="marketplace-overview",
        code="IN",
    )
    first_batch = ImportBatch(
        id="overview-batch-1",
        organisation_id=organisation.id,
        marketplace_id=marketplace.id,
        original_filename="first.xlsx",
        checksum="overview-checksum-1",
    )
    second_batch = ImportBatch(
        id="overview-batch-2",
        organisation_id=organisation.id,
        marketplace_id=marketplace.id,
        original_filename="second.xlsx",
        checksum="overview-checksum-2",
    )
    db_session.add_all([first_batch, second_batch])
    first = _add_product(
        db_session,
        product_id="overview-1",
        organisation_id=organisation.id,
        marketplace_id=marketplace.id,
        asin="B000OVER01",
        title="Synthetic race car",
        brand="Popular Brand",
        category="Toys & Games",
        price="500.00",
        offers=2,
        overall_score=80,
        confidence=90,
        strategy="test_buy",
        monthly_bought=100,
        import_batch=first_batch,
    )
    second = _add_product(
        db_session,
        product_id="overview-2",
        organisation_id=organisation.id,
        marketplace_id=marketplace.id,
        asin="B000OVER02",
        title="Synthetic doll",
        brand="Popular Brand",
        category="Toys & Games",
        price="750.00",
        offers=3,
        overall_score=75,
        confidence=90,
        strategy="test_buy",
        monthly_bought=None,
        import_batch=second_batch,
    )
    first.subcategory = "Cars & Race Cars"
    second.subcategory = "Dolls"
    db_session.commit()

    with _api_client(db_session) as client:
        response = client.get(
            "/api/v1/dashboard",
            params={
                "organisation_id": organisation.id,
                "marketplace_id": marketplace.id,
            },
        )
        category_response = client.get(
            "/api/v1/dashboard/dataset-overview",
            params={
                "organisation_id": organisation.id,
                "marketplace_id": marketplace.id,
                "category": "Toys & Games",
            },
        )
        estimate_response = client.post(
            "/api/v1/dashboard/category-cost-estimate",
            params={
                "organisation_id": organisation.id,
                "marketplace_id": marketplace.id,
                "subcategory": "Cars & Race Cars",
            },
            json={
                "gst_rate_percent": "18",
                "amazon_fee_percent": "15",
                "shipping_percent": "8",
                "advertising_percent": "5",
                "returns_percent": "3",
                "target_profit_percent": "15",
            },
        )
        selected_batch = client.get(
            "/api/v1/dashboard/dataset-overview",
            params={
                "organisation_id": organisation.id,
                "marketplace_id": marketplace.id,
                "import_batch_id": first_batch.id,
            },
        )
        selected_products = client.get(
            "/api/v1/products",
            params={
                "organisation_id": organisation.id,
                "marketplace_id": marketplace.id,
                "import_batch_id": first_batch.id,
            },
        )

    assert response.status_code == 200
    overview = response.json()["dataset_overview"]
    assert overview["readiness"] == "relative_research_only"
    assert overview["product_count"] == 2
    assert overview["category_count"] == 1
    assert overview["subcategory_count"] == 2
    assert overview["monthly_demand_coverage_percentage"] == "50.0"
    assert overview["estimated_monthly_revenue"] is None
    assert overview["top_categories"][0]["label"] == "Toys & Games"
    assert overview["price_range_currency_code"] == "INR"
    assert overview["price_ranges"] == [
        {"label": "500\u2013999", "product_count": 2, "product_percentage": "100.0"}
    ]
    assert "revenue_blocked_low_monthly_demand" in overview["conclusion_codes"]
    assert category_response.status_code == 200
    assert category_response.json()["product_count"] == 2
    assert {item["label"] for item in category_response.json()["top_subcategories"]} == {
        "Cars & Race Cars",
        "Dolls",
    }
    assert estimate_response.status_code == 200
    estimate = estimate_response.json()
    assert estimate["formula_version"] == "selleros.target-sourcing-cost.v1"
    assert estimate["pagination"]["total_items"] == 1
    assert estimate["items"][0]["asin"] == "B000OVER01"
    assert estimate["items"][0]["selling_price_source"] == "buy_box_90d_average"
    assert estimate["items"][0]["maximum_wholesale_cost_ex_gst"] == "205.17"
    assert selected_batch.json()["product_count"] == 1
    assert selected_products.json()["pagination"]["total_items"] == 1
    assert selected_products.json()["items"][0]["asin"] == "B000OVER01"


def test_legacy_undated_evidence_is_browsable_but_excluded_from_current_decisions(
    db_session: Session,
) -> None:
    organisation, marketplace = _add_workspace(
        db_session,
        organisation_id="organisation-undated",
        marketplace_id="marketplace-undated",
        code="IN",
    )
    product = _add_product(
        db_session,
        product_id="product-undated",
        organisation_id=organisation.id,
        marketplace_id=marketplace.id,
        asin="B000UND001",
        title="Synthetic undated legacy product",
        brand="Synthetic",
        category="Legacy",
        price="100.00",
        offers=2,
        overall_score=90,
        confidence=90,
        strategy="test_buy",
        observed_on=None,
    )
    db_session.commit()
    scope = {
        "organisation_id": organisation.id,
        "marketplace_id": marketplace.id,
    }

    with _api_client(db_session) as client:
        dashboard = client.get("/api/v1/dashboard", params=scope)
        products = client.get("/api/v1/products", params=scope)
        detail = client.get(f"/api/v1/products/{product.id}", params=scope)

    assert dashboard.status_code == 200
    dashboard_payload = dashboard.json()
    assert dashboard_payload["tracked_product_count"] == 1
    assert dashboard_payload["top_opportunities"] == []
    assert dashboard_payload["top_risks"] == []
    assert sum(item["count"] for item in dashboard_payload["strategy_distribution"]) == 0
    assert "observation_date_unconfirmed" in {
        alert["id"] for alert in dashboard_payload["data_quality_alerts"]
    }

    item = products.json()["items"][0]
    assert item["latest_observed_on"] is None
    assert item["strategy"] is None
    assert "observation_date_unconfirmed" in item["data_quality_codes"]
    assert "observation_date_unconfirmed" in {notice["code"] for notice in detail.json()["notices"]}


def test_empty_dashboard_is_scoped_and_actionable(db_session: Session) -> None:
    organisation, marketplace = _add_workspace(
        db_session,
        organisation_id="organisation-a",
        marketplace_id="marketplace-a",
        code="IN",
    )
    _, other_marketplace = _add_workspace(
        db_session,
        organisation_id="organisation-b",
        marketplace_id="marketplace-b",
        code="US",
    )
    db_session.commit()

    with _api_client(db_session) as client:
        response = client.get(
            "/api/v1/dashboard",
            params={
                "organisation_id": organisation.id,
                "marketplace_id": marketplace.id,
            },
        )
        cross_tenant = client.get(
            "/api/v1/dashboard",
            params={
                "organisation_id": organisation.id,
                "marketplace_id": other_marketplace.id,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tracked_product_count"] == 0
    assert payload["latest_import"] is None
    assert payload["strategy_distribution"] == [
        {"strategy": "discovery", "count": 0},
        {"strategy": "test_buy", "count": 0},
        {"strategy": "growth", "count": 0},
        {"strategy": "cash_cow", "count": 0},
        {"strategy": "premium_margin", "count": 0},
        {"strategy": "monitor", "count": 0},
        {"strategy": "clearance_watch", "count": 0},
        {"strategy": "avoid", "count": 0},
    ]
    assert payload["empty_state"]["primary_action"] == "open_imports"
    assert [kpi["id"] for kpi in payload["kpis"]] == [
        "tracked_products",
        "classified_products",
        "average_opportunity_score",
        "low_confidence_products",
    ]
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["error"]["code"] == "resource_not_found"


def test_product_filters_sort_pagination_and_tenant_scope(db_session: Session) -> None:
    organisation, marketplace = _add_workspace(
        db_session,
        organisation_id="organisation-a",
        marketplace_id="marketplace-a",
        code="IN",
    )
    other_organisation, other_marketplace = _add_workspace(
        db_session,
        organisation_id="organisation-b",
        marketplace_id="marketplace-b",
        code="US",
    )
    first = _add_product(
        db_session,
        product_id="00000000-0000-0000-0000-000000000001",
        organisation_id=organisation.id,
        marketplace_id=marketplace.id,
        asin="B000000001",
        title="Alpha storage box",
        brand="Acme",
        category="Home",
        price="19.99",
        offers=3,
        overall_score=80,
        confidence=80,
        strategy="growth",
    )
    second = _add_product(
        db_session,
        product_id="00000000-0000-0000-0000-000000000002",
        organisation_id=organisation.id,
        marketplace_id=marketplace.id,
        asin="B000000002",
        title="Beta storage box",
        brand="Acme",
        category="Home",
        price="25.00",
        offers=5,
        overall_score=80,
        confidence=70,
        strategy="growth",
    )
    _add_product(
        db_session,
        product_id="00000000-0000-0000-0000-000000000003",
        organisation_id=organisation.id,
        marketplace_id=marketplace.id,
        asin="B000000003",
        title="Gamma toy",
        brand="Different",
        category="Toys",
        price="9.00",
        offers=15,
        overall_score=20,
        confidence=90,
        strategy="avoid",
    )
    _add_product(
        db_session,
        product_id="00000000-0000-0000-0000-000000000004",
        organisation_id=other_organisation.id,
        marketplace_id=other_marketplace.id,
        asin="B000000004",
        title="Other tenant product",
        brand="Acme",
        category="Home",
        price="20.00",
        offers=4,
        overall_score=99,
        confidence=99,
        strategy="growth",
    )
    db_session.commit()
    params: dict[str, str | int] = {
        "organisation_id": organisation.id,
        "marketplace_id": marketplace.id,
        "search": "Acme",
        "strategy": "growth",
        "category": "home",
        "min_score": 80,
        "max_score": 80,
        "min_offer_count": 3,
        "max_offer_count": 5,
        "min_price": "10.00",
        "max_price": "30.00",
        "min_confidence": 60,
        "max_confidence": 90,
        "sort_by": "overall_opportunity",
        "sort_direction": "desc",
        "page_size": 1,
    }

    with _api_client(db_session) as client:
        first_page = client.get("/api/v1/products", params={**params, "page": 1})
        second_page = client.get("/api/v1/products", params={**params, "page": 2})
        asin_search = client.get(
            "/api/v1/products",
            params={
                "organisation_id": organisation.id,
                "marketplace_id": marketplace.id,
                "search": "B000000003",
            },
        )

    assert first_page.status_code == 200
    first_payload = first_page.json()
    second_payload = second_page.json()
    assert first_payload["pagination"] == {
        "page": 1,
        "page_size": 1,
        "total_items": 2,
        "total_pages": 2,
        "has_previous": False,
        "has_next": True,
    }
    assert first_payload["items"][0]["product_id"] == first.id
    assert second_payload["items"][0]["product_id"] == second.id
    assert second_payload["pagination"]["has_previous"] is True
    assert asin_search.json()["items"][0]["asin"] == "B000000003"


def test_product_detail_returns_latest_evidence_and_last_24_snapshots(
    db_session: Session,
) -> None:
    organisation, marketplace = _add_workspace(
        db_session,
        organisation_id="organisation-a",
        marketplace_id="marketplace-a",
        code="IN",
    )
    product = Product(
        id="00000000-0000-0000-0000-000000000010",
        organisation_id=organisation.id,
        marketplace_id=marketplace.id,
        asin="B000000010",
        title="Historical product",
        brand="Synthetic",
        category="Home",
        amazon_url="javascript:alert(1)",
    )
    db_session.add(product)
    db_session.flush()
    started_at = datetime(2024, 1, 1, tzinfo=UTC)
    snapshots: list[ProductSnapshot] = []
    for offset in range(25):
        snapshot = ProductSnapshot(
            id=f"snapshot-history-{offset:02d}",
            product=product,
            snapshot_at=started_at + timedelta(days=offset),
            buy_box_price=Decimal("24.99"),
            buy_box_price_90d=Decimal("25.50"),
            currency_code="INR",
            sales_rank=8_000 + offset,
            sales_rank_90d=9_000,
            sales_rank_drops_90d=75,
            review_rating=Decimal("4.25"),
            review_count=200,
            new_offer_count=4,
            buy_box_winner_count_90d=2,
            monthly_sold=180,
            # Deliberately omitted to produce an explicit missing-data notice.
            buy_box_oos_percentage_90d=None,
        )
        db_session.add(snapshot)
        db_session.flush()
        snapshots.append(snapshot)
        db_session.add(
            StrategyRecommendation(
                snapshot=snapshot,
                strategy="monitor",
                rules_version="strategy-v1.0.0",
                configuration_checksum="strategy-config-checksum",
                confidence_score=70,
                evidence=_evidence(),
                created_at=snapshot.snapshot_at,
            )
        )

    latest = snapshots[-1]
    product.latest_snapshot_id = latest.id
    for name, value in (
        ("demand", 82),
        ("competition", 68),
        ("price_stability", 74),
        ("data_confidence", 85),
    ):
        _add_score(db_session, latest, name=name, value=value, created_at=latest.snapshot_at)
    _add_score(
        db_session,
        latest,
        name="overall_opportunity",
        value=70,
        version="selleros.market-opportunity.v1",
        created_at=latest.snapshot_at,
    )
    newest_score = _add_score(
        db_session,
        latest,
        name="overall_opportunity",
        value=81,
        version="selleros.market-opportunity.v2",
        created_at=latest.snapshot_at + timedelta(seconds=1),
    )
    newest_recommendation = StrategyRecommendation(
        snapshot=latest,
        strategy="growth",
        rules_version="strategy-v2.0.0",
        configuration_checksum="strategy-config-v2-checksum",
        confidence_score=85,
        evidence=_evidence(),
        created_at=latest.snapshot_at + timedelta(seconds=1),
    )
    db_session.add(newest_recommendation)
    db_session.commit()

    with _api_client(db_session) as client:
        response = client.get(
            f"/api/v1/products/{product.id}",
            params={
                "organisation_id": organisation.id,
                "marketplace_id": marketplace.id,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["product"]["amazon_url"] == "https://www.amazon.in/dp/B000000010"
    assert len(payload["snapshot_history"]) == 24
    assert payload["snapshot_history"][0]["id"] == latest.id
    assert payload["snapshot_history"][-1]["id"] == snapshots[1].id
    latest_payload = payload["latest_snapshot"]
    assert latest_payload["scores"][-1]["id"] == newest_score.id
    assert latest_payload["scores"][-1]["value"] == 81
    assert latest_payload["recommendation"]["id"] == newest_recommendation.id
    assert latest_payload["recommendation"]["strategy"] == "growth"
    assert latest_payload["recommendation"]["evidence"][0]["reason_code"] == "demand_strong"
    assert payload["strategy_history"][0]["strategy"] == "growth"
    assert any(notice["field"] == "buy_box_oos_percentage_90d" for notice in payload["notices"])


def test_product_detail_hides_unsupported_recommendation_without_evidence(
    db_session: Session,
) -> None:
    organisation, marketplace = _add_workspace(
        db_session,
        organisation_id="organisation-a",
        marketplace_id="marketplace-a",
        code="IN",
    )
    product = _add_product(
        db_session,
        product_id="00000000-0000-0000-0000-000000000020",
        organisation_id=organisation.id,
        marketplace_id=marketplace.id,
        asin="B000000020",
        title="Evidence safety product",
        brand="Synthetic",
        category="Home",
        price="15.00",
        offers=2,
        overall_score=70,
        confidence=75,
        strategy="test_buy",
    )
    latest = db_session.get(ProductSnapshot, product.latest_snapshot_id)
    assert latest is not None
    db_session.add(
        StrategyRecommendation(
            snapshot=latest,
            strategy="growth",
            rules_version="strategy-v2.0.0",
            configuration_checksum="invalid-no-evidence",
            confidence_score=90,
            evidence=[],
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
    )
    db_session.commit()

    with _api_client(db_session) as client:
        response = client.get(
            f"/api/v1/products/{product.id}",
            params={
                "organisation_id": organisation.id,
                "marketplace_id": marketplace.id,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["latest_snapshot"]["recommendation"] is None
    assert payload["strategy_history"] == []
    assert "recommendation_evidence_missing" in {notice["code"] for notice in payload["notices"]}
