from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.core.errors import ApplicationError
from app.db.session import get_db
from app.models.domain import (
    AuditEvent,
    CostProfile,
    Marketplace,
    Organisation,
    Product,
    ProductSnapshot,
)
from app.modules.economics.api import router as economics_router
from app.modules.economics.repository import EconomicsRepository


@contextmanager
def _client(session: Session) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(economics_router, prefix="/api/v1")

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
    session: Session, *, organisation_id: str, marketplace_id: str, product_id: str
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
        organisation_id=organisation_id,
        marketplace=marketplace,
        asin="B000ECON01",
        title="Synthetic economics product",
    )
    snapshot = ProductSnapshot(
        id=f"snapshot-{product_id}",
        product=product,
        snapshot_at=datetime(2026, 5, 1, tzinfo=UTC),
        observed_on=datetime(2026, 5, 1, tzinfo=UTC).date(),
        observed_on_source="user_confirmed",
        buy_box_price=Decimal("100.00"),
        currency_code="INR",
    )
    session.add_all([organisation, marketplace, product, snapshot])
    session.flush()
    product.latest_snapshot_id = snapshot.id
    session.commit()
    return organisation, marketplace, product


def _profile_payload(
    *, product_id: str | None = None, effective_from: str = "2026-01-01T00:00:00Z"
) -> dict[str, object]:
    return {
        "product_id": product_id,
        "currency_code": "INR",
        "selling_price_tax_basis": "tax_exclusive",
        "purchase_cost": "40.00",
        "gst_rate_percent": "10.00",
        "gst_recoverable_percent": "50.00",
        "freight_cost": "3.00",
        "prep_cost": "2.00",
        "packaging_cost": "1.00",
        "advertising_rate_percent": "5.00",
        "returns_rate_percent": "2.00",
        "overhead_cost": "2.00",
        "referral_fee_rate_percent": "15.00",
        "fulfilment_fee": "5.00",
        "closing_fee": "1.00",
        "storage_fee": "1.00",
        "fee_source": "Synthetic Amazon fee schedule",
        "fee_effective_at": "2026-01-01T00:00:00Z",
        "fee_status": "observed",
        "minimum_margin_percent": "10.00",
        "target_margin_percent": "20.00",
        "effective_from": effective_from,
    }


def test_marketplace_default_profile_calculates_traced_economics(db_session: Session) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="economics-org-a",
        marketplace_id="economics-market-a",
        product_id="economics-product-a",
    )
    scope = {
        "organisation_id": organisation.id,
        "marketplace_id": marketplace.id,
    }

    with _client(db_session) as client:
        created = client.post(
            "/api/v1/cost-profiles",
            params=scope,
            json=_profile_payload(),
        )
        response = client.get(
            f"/api/v1/products/{product.id}/economics",
            params=scope,
        )

    assert created.status_code == 201, created.text
    assert created.json()["scope"] == "marketplace_default"
    assert created.json()["selling_price_tax_basis"] == "tax_exclusive"
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["product"] == {
        "product_id": product.id,
        "asin": product.asin,
        "title": product.title,
    }
    assert payload["observed_price"]["evidence_label"] == "observed"
    assert payload["profile_source"] == "marketplace_default"
    assert payload["profiles_by_scope"]["product"] is None
    assert payload["profiles_by_scope"]["marketplace_default"]["id"] == created.json()["id"]
    assert payload["active_profile"]["evidence_label"] == "user_confirmed"
    assert payload["calculation"]["formula_version"] == "selleros.unit-economics.v2"
    assert payload["calculation"]["selling_price_tax_basis"] == "tax_exclusive"
    assert payload["calculation"]["decision_label"] == "calculated"
    assert payload["calculation"]["outputs"] == {
        "landed_cost": "48.00",
        "net_revenue": "100.00",
        "output_gst": "0.00",
        "amazon_fees": "22.00",
        "contribution_profit": "21.00",
        "margin_percent": "21.00",
        "roi_percent": "43.75",
        "break_even_price": "73.08",
        "minimum_acceptable_price": "83.82",
        "target_price": "98.28",
    }
    assert payload["calculation"]["inputs"]["purchase_cost"] == "40.0000"
    assert payload["calculation"]["fee_evidence"]["source"] == ("Synthetic Amazon fee schedule")
    assert payload["audit_history"][0]["event_type"] == "cost_profile.created"


