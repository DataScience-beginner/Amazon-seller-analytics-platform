from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class ImportStatus(StrEnum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class SnapshotKind(StrEnum):
    keepa = "keepa"
    manual = "manual"


class Organisation(Base):
    __tablename__ = "organisations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    users: Mapped[list[User]] = relationship(back_populates="organisation")
    marketplaces: Mapped[list[Marketplace]] = relationship(back_populates="organisation")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("organisation_id", "email", name="uq_user_org_email"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    organisation: Mapped[Organisation] = relationship(back_populates="users")


class Marketplace(Base):
    __tablename__ = "marketplaces"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_marketplace_org_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    default_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)

    organisation: Mapped[Organisation] = relationship(back_populates="marketplaces")
    products: Mapped[list[Product]] = relationship(back_populates="marketplace")


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        UniqueConstraint("organisation_id", "checksum", name="uq_import_org_checksum"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id"), nullable=False, index=True
    )
    marketplace_id: Mapped[str] = mapped_column(
        ForeignKey("marketplaces.id"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[ImportStatus] = mapped_column(
        SAEnum(ImportStatus), default=ImportStatus.pending, nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    columns: Mapped[list[ImportColumn]] = relationship(
        back_populates="import_batch", cascade="all, delete-orphan"
    )
    row_errors: Mapped[list[ImportRowError]] = relationship(
        back_populates="import_batch", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list[ProductSnapshot]] = relationship(back_populates="import_batch")


class ImportColumn(Base):
    __tablename__ = "import_columns"
    __table_args__ = (
        UniqueConstraint("import_batch_id", "source_header", name="uq_import_column_header"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    import_batch_id: Mapped[str] = mapped_column(
        ForeignKey("import_batches.id"), nullable=False, index=True
    )
    source_header: Mapped[str] = mapped_column(String(512), nullable=False)
    canonical_field: Mapped[str | None] = mapped_column(String(128))
    is_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_mapped: Mapped[bool] = mapped_column(default=False, nullable=False)

    import_batch: Mapped[ImportBatch] = relationship(back_populates="columns")


class ImportRowError(Base):
    __tablename__ = "import_row_errors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    import_batch_id: Mapped[str] = mapped_column(
        ForeignKey("import_batches.id"), nullable=False, index=True
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(128))
    message: Mapped[str] = mapped_column(Text, nullable=False)

    import_batch: Mapped[ImportBatch] = relationship(back_populates="row_errors")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id", "marketplace_id", "asin", name="uq_product_org_marketplace_asin"
        ),
        Index("ix_products_org_marketplace", "organisation_id", "marketplace_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id"), nullable=False, index=True
    )
    marketplace_id: Mapped[str] = mapped_column(
        ForeignKey("marketplaces.id"), nullable=False, index=True
    )
    asin: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str | None] = mapped_column(String(1000))
    brand: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    marketplace: Mapped[Marketplace] = relationship(back_populates="products")
    snapshots: Mapped[list[ProductSnapshot]] = relationship(back_populates="product")
    cost_profiles: Mapped[list[CostProfile]] = relationship(back_populates="product")
    inventory_positions: Mapped[list[InventoryPosition]] = relationship(back_populates="product")


class ProductSnapshot(Base):
    __tablename__ = "product_snapshots"
    __table_args__ = (Index("ix_snapshots_product_taken_at", "product_id", "snapshot_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    import_batch_id: Mapped[str | None] = mapped_column(ForeignKey("import_batches.id"), index=True)
    snapshot_kind: Mapped[SnapshotKind] = mapped_column(
        SAEnum(SnapshotKind), default=SnapshotKind.keepa, nullable=False
    )
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    market_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_row_number: Mapped[int | None] = mapped_column(Integer)

    product: Mapped[Product] = relationship(back_populates="snapshots")
    import_batch: Mapped[ImportBatch | None] = relationship(back_populates="snapshots")
    raw_attributes: Mapped[list[RawAttribute]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )
    score_results: Mapped[list[ScoreResult]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list[StrategyRecommendation]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )


@event.listens_for(ProductSnapshot, "before_update")
def _prevent_snapshot_update(_mapper: Any, _connection: Any, _target: ProductSnapshot) -> None:
    raise ValueError("Product snapshots are immutable")


@event.listens_for(ProductSnapshot, "before_delete")
def _prevent_snapshot_delete(_mapper: Any, _connection: Any, _target: ProductSnapshot) -> None:
    raise ValueError("Product snapshots are immutable")


class RawAttribute(Base):
    __tablename__ = "raw_attributes"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "source_header", name="uq_raw_attribute_snapshot_header"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("product_snapshots.id"), nullable=False, index=True
    )
    source_header: Mapped[str] = mapped_column(String(512), nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)

    snapshot: Mapped[ProductSnapshot] = relationship(back_populates="raw_attributes")


class ScoreResult(Base):
    __tablename__ = "score_results"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "score_name", "formula_version", name="uq_score_snapshot_name_version"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("product_snapshots.id"), nullable=False, index=True
    )
    score_name: Mapped[str] = mapped_column(String(120), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(80), nullable=False)
    score_value: Mapped[int] = mapped_column(Integer, nullable=False)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    snapshot: Mapped[ProductSnapshot] = relationship(back_populates="score_results")


class StrategyRecommendation(Base):
    __tablename__ = "strategy_recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("product_snapshots.id"), nullable=False, index=True
    )
    strategy: Mapped[str] = mapped_column(String(80), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    snapshot: Mapped[ProductSnapshot] = relationship(back_populates="recommendations")


class CostProfile(Base):
    __tablename__ = "cost_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id"), nullable=False, index=True
    )
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), index=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    supplier_unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    freight_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    prep_packaging_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    product: Mapped[Product | None] = relationship(back_populates="cost_profiles")


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("organisation_id", "name", name="uq_supplier_org_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    offers: Mapped[list[SupplierOffer]] = relationship(back_populates="supplier")


class SupplierOffer(Base):
    __tablename__ = "supplier_offers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    minimum_order_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    supplier: Mapped[Supplier] = relationship(back_populates="offers")


class InventoryPosition(Base):
    __tablename__ = "inventory_positions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    units_on_hand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    units_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    product: Mapped[Product] = relationship(back_populates="inventory_positions")


class ForecastScenario(Base):
    __tablename__ = "forecast_scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    assumptions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class PricingPlan(Base):
    __tablename__ = "pricing_plans"
    __table_args__ = (
        CheckConstraint("minimum_price <= target_price", name="ck_pricing_min_lte_target"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    minimum_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    target_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id"), nullable=False, index=True
    )
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
