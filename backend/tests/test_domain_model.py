from datetime import UTC
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
    ScoreResult,
    StrategyRecommendation,
)


def test_database_can_create_canonical_tables(db_session: Session) -> None:
    organisation = Organisation(name="Synthetic Seller")
    db_session.add(organisation)
    db_session.commit()

    assert organisation.id is not None
    db_session.expire(organisation, ["created_at"])
    assert organisation.created_at.tzinfo is UTC


def test_sqlite_enforces_foreign_keys(db_session: Session) -> None:
    organisation = Organisation(name="Synthetic Seller")
    db_session.add(organisation)
    db_session.flush()
    db_session.add(
        Product(
            organisation_id=organisation.id,
            marketplace_id="missing-marketplace",
            asin="B000TEST00",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


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
    product = Product(
        id="product-cost-separation",
        organisation_id=organisation.id,
        marketplace=marketplace,
        asin="B000TEST02",
    )
    snapshot = ProductSnapshot(product=product, market_metrics={"buy_box_price": "19.99"})
    cost = CostProfile(
        organisation_id=organisation.id,
        marketplace_id=marketplace.id,
        product=product,
        profile_scope_key=product.id,
        version=1,
        currency_code="USD",
        selling_price_tax_basis="tax_exclusive",
        supplier_unit_cost=Decimal("7.50"),
        configuration_checksum="synthetic-checksum",
    )
    raw = RawAttribute(
        snapshot=snapshot,
        source_column_ordinal=1,
        source_header="Unexpected Keepa Column",
        value="kept",
    )
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


def test_imported_snapshot_evidence_cannot_be_updated_or_deleted(
    db_session: Session,
) -> None:
    organisation = Organisation(name="Evidence Seller")
    marketplace = Marketplace(
        organisation=organisation,
        code="AU",
        name="Amazon Australia",
        default_currency_code="AUD",
    )
    db_session.add(organisation)
    db_session.flush()
    product = Product(
        organisation_id=organisation.id,
        marketplace=marketplace,
        asin="B000TEST04",
    )
    snapshot = ProductSnapshot(product=product, market_metrics={})
    raw = RawAttribute(
        snapshot=snapshot,
        source_column_ordinal=1,
        source_header="Unexpected Keepa Column",
        value="original",
    )
    score = ScoreResult(
        snapshot=snapshot,
        score_name="demand",
        formula_version="selleros.market-opportunity.v1",
        configuration_checksum="a" * 64,
        score_value=50,
        inputs={},
        reason_codes=[],
    )
    recommendation = StrategyRecommendation(
        snapshot=snapshot,
        strategy="monitor",
        rules_version="strategy-v1.0.0",
        configuration_checksum="b" * 64,
        confidence_score=50,
        evidence=[],
    )
    db_session.add_all([organisation, marketplace, product, snapshot, raw, score, recommendation])
    db_session.commit()

    next_score_version = ScoreResult(
        score_name="demand",
        formula_version="selleros.market-opportunity.v2",
        configuration_checksum="c" * 64,
        score_value=55,
        inputs={},
        reason_codes=[],
    )
    next_strategy_version = StrategyRecommendation(
        strategy="monitor",
        rules_version="strategy-v2.0.0",
        configuration_checksum="d" * 64,
        confidence_score=55,
        evidence=[],
    )
    snapshot.score_results.append(next_score_version)
    snapshot.recommendations.append(next_strategy_version)
    db_session.commit()
    assert next_score_version.id is not None
    assert next_strategy_version.id is not None

    changes = (
        (raw, "value", "changed"),
        (score, "score_value", 75),
        (recommendation, "strategy", "avoid"),
    )
    for evidence, attribute, changed_value in changes:
        setattr(evidence, attribute, changed_value)
        with pytest.raises(ValueError, match="Imported snapshot evidence is immutable"):
            db_session.commit()
        db_session.rollback()
        db_session.refresh(evidence)

        db_session.delete(evidence)
        with pytest.raises(ValueError, match="Imported snapshot evidence is immutable"):
            db_session.commit()
        db_session.rollback()
        db_session.refresh(evidence)