def test_product_profile_revisions_are_effective_dated_and_audited(db_session: Session) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="economics-org-b",
        marketplace_id="economics-market-b",
        product_id="economics-product-b",
    )
    scope = {
        "organisation_id": organisation.id,
        "marketplace_id": marketplace.id,
    }

    with _client(db_session) as client:
        first = client.post(
            "/api/v1/cost-profiles",
            params=scope,
            json=_profile_payload(product_id=product.id),
        )
        second_payload = _profile_payload(
            product_id=product.id,
            effective_from="2026-02-01T00:00:00Z",
        )
        second_payload["purchase_cost"] = "45.00"
        second = client.post(
            "/api/v1/cost-profiles",
            params=scope,
            json=second_payload,
        )
        response = client.get(
            f"/api/v1/products/{product.id}/economics",
            params=scope,
        )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json()["version"] == 2
    assert second.json()["supersedes_profile_id"] == first.json()["id"]
    payload = response.json()
    assert payload["profile_source"] == "product"
    assert payload["active_profile"]["purchase_cost"] == "45.0000"
    history = {item["version"]: item for item in payload["profile_history"]}
    assert history[1]["effective_to"] == "2026-02-01T00:00:00Z"
    assert [event["event_type"] for event in payload["audit_history"][:2]] == [
        "cost_profile.revised",
        "cost_profile.created",
    ]


def test_missing_fees_remain_partial_and_binary_floats_are_rejected(
    db_session: Session,
) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="economics-org-c",
        marketplace_id="economics-market-c",
        product_id="economics-product-c",
    )
    scope = {
        "organisation_id": organisation.id,
        "marketplace_id": marketplace.id,
    }
    missing_fee_payload = _profile_payload(product_id=product.id)
    for field in (
        "referral_fee_rate_percent",
        "fulfilment_fee",
        "closing_fee",
        "storage_fee",
        "fee_source",
        "fee_effective_at",
        "fee_status",
    ):
        missing_fee_payload[field] = None
    float_payload = _profile_payload(product_id=product.id)
    float_payload["purchase_cost"] = 40.5
    integer_payload = _profile_payload(product_id=product.id)
    integer_payload["purchase_cost"] = 40

    with _client(db_session) as client:
        created = client.post(
            "/api/v1/cost-profiles",
            params=scope,
            json=missing_fee_payload,
        )
        response = client.get(
            f"/api/v1/products/{product.id}/economics",
            params=scope,
        )
        rejected = client.post(
            "/api/v1/cost-profiles",
            params=scope,
            json=float_payload,
        )
        rejected_integer = client.post(
            "/api/v1/cost-profiles",
            params=scope,
            json=integer_payload,
        )

    assert created.status_code == 201
    assert response.json()["calculation"]["status"] == "partial"
    assert response.json()["calculation"]["outputs"]["amazon_fees"] is None
    assert "ECONOMICS_FEE_INPUTS_MISSING" in {
        notice["code"] for notice in response.json()["notices"]
    }
    assert rejected.status_code == 422
    assert rejected_integer.status_code == 422


def test_economics_never_crosses_organisation_or_marketplace_scope(
    db_session: Session,
) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="economics-org-d",
        marketplace_id="economics-market-d",
        product_id="economics-product-d",
    )
    other_organisation, other_marketplace, _ = _workspace(
        db_session,
        organisation_id="economics-org-e",
        marketplace_id="economics-market-e",
        product_id="economics-product-e",
    )

    with _client(db_session) as client:
        crossed_marketplace = client.get(
            f"/api/v1/products/{product.id}/economics",
            params={
                "organisation_id": organisation.id,
                "marketplace_id": other_marketplace.id,
            },
        )
        crossed_product = client.get(
            f"/api/v1/products/{product.id}/economics",
            params={
                "organisation_id": other_organisation.id,
                "marketplace_id": other_marketplace.id,
            },
        )

    assert crossed_marketplace.status_code == 404
    assert crossed_product.status_code == 404
    assert marketplace.organisation_id == organisation.id


def test_concurrent_first_profile_conflict_returns_409_and_rolls_back(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="economics-org-race",
        marketplace_id="economics-market-race",
        product_id="economics-product-race",
    )
    scope = {
        "organisation_id": organisation.id,
        "marketplace_id": marketplace.id,
    }
    with _client(db_session) as client:
        first = client.post(
            "/api/v1/cost-profiles",
            params=scope,
            json=_profile_payload(product_id=product.id),
        )
    assert first.status_code == 201

    monkeypatch.setattr(
        EconomicsRepository,
        "current_revision",
        lambda _self, _organisation_id, _marketplace_id, _scope_key: None,
    )
    with _client(db_session) as client:
        conflict = client.post(
            "/api/v1/cost-profiles",
            params=scope,
            json=_profile_payload(
                product_id=product.id,
                effective_from="2026-02-01T00:00:00Z",
            ),
        )

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "cost_profile_revision_conflict"
    assert db_session.scalar(select(func.count(CostProfile.id))) == 1
    assert (
        db_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.event_type.in_(["cost_profile.created", "cost_profile.revised"])
            )
        )
        == 1
    )
    retained = db_session.scalar(select(CostProfile))
    assert retained is not None
    assert retained.effective_to is None


