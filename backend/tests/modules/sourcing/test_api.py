from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApplicationError
from app.db.session import get_db
from app.models.domain import (
    AuditEvent,
    Marketplace,
    Organisation,
    Product,
    ProductSnapshot,
    ScoreResult,
    Supplier,
    SupplierOffer,
    SupplierOfferPriceTier,
)
from app.models.domain import (
    TestBuyRecommendation as RecommendationRecord,
)
from app.modules.sourcing.api import router as sourcing_router
from app.modules.sourcing.repository import SourcingRepository


@contextmanager
def _client(session: Session) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(sourcing_router, prefix="/api/v1")

    @app.exception_handler(ApplicationError)
    async def handle_application_error(_request: Request, error: ApplicationError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": error.code, "message": error.message}},
        )

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client


def _workspace(
    session: Session,
    *,
    organisation_id: str,
    marketplace_id: str,
    product_id: str,
    confidence: int | None = 80,
    monthly_demand: int | None = 60,
) -> tuple[Organisation, Marketplace, Product]:
    organisation = Organisation(id=organisation_id, name=f"Seller {organisation_id}")
    marketplace = Marketplace(
        id=marketplace_id,
        organisation=organisation,
        code="IN",
        name="Amazon India",
        default_currency_code="INR",
    )
    product = Product(
        id=product_id,
        organisation_id=organisation.id,
        marketplace=marketplace,
        asin="B000SRC001",
        title="Synthetic sourcing product",
    )
    snapshot = ProductSnapshot(
        id=f"snapshot-{product_id}",
        product=product,
        snapshot_at=datetime(2026, 5, 1, tzinfo=UTC),
        observed_on=datetime(2026, 5, 1, tzinfo=UTC).date(),
        observed_on_source="user_confirmed",
        monthly_sold=monthly_demand,
    )
    session.add_all([organisation, marketplace, product, snapshot])
    if confidence is not None:
        session.add(
            ScoreResult(
                snapshot=snapshot,
                score_name="data_confidence",
                formula_version="selleros.market-opportunity.v1",
                configuration_checksum="synthetic-score-checksum",
                score_value=confidence,
                inputs={"source": "synthetic"},
                reason_codes=[],
                created_at=datetime(2026, 5, 1, tzinfo=UTC),
            )
        )
    session.flush()
    product.latest_snapshot_id = snapshot.id
    session.commit()
    return organisation, marketplace, product


def _offer_payload(product_id: str) -> dict[str, object]:
    today = datetime.now(UTC).date()
    return {
        "product_id": product_id,
        "supplier_name": "Synthetic Supplier",
        "currency_code": "INR",
        "unit_cost": "10.00",
        "minimum_order_quantity": 5,
        "lead_time_days": 20,
        "quotation_date": (today - timedelta(days=1)).isoformat(),
        "valid_until": (today + timedelta(days=365)).isoformat(),
        "notes": "Synthetic quotation only",
        "price_tiers": [{"minimum_quantity": 50, "unit_cost": "8.00"}],
    }


def test_offer_tiers_are_recorded_listed_and_compared_without_price_only_selection(
    db_session: Session,
) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="sourcing-org-a",
        marketplace_id="sourcing-market-a",
        product_id="sourcing-product-a",
    )
    scope = {
        "organisation_id": organisation.id,
        "marketplace_id": marketplace.id,
    }

    with _client(db_session) as client:
        created = client.post(
            "/api/v1/supplier-offers",
            params=scope,
            json=_offer_payload(product.id),
        )
        listed = client.get(
            f"/api/v1/products/{product.id}/supplier-offers",
            params={**scope, "page": 1, "page_size": 1},
        )
        unbounded = client.get(
            f"/api/v1/products/{product.id}/supplier-offers",
            params={**scope, "page_size": 101},
        )

    assert created.status_code == 201, created.text
    assert created.json()["price_tiers"] == [
        {"minimum_quantity": 5, "unit_cost": "10.0000"},
        {"minimum_quantity": 50, "unit_cost": "8.0000"},
    ]
    assert listed.status_code == 200
    assert listed.json()["product"]["product_id"] == product.id
    assert listed.json()["pagination"]["total_items"] == 1
    assert listed.json()["comparison_dimensions"] == [
        "unit_cost",
        "minimum_order_quantity",
        "lead_time_days",
    ]
    assert "does not select" in listed.json()["selection_note"]
    assert unbounded.status_code == 422


