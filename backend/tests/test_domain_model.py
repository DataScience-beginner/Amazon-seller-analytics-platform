from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.domain import (
    CostProfile,
    Marketplace,
    Organisation,
    Product,
    ProductSnapshot,
    RawAttribute,
)


def test_database_can_create_canonical_tables(db_session: Session) -> None:
    organisation = Organisation(name="Synthetic Seller")
    db_session.add(organisation)
    db_session.commit()

    assert organisation.id is not None


def test_product_unique_by_organisation_marketplace_and_asin(db_session: Session) -> None:
    organisation = Organisation(name="Synthetic Seller")
    marketplace = Marketplace(
        organisation=organisation, code="IN", name="Amazon India", default_currency_code="INR"
    )
    db_session.add_all([organisation, marketplace])
    db_session.flush()
    db_session.add_all(
        [
            Product(
                organisation_id=organisation.id, marketplace_id=marketplace.id, asin="B000TEST01"
            ),
            Product(
                organisation_id=organisation.id, marketplace_id=marketplace.id, asin="B000TEST01"
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_cost_profiles_are_structurally_separate_from_snapshots(db_session: Session) -> None:
    organisation = Organisation(name="Synthetic Seller")
    marketplace = Marketplace(
        organisation=organisation, code="US", name="Amazon US", default_currency_code="USD"
    )
    db_session.add(organisation)
    db_session.flush()
    product = Product(organisation_id=organisation.id, marketplace=marketplace, asin="B000TEST02")
    snapshot = ProductSnapshot(product=product, market_metrics={"buy_box_price": "19.99"})
    cost = CostProfile(
        organisation_id=organisation.id,
        product=product,
        currency_code="USD",
        supplier_unit_cost=Decimal("7.50"),
    )
    raw = RawAttribute(snapshot=snapshot, source_header="Unexpected Keepa Column", value="kept")
    db_session.add_all([organisation, marketplace, product, snapshot, cost, raw])
    db_session.commit()

    assert snapshot.market_metrics == {"buy_box_price": "19.99"}
    assert cost.supplier_unit_cost == Decimal("7.50")
    assert raw.value == "kept"
    assert not hasattr(snapshot, "supplier_unit_cost")


def test_product_snapshots_cannot_be_updated_or_deleted(db_session: Session) -> None:
    organisation = Organisation(name="Synthetic Seller")
    marketplace = Marketplace(
        organisation=organisation, code="GB", name="Amazon UK", default_currency_code="GBP"
    )
    db_session.add(organisation)
    db_session.flush()
    product = Product(organisation_id=organisation.id, marketplace=marketplace, asin="B000TEST03")
    snapshot = ProductSnapshot(product=product, market_metrics={"buy_box_price": "20.00"})
    db_session.add(snapshot)
    db_session.commit()

    snapshot.market_metrics = {"buy_box_price": "18.00"}
    with pytest.raises(ValueError, match="Product snapshots are immutable"):
        db_session.commit()

    db_session.rollback()
    db_session.delete(snapshot)
    with pytest.raises(ValueError, match="Product snapshots are immutable"):
        db_session.commit()