def test_product_and_marketplace_profiles_are_resolved_independently(
    db_session: Session,
) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="economics-org-both",
        marketplace_id="economics-market-both",
        product_id="economics-product-both",
    )
    scope = {"organisation_id": organisation.id, "marketplace_id": marketplace.id}

    with _client(db_session) as client:
        marketplace_default = client.post(
            "/api/v1/cost-profiles", params=scope, json=_profile_payload()
        )
        product_specific = client.post(
            "/api/v1/cost-profiles",
            params=scope,
            json=_profile_payload(product_id=product.id),
        )
        response = client.get(f"/api/v1/products/{product.id}/economics", params=scope)

    assert marketplace_default.status_code == 201
    assert product_specific.status_code == 201
    payload = response.json()
    assert payload["profile_source"] == "product"
    assert payload["active_profile"]["id"] == product_specific.json()["id"]
    assert payload["profiles_by_scope"]["product"]["id"] == product_specific.json()["id"]
    assert (
        payload["profiles_by_scope"]["marketplace_default"]["id"]
        == (marketplace_default.json()["id"])
    )


def test_tax_inclusive_profile_exposes_net_revenue_and_output_gst(db_session: Session) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="economics-org-tax",
        marketplace_id="economics-market-tax",
        product_id="economics-product-tax",
    )
    snapshot = db_session.get(ProductSnapshot, f"snapshot-{product.id}")
    assert snapshot is not None
    # Imported evidence is immutable, so create a fresh tax-inclusive observed-price snapshot.
    inclusive_snapshot = ProductSnapshot(
        id=f"inclusive-snapshot-{product.id}",
        product=product,
        snapshot_at=datetime(2026, 5, 2, tzinfo=UTC),
        observed_on=datetime(2026, 5, 2, tzinfo=UTC).date(),
        observed_on_source="user_confirmed",
        buy_box_price=Decimal("110.00"),
        currency_code="INR",
    )
    db_session.add(inclusive_snapshot)
    db_session.flush()
    product.latest_snapshot_id = inclusive_snapshot.id
    db_session.commit()
    scope = {"organisation_id": organisation.id, "marketplace_id": marketplace.id}
    profile_payload = _profile_payload(product_id=product.id)
    profile_payload["selling_price_tax_basis"] = "tax_inclusive"

    with _client(db_session) as client:
        created = client.post("/api/v1/cost-profiles", params=scope, json=profile_payload)
        response = client.get(f"/api/v1/products/{product.id}/economics", params=scope)

    assert created.status_code == 201
    calculation = response.json()["calculation"]
    assert calculation["selling_price_tax_basis"] == "tax_inclusive"
    assert calculation["outputs"]["net_revenue"] == "100.00"
    assert calculation["outputs"]["output_gst"] == "10.00"


def test_negative_imported_price_is_preserved_but_excluded_from_economics(
    db_session: Session,
) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="economics-org-negative-price",
        marketplace_id="economics-market-negative-price",
        product_id="economics-product-negative-price",
    )
    negative_snapshot = ProductSnapshot(
        id=f"negative-snapshot-{product.id}",
        product=product,
        snapshot_at=datetime(2026, 5, 2, tzinfo=UTC),
        observed_on=datetime(2026, 5, 2, tzinfo=UTC).date(),
        observed_on_source="user_confirmed",
        buy_box_price=Decimal("-1.00"),
        currency_code="INR",
    )
    db_session.add(negative_snapshot)
    db_session.flush()
    product.latest_snapshot_id = negative_snapshot.id
    db_session.commit()
    scope = {"organisation_id": organisation.id, "marketplace_id": marketplace.id}

    with _client(db_session) as client:
        created = client.post(
            "/api/v1/cost-profiles",
            params=scope,
            json=_profile_payload(product_id=product.id),
        )
        response = client.get(f"/api/v1/products/{product.id}/economics", params=scope)

    assert created.status_code == 201
    assert response.status_code == 200
    payload = response.json()
    assert payload["observed_price"]["amount"] == "-1.00"
    assert payload["calculation"]["status"] == "partial"
    assert payload["calculation"]["inputs"]["selling_price"] is None
    assert payload["calculation"]["outputs"]["net_revenue"] is None
    assert payload["calculation"]["outputs"]["contribution_profit"] is None
    assert payload["calculation"]["outputs"]["break_even_price"] is not None
    assert "ECONOMICS_SELLING_PRICE_INVALID" in {notice["code"] for notice in payload["notices"]}