def test_test_buy_endpoint_persists_three_advisory_scenarios_and_audit(
    db_session: Session,
) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="sourcing-org-b",
        marketplace_id="sourcing-market-b",
        product_id="sourcing-product-b",
    )
    scope = {
        "organisation_id": organisation.id,
        "marketplace_id": marketplace.id,
    }

    with _client(db_session) as client:
        offer = client.post(
            "/api/v1/supplier-offers",
            params=scope,
            json=_offer_payload(product.id),
        )
        response = client.post(
            f"/api/v1/products/{product.id}/test-buy-scenarios",
            params=scope,
            json={
                "supplier_offer_id": offer.json()["id"],
                "budget_amount": "1000.00",
                "budget_currency_code": "INR",
            },
        )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["product"]["product_id"] == product.id
    assert payload["formula_version"] == "selleros.test-buy.v1"
    assert payload["advisory_only"] is True
    assert payload["outcome"] == "recommended"
    assert payload["decision_label"] == "recommended"
    assert [item["scenario"] for item in payload["scenarios"]] == [
        "conservative",
        "expected",
        "aggressive",
    ]
    assert [item["quantity"] for item in payload["scenarios"]] == [38, 80, 125]
    assert payload["evidence"]["monthly_demand_label"] == "estimated"
    assert payload["evidence"]["source_snapshot_id"] == f"snapshot-{product.id}"
    assert payload["evidence"]["data_confidence_score_result_id"] is not None
    assert "TEST_BUY_DEMAND_IS_ESTIMATED" in {notice["code"] for notice in payload["notices"]}
    recommendation = db_session.scalar(select(RecommendationRecord))
    assert recommendation is not None
    assert recommendation.advisory_only is True
    assert recommendation.outcome.value == "recommended"
    assert recommendation.source_snapshot_id == f"snapshot-{product.id}"
    assert recommendation.data_confidence_score_result_id is not None
    assert recommendation.evidence == payload["evidence"]
    assert len(recommendation.scenarios) == 3
    audit = db_session.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "test_buy.evaluated")
    )
    assert audit is not None
    assert audit.event_payload["advisory_only"] is True


def test_supplier_and_test_buy_reads_are_tenant_scoped(db_session: Session) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="sourcing-org-c",
        marketplace_id="sourcing-market-c",
        product_id="sourcing-product-c",
    )
    other_organisation, other_marketplace, other_product = _workspace(
        db_session,
        organisation_id="sourcing-org-d",
        marketplace_id="sourcing-market-d",
        product_id="sourcing-product-d",
    )
    scope = {
        "organisation_id": organisation.id,
        "marketplace_id": marketplace.id,
    }

    with _client(db_session) as client:
        offer = client.post(
            "/api/v1/supplier-offers",
            params=scope,
            json=_offer_payload(product.id),
        )
        cross_list = client.get(
            f"/api/v1/products/{product.id}/supplier-offers",
            params={
                "organisation_id": other_organisation.id,
                "marketplace_id": other_marketplace.id,
            },
        )
        cross_recommendation = client.post(
            f"/api/v1/products/{other_product.id}/test-buy-scenarios",
            params={
                "organisation_id": other_organisation.id,
                "marketplace_id": other_marketplace.id,
            },
            json={
                "supplier_offer_id": offer.json()["id"],
                "budget_amount": "1000.00",
                "budget_currency_code": "INR",
            },
        )

    assert cross_list.status_code == 404
    assert cross_recommendation.status_code == 404
    assert marketplace.organisation_id == organisation.id


