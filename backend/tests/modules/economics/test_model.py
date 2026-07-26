from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.domain import AuditEvent, CostProfile, Marketplace, Organisation, Product


def test_database_rejects_mismatched_product_cost_scope_key(db_session: Session) -> None:
    organisation = Organisation(id="scope-integrity-org", name="Scope integrity seller")
    marketplace = Marketplace(
        id="scope-integrity-market",
        organisation=organisation,
        code="IN",
        name="Amazon India",
        default_currency_code="INR",
    )
    product = Product(
        id="scope-integrity-product",
        organisation_id=organisation.id,
        marketplace=marketplace,
        asin="B000SCOPE1",
    )
    db_session.add_all([organisation, marketplace, product])
    db_session.flush()
    db_session.add(
        CostProfile(
            organisation_id=organisation.id,
            marketplace_id=marketplace.id,
            product_id=product.id,
            profile_scope_key="marketplace_default",
            version=1,
            currency_code="INR",
            selling_price_tax_basis="tax_exclusive",
            supplier_unit_cost=Decimal("1.00"),
            configuration_checksum="synthetic-scope-integrity",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def _persisted_profile(db_session: Session, *, suffix: str) -> CostProfile:
    organisation = Organisation(id=f"append-org-{suffix}", name="Append-only seller")
    marketplace = Marketplace(
        id=f"append-market-{suffix}",
        organisation=organisation,
        code="IN",
        name="Amazon India",
        default_currency_code="INR",
    )
    product = Product(
        id=f"append-product-{suffix}",
        organisation_id=organisation.id,
        marketplace=marketplace,
        asin=(f"B{suffix.upper()}000000000")[:10],
    )
    profile = CostProfile(
        id=f"append-profile-{suffix}",
        organisation_id=organisation.id,
        marketplace_id=marketplace.id,
        product_id=product.id,
        profile_scope_key=product.id,
        version=1,
        currency_code="INR",
        selling_price_tax_basis="tax_exclusive",
        supplier_unit_cost=Decimal("10.00"),
        configuration_checksum=f"synthetic-{suffix}",
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
    )
    db_session.add_all([organisation, marketplace, product, profile])
    db_session.commit()
    return profile


def test_new_orm_cost_profile_cannot_omit_tax_basis(db_session: Session) -> None:
    organisation = Organisation(id="tax-guard-org", name="Tax guard seller")
    marketplace = Marketplace(
        id="tax-guard-market",
        organisation=organisation,
        code="IN",
        name="Amazon India",
        default_currency_code="INR",
    )
    product = Product(
        id="tax-guard-product",
        organisation_id=organisation.id,
        marketplace=marketplace,
        asin="B000TAXGRD",
    )
    db_session.add_all([organisation, marketplace, product])
    db_session.flush()
    db_session.add(
        CostProfile(
            organisation_id=organisation.id,
            marketplace_id=marketplace.id,
            product_id=product.id,
            profile_scope_key=product.id,
            version=1,
            currency_code="INR",
            supplier_unit_cost=Decimal("1.00"),
            configuration_checksum="synthetic-tax-guard",
        )
    )

    with pytest.raises(ValueError, match="explicit selling-price tax basis"):
        db_session.flush()


def test_cost_profile_only_allows_one_time_utc_closure(db_session: Session) -> None:
    profile = _persisted_profile(db_session, suffix="closure")
    profile_id = profile.id
    profile.effective_to = datetime(2026, 2, 1, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    with pytest.raises(ValueError, match="one-time UTC"):
        db_session.flush()
    db_session.rollback()

    retained = db_session.get(CostProfile, profile_id)
    assert retained is not None
    retained.effective_to = datetime(2026, 2, 1, tzinfo=UTC)
    db_session.commit()

    retained.effective_to = datetime(2026, 3, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="one-time UTC"):
        db_session.flush()
    db_session.rollback()


def test_cost_profile_rejects_other_updates_and_deletes(db_session: Session) -> None:
    profile = _persisted_profile(db_session, suffix="mutation")
    profile_id = profile.id
    profile.supplier_unit_cost = Decimal("11.00")
    with pytest.raises(ValueError, match="append-only"):
        db_session.flush()
    db_session.rollback()

    retained = db_session.get(CostProfile, profile_id)
    assert retained is not None
    db_session.delete(retained)
    with pytest.raises(ValueError, match="append-only"):
        db_session.flush()


def test_audit_events_reject_updates_and_deletes(db_session: Session) -> None:
    organisation = Organisation(id="audit-immutable-org", name="Audit immutable seller")
    db_session.add(organisation)
    db_session.flush()
    event = AuditEvent(
        id="audit-immutable-event",
        organisation_id=organisation.id,
        event_type="synthetic.created",
        entity_type="synthetic",
        entity_id="synthetic-entity",
    )
    db_session.add(event)
    db_session.commit()
    event_id = event.id

    event.event_type = "synthetic.changed"
    with pytest.raises(ValueError, match="Audit events are immutable"):
        db_session.flush()
    db_session.rollback()

    retained = db_session.get(AuditEvent, event_id)
    assert retained is not None
    db_session.delete(retained)
    with pytest.raises(ValueError, match="Audit events are immutable"):
        db_session.flush()