def test_legacy_undated_snapshot_is_not_used_as_observed_economics(
    db_session: Session,
) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="economics-org-undated",
        marketplace_id="economics-market-undated",
        product_id="economics-product-undated",
    )
    legacy_snapshot = ProductSnapshot(
        id=f"legacy-snapshot-{product.id}",
        product=product,
        snapshot_at=datetime(2026, 5, 3, tzinfo=UTC),
        buy_box_price=Decimal("120.00"),
        currency_code="INR",
    )
    db_session.add(legacy_snapshot)
    db_session.flush()
    product.latest_snapshot_id = legacy_snapshot.id
    db_session.commit()
    scope = {"organisation_id": organisation.id, "marketplace_id": marketplace.id}

    with _client(db_session) as client:
        created = client.post(
            "/api/v1/cost-profiles",
            params=scope,
            json=_profile_payload(product_id=product.id),
        )
        response = client.get(f"/api/v1/products/{product.id}/economics", params=scope)

    assert created.status_code == 201
    assert response.status_code == 200
    payload = response.json()
    assert payload["observed_price"] is None
    assert payload["calculation"]["inputs"]["selling_price"] is None
    assert "ECONOMICS_OBSERVATION_DATE_UNCONFIRMED" in {
        notice["code"] for notice in payload["notices"]
    }


def test_legacy_null_tax_basis_fails_closed_without_inference(db_session: Session) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="economics-org-legacy-tax",
        marketplace_id="economics-market-legacy-tax",
        product_id="economics-product-legacy-tax",
    )
    db_session.execute(
        insert(CostProfile).values(
            id="legacy-null-tax-profile",
            organisation_id=organisation.id,
            marketplace_id=marketplace.id,
            product_id=product.id,
            profile_scope_key=product.id,
            version=1,
            currency_code="INR",
            selling_price_tax_basis=None,
            supplier_unit_cost=Decimal("40.00"),
            freight_cost=Decimal("3.00"),
            prep_packaging_cost=Decimal("3.00"),
            prep_cost=Decimal("2.00"),
            packaging_cost=Decimal("1.00"),
            gst_rate_percent=Decimal("10.00"),
            gst_recoverable_percent=Decimal("50.00"),
            advertising_rate_percent=Decimal("5.00"),
            returns_rate_percent=Decimal("2.00"),
            overhead_cost=Decimal("2.00"),
            referral_fee_rate_percent=Decimal("15.00"),
            fulfilment_fee=Decimal("5.00"),
            closing_fee=Decimal("1.00"),
            storage_fee=Decimal("1.00"),
            minimum_margin_percent=Decimal("10.00"),
            target_margin_percent=Decimal("20.00"),
            configuration_checksum="legacy-unverified",
            effective_from=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    db_session.commit()
    scope = {"organisation_id": organisation.id, "marketplace_id": marketplace.id}

    with _client(db_session) as client:
        response = client.get(f"/api/v1/products/{product.id}/economics", params=scope)

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_profile"]["selling_price_tax_basis"] is None
    calculation = payload["calculation"]
    assert calculation["status"] == "partial"
    assert calculation["selling_price_tax_basis"] is None
    assert calculation["decision_label"] == "calculated"
    assert calculation["outputs"]["landed_cost"] == "48.00"
    for field in (
        "net_revenue",
        "output_gst",
        "amazon_fees",
        "contribution_profit",
        "margin_percent",
        "roi_percent",
        "break_even_price",
        "minimum_acceptable_price",
        "target_price",
    ):
        assert calculation["outputs"][field] is None
    assert "ECONOMICS_SELLING_PRICE_TAX_BASIS_MISSING" in calculation["reason_codes"]


def test_new_cost_profile_requires_explicit_tax_basis(db_session: Session) -> None:
    organisation, marketplace, product = _workspace(
        db_session,
        organisation_id="economics-org-required-tax",
        marketplace_id="economics-market-required-tax",
        product_id="economics-product-required-tax",
    )
    scope = {"organisation_id": organisation.id, "marketplace_id": marketplace.id}
    payload = _profile_payload(product_id=product.id)
    del payload["selling_price_tax_basis"]

    with _client(db_session) as client:
        response = client.post("/api/v1/cost-profiles", params=scope, json=payload)

    assert response.status_code == 422