def test_low_confidence_is_capped_through_the_api(db_session: Session) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="sourcing-org-e",
        marketplace_id="sourcing-market-e",
        product_id="sourcing-product-e",
        confidence=40,
    )
    scope = {
        "organisation_id": organisation.id,
        "marketplace_id": marketplace.id,
    }

    with _client(db_session) as client:
        offer = client.post(
            "/api/v1/supplier-offers",
            params=scope,
            json=_offer_payload(product.id),
        )
        response = client.post(
            f"/api/v1/products/{product.id}/test-buy-scenarios",
            params=scope,
            json={
                "supplier_offer_id": offer.json()["id"],
                "budget_amount": "1000.00",
                "budget_currency_code": "INR",
            },
        )

    assert response.status_code == 201
    assert [item["quantity"] for item in response.json()["scenarios"]] == [28, 28, 28]
    assert "TEST_BUY_LOW_CONFIDENCE_CAP_APPLIED" in {
        notice["code"] for notice in response.json()["notices"]
    }


def test_concurrent_supplier_name_conflict_returns_409_and_rolls_back(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="sourcing-org-race",
        marketplace_id="sourcing-market-race",
        product_id="sourcing-product-race",
    )
    scope = {
        "organisation_id": organisation.id,
        "marketplace_id": marketplace.id,
    }
    with _client(db_session) as client:
        first = client.post(
            "/api/v1/supplier-offers",
            params=scope,
            json=_offer_payload(product.id),
        )
    assert first.status_code == 201

    def duplicate_supplier(
        repository: SourcingRepository, organisation_id: str, name: str
    ) -> Supplier:
        supplier = Supplier(
            id="concurrent-duplicate-supplier",
            organisation_id=organisation_id,
            name=name,
        )
        repository.session.add(supplier)
        return supplier

    monkeypatch.setattr(SourcingRepository, "find_or_create_supplier", duplicate_supplier)
    with _client(db_session) as client:
        conflict = client.post(
            "/api/v1/supplier-offers",
            params=scope,
            json=_offer_payload(product.id),
        )

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "supplier_offer_conflict"
    assert db_session.scalar(select(func.count(Supplier.id))) == 1
    assert db_session.scalar(select(func.count(SupplierOffer.id))) == 1
    assert (
        db_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.event_type == "supplier_offer.recorded"
            )
        )
        == 1
    )


def test_supplier_offer_currency_must_match_marketplace(db_session: Session) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="sourcing-org-currency",
        marketplace_id="sourcing-market-currency",
        product_id="sourcing-product-currency",
    )
    payload = _offer_payload(product.id)
    payload["currency_code"] = "USD"

    with _client(db_session) as client:
        response = client.post(
            "/api/v1/supplier-offers",
            params={"organisation_id": organisation.id, "marketplace_id": marketplace.id},
            json=payload,
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "supplier_offer_currency_mismatch"
    assert db_session.scalar(select(func.count(SupplierOffer.id))) == 0


def test_sourcing_money_requires_decimal_strings(db_session: Session) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="sourcing-org-decimal-contract",
        marketplace_id="sourcing-market-decimal-contract",
        product_id="sourcing-product-decimal-contract",
    )
    payload = _offer_payload(product.id)
    payload["unit_cost"] = 10

    with _client(db_session) as client:
        response = client.post(
            "/api/v1/supplier-offers",
            params={"organisation_id": organisation.id, "marketplace_id": marketplace.id},
            json=payload,
        )

    assert response.status_code == 422


def test_offer_pagination_totals_and_pages_remain_reliable(db_session: Session) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="sourcing-org-pages",
        marketplace_id="sourcing-market-pages",
        product_id="sourcing-product-pages",
    )
    scope = {"organisation_id": organisation.id, "marketplace_id": marketplace.id}

    with _client(db_session) as client:
        for index in range(3):
            payload = _offer_payload(product.id)
            payload["supplier_name"] = f"Synthetic Supplier {index}"
            created = client.post("/api/v1/supplier-offers", params=scope, json=payload)
            assert created.status_code == 201
        first = client.get(
            f"/api/v1/products/{product.id}/supplier-offers",
            params={**scope, "page": 1, "page_size": 2},
        )
        second = client.get(
            f"/api/v1/products/{product.id}/supplier-offers",
            params={**scope, "page": 2, "page_size": 2},
        )

    assert first.json()["pagination"] == {
        "page": 1,
        "page_size": 2,
        "total_items": 3,
        "total_pages": 2,
        "has_previous": False,
        "has_next": True,
    }
    assert len(first.json()["items"]) == 2
    assert second.json()["pagination"]["total_items"] == 3
    assert second.json()["pagination"]["total_pages"] == 2
    assert second.json()["pagination"]["has_previous"] is True
    assert second.json()["pagination"]["has_next"] is False
    assert len(second.json()["items"]) == 1


def test_missing_demand_persists_blocked_provenance_without_estimated_label(
    db_session: Session,
) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="sourcing-org-no-demand",
        marketplace_id="sourcing-market-no-demand",
        product_id="sourcing-product-no-demand",
        monthly_demand=None,
    )
    scope = {"organisation_id": organisation.id, "marketplace_id": marketplace.id}
    with _client(db_session) as client:
        offer = client.post(
            "/api/v1/supplier-offers", params=scope, json=_offer_payload(product.id)
        )
        response = client.post(
            f"/api/v1/products/{product.id}/test-buy-scenarios",
            params=scope,
            json={
                "supplier_offer_id": offer.json()["id"],
                "budget_amount": "1000.00",
                "budget_currency_code": "INR",
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["outcome"] == "blocked"
    assert payload["decision_label"] is None
    assert all(item["status"] == "blocked" for item in payload["scenarios"])
    assert payload["evidence"]["monthly_demand_units"] is None
    assert payload["evidence"]["monthly_demand_label"] is None
    assert payload["evidence"]["monthly_demand_source"] is None
    assert "TEST_BUY_DEMAND_IS_ESTIMATED" not in {notice["code"] for notice in payload["notices"]}
    record = db_session.scalar(select(RecommendationRecord))
    assert record is not None
    assert record.outcome.value == "blocked"
    assert record.source_snapshot_id == f"snapshot-{product.id}"
    assert record.data_confidence_score_result_id is not None
    assert record.evidence["monthly_demand_label"] is None


def test_legacy_undated_snapshot_is_excluded_from_test_buy_evidence(
    db_session: Session,
) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="sourcing-org-undated",
        marketplace_id="sourcing-market-undated",
        product_id="sourcing-product-undated",
    )
    legacy_snapshot = ProductSnapshot(
        id=f"legacy-snapshot-{product.id}",
        product=product,
        snapshot_at=datetime(2026, 5, 3, tzinfo=UTC),
        monthly_sold=500,
    )
    db_session.add(legacy_snapshot)
    db_session.flush()
    product.latest_snapshot_id = legacy_snapshot.id
    db_session.commit()
    scope = {"organisation_id": organisation.id, "marketplace_id": marketplace.id}

    with _client(db_session) as client:
        offer = client.post(
            "/api/v1/supplier-offers", params=scope, json=_offer_payload(product.id)
        )
        response = client.post(
            f"/api/v1/products/{product.id}/test-buy-scenarios",
            params=scope,
            json={
                "supplier_offer_id": offer.json()["id"],
                "budget_amount": "1000.00",
                "budget_currency_code": "INR",
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["outcome"] == "blocked"
    assert payload["evidence"]["source_snapshot_id"] is None
    assert payload["evidence"]["market_observed_on"] is None
    assert payload["evidence"]["monthly_demand_units"] is None
    assert "TEST_BUY_OBSERVATION_DATE_UNCONFIRMED" in {
        notice["code"] for notice in payload["notices"]
    }


def test_missing_confidence_has_no_calculated_evidence_label(db_session: Session) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="sourcing-org-no-confidence",
        marketplace_id="sourcing-market-no-confidence",
        product_id="sourcing-product-no-confidence",
        confidence=None,
    )
    scope = {"organisation_id": organisation.id, "marketplace_id": marketplace.id}
    with _client(db_session) as client:
        offer = client.post(
            "/api/v1/supplier-offers", params=scope, json=_offer_payload(product.id)
        )
        response = client.post(
            f"/api/v1/products/{product.id}/test-buy-scenarios",
            params=scope,
            json={
                "supplier_offer_id": offer.json()["id"],
                "budget_amount": "1000.00",
                "budget_currency_code": "INR",
            },
        )

    assert response.status_code == 201
    evidence = response.json()["evidence"]
    assert response.json()["outcome"] == "blocked"
    assert evidence["data_confidence_score"] is None
    assert evidence["data_confidence_score_result_id"] is None
    assert evidence["data_confidence_formula_version"] is None
    assert evidence["data_confidence_label"] is None


def test_negative_imported_demand_is_retained_as_evidence_but_fails_closed(
    db_session: Session,
) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="sourcing-org-negative-demand",
        marketplace_id="sourcing-market-negative-demand",
        product_id="sourcing-product-negative-demand",
        monthly_demand=-5,
    )
    scope = {"organisation_id": organisation.id, "marketplace_id": marketplace.id}
    with _client(db_session) as client:
        offer = client.post(
            "/api/v1/supplier-offers", params=scope, json=_offer_payload(product.id)
        )
        response = client.post(
            f"/api/v1/products/{product.id}/test-buy-scenarios",
            params=scope,
            json={
                "supplier_offer_id": offer.json()["id"],
                "budget_amount": "1000.00",
                "budget_currency_code": "INR",
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["outcome"] == "blocked"
    assert payload["decision_label"] is None
    assert payload["inputs"]["monthly_demand_units"] is None
    assert payload["evidence"]["monthly_demand_units"] == -5
    assert payload["evidence"]["monthly_demand_label"] is None
    assert payload["evidence"]["monthly_demand_source"] == "keepa_monthly_sold"
    assert "TEST_BUY_MONTHLY_DEMAND_INVALID" in {notice["code"] for notice in payload["notices"]}
    assert "TEST_BUY_DEMAND_IS_ESTIMATED" not in {notice["code"] for notice in payload["notices"]}
    record = db_session.scalar(select(RecommendationRecord))
    assert record is not None
    assert record.evidence["monthly_demand_units"] == -5


def test_supplier_name_at_quote_survives_master_supplier_rename(db_session: Session) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="sourcing-org-name-snapshot",
        marketplace_id="sourcing-market-name-snapshot",
        product_id="sourcing-product-name-snapshot",
    )
    scope = {"organisation_id": organisation.id, "marketplace_id": marketplace.id}
    with _client(db_session) as client:
        created = client.post(
            "/api/v1/supplier-offers", params=scope, json=_offer_payload(product.id)
        )
    supplier = db_session.scalar(select(Supplier))
    assert supplier is not None
    supplier.name = "Renamed Supplier Master"
    db_session.commit()

    with _client(db_session) as client:
        listed = client.get(f"/api/v1/products/{product.id}/supplier-offers", params=scope)

    assert created.json()["supplier"]["name"] == "Synthetic Supplier"
    assert listed.json()["items"][0]["supplier"] == {
        "id": supplier.id,
        "name": "Synthetic Supplier",
    }


def test_price_tier_cannot_be_appended_to_persisted_offer(db_session: Session) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="sourcing-org-tier-guard",
        marketplace_id="sourcing-market-tier-guard",
        product_id="sourcing-product-tier-guard",
    )
    scope = {"organisation_id": organisation.id, "marketplace_id": marketplace.id}
    with _client(db_session) as client:
        created = client.post(
            "/api/v1/supplier-offers", params=scope, json=_offer_payload(product.id)
        )
    offer = db_session.get(SupplierOffer, created.json()["id"])
    assert offer is not None
    offer_id = offer.id
    offer.price_tiers.append(
        SupplierOfferPriceTier(minimum_quantity=100, unit_cost=Decimal("7.00"))
    )

    with pytest.raises(ValueError, match="immutable|only be inserted"):
        db_session.flush()
    db_session.rollback()

    db_session.add(
        SupplierOfferPriceTier(
            supplier_offer_id=offer_id,
            minimum_quantity=100,
            unit_cost=Decimal("7.00"),
        )
    )
    with pytest.raises(ValueError, match="only be inserted with a new supplier quotation"):
        db_session.flush()
