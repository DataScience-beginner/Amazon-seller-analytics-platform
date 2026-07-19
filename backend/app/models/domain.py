from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
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
from sqlalchemy import (
    inspect as sa_inspect,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db.types import UTCDateTime


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


class MappingStatus(StrEnum):
    mapped = "mapped"
    unknown = "unknown"
    ambiguous = "ambiguous"


class MappingSource(StrEnum):
    registry = "registry"
    user = "user"
    unmapped = "unmapped"


class RowErrorSeverity(StrEnum):
    error = "error"
    warning = "warning"


class FeeInputStatus(StrEnum):
    observed = "observed"
    estimated = "estimated"
    user_confirmed = "user_confirmed"


class SellingPriceTaxBasis(StrEnum):
    tax_inclusive = "tax_inclusive"
    tax_exclusive = "tax_exclusive"


class TestBuyOutcome(StrEnum):
    recommended = "recommended"
    blocked = "blocked"


class Organisation(Base):
    __tablename__ = "organisations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)

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
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)

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
        UniqueConstraint(
            "organisation_id",
            "marketplace_id",
            "checksum",
            name="uq_import_org_marketplace_checksum",
        ),
        Index(
            "ix_import_batches_org_marketplace_uploaded",
            "organisation_id",
            "marketplace_id",
            "uploaded_at",
        ),
        CheckConstraint("file_size_bytes >= 0", name="ck_import_file_size_nonnegative"),
        CheckConstraint(
            "header_row_number IS NULL OR header_row_number >= 1",
            name="ck_import_header_row_positive",
        ),
        CheckConstraint(
            "total_rows >= 0 AND created_rows >= 0 AND matched_rows >= 0 "
            "AND skipped_rows >= 0 AND failed_rows >= 0",
            name="ck_import_counts_nonnegative",
        ),
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
    checksum_algorithm: Mapped[str] = mapped_column(String(32), default="sha256", nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))
    storage_key: Mapped[str | None] = mapped_column(String(255))
    workbook_sheet_name: Mapped[str | None] = mapped_column(String(255))
    header_row_number: Mapped[int | None] = mapped_column(Integer)
    alias_registry_version: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[ImportStatus] = mapped_column(
        SAEnum(ImportStatus), default=ImportStatus.pending, nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matched_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(120))
    failure_message: Mapped[str | None] = mapped_column(String(500))

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
        UniqueConstraint(
            "import_batch_id", "source_column_ordinal", name="uq_import_column_position"
        ),
        CheckConstraint("source_column_ordinal >= 1", name="ck_import_column_position_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    import_batch_id: Mapped[str] = mapped_column(
        ForeignKey("import_batches.id"), nullable=False, index=True
    )
    source_column_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    source_header: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_header: Mapped[str] = mapped_column(String(512), nullable=False)
    canonical_field: Mapped[str | None] = mapped_column(String(128))
    mapping_status: Mapped[MappingStatus] = mapped_column(
        SAEnum(MappingStatus), default=MappingStatus.unknown, nullable=False
    )
    mapping_source: Mapped[MappingSource] = mapped_column(
        SAEnum(MappingSource), default=MappingSource.unmapped, nullable=False
    )
    mapping_candidates: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    sample_values: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    is_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_mapped: Mapped[bool] = mapped_column(default=False, nullable=False)

    import_batch: Mapped[ImportBatch] = relationship(back_populates="columns")


class ImportRowError(Base):
    __tablename__ = "import_row_errors"
    __table_args__ = (CheckConstraint("row_number >= 1", name="ck_import_row_error_row_positive"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    import_batch_id: Mapped[str] = mapped_column(
        ForeignKey("import_batches.id"), nullable=False, index=True
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(128))
    error_code: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[RowErrorSeverity] = mapped_column(
        SAEnum(RowErrorSeverity), default=RowErrorSeverity.error, nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)

    import_batch: Mapped[ImportBatch] = relationship(back_populates="row_errors")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id", "marketplace_id", "asin", name="uq_product_org_marketplace_asin"
        ),
        Index("ix_products_org_marketplace", "organisation_id", "marketplace_id"),
        Index(
            "ix_products_org_marketplace_category", "organisation_id", "marketplace_id", "category"
        ),
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
    category: Mapped[str | None] = mapped_column(String(255))
    subcategory: Mapped[str | None] = mapped_column(String(255))
    image_url: Mapped[str | None] = mapped_column(String(2000))
    amazon_url: Mapped[str | None] = mapped_column(String(2000))
    latest_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("product_snapshots.id", use_alter=True, name="fk_product_latest_snapshot"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)

    marketplace: Mapped[Marketplace] = relationship(back_populates="products")
    snapshots: Mapped[list[ProductSnapshot]] = relationship(
        back_populates="product", foreign_keys="ProductSnapshot.product_id"
    )
    latest_snapshot: Mapped[ProductSnapshot | None] = relationship(
        foreign_keys=[latest_snapshot_id], post_update=True
    )
    cost_profiles: Mapped[list[CostProfile]] = relationship(back_populates="product")
    supplier_offers: Mapped[list[SupplierOffer]] = relationship(back_populates="product")
    inventory_positions: Mapped[list[InventoryPosition]] = relationship(back_populates="product")


class ProductSnapshot(Base):
    __tablename__ = "product_snapshots"
    __table_args__ = (
        UniqueConstraint("import_batch_id", "product_id", name="uq_snapshot_import_batch_product"),
        Index("ix_snapshots_product_taken_at", "product_id", "snapshot_at"),
        CheckConstraint(
            "buy_box_oos_percentage_90d IS NULL OR "
            "(buy_box_oos_percentage_90d >= 0 AND buy_box_oos_percentage_90d <= 100)",
            name="ck_snapshot_oos_percentage",
        ),
        CheckConstraint(
            "review_rating IS NULL OR (review_rating >= 0 AND review_rating <= 5)",
            name="ck_snapshot_review_rating",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    import_batch_id: Mapped[str | None] = mapped_column(ForeignKey("import_batches.id"), index=True)
    snapshot_kind: Mapped[SnapshotKind] = mapped_column(
        SAEnum(SnapshotKind), default=SnapshotKind.keepa, nullable=False
    )
    snapshot_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    title: Mapped[str | None] = mapped_column(String(1000))
    brand: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(255))
    subcategory: Mapped[str | None] = mapped_column(String(255))
    buy_box_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    buy_box_price_90d: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency_code: Mapped[str | None] = mapped_column(String(3))
    sales_rank: Mapped[int | None] = mapped_column(Integer)
    sales_rank_90d: Mapped[int | None] = mapped_column(Integer)
    sales_rank_drops_90d: Mapped[int | None] = mapped_column(Integer)
    review_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    review_count: Mapped[int | None] = mapped_column(Integer)
    new_offer_count: Mapped[int | None] = mapped_column(Integer)
    total_offer_count: Mapped[int | None] = mapped_column(Integer)
    buy_box_winner_count_90d: Mapped[int | None] = mapped_column(Integer)
    buy_box_oos_percentage_90d: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    monthly_sold: Mapped[int | None] = mapped_column(Integer)
    is_fba: Mapped[bool | None] = mapped_column()
    image_url: Mapped[str | None] = mapped_column(String(2000))
    amazon_url: Mapped[str | None] = mapped_column(String(2000))
    market_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_row_number: Mapped[int | None] = mapped_column(Integer)

    product: Mapped[Product] = relationship(back_populates="snapshots", foreign_keys=[product_id])
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
def _prevent_snapshot_update(mapper: Any, _connection: Any, target: ProductSnapshot) -> None:
    state = sa_inspect(target)
    if any(state.attrs[column.key].history.has_changes() for column in mapper.column_attrs):
        raise ValueError("Product snapshots are immutable")


@event.listens_for(ProductSnapshot, "before_delete")
def _prevent_snapshot_delete(_mapper: Any, _connection: Any, _target: ProductSnapshot) -> None:
    raise ValueError("Product snapshots are immutable")


class RawAttribute(Base):
    __tablename__ = "raw_attributes"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "source_column_ordinal", name="uq_raw_attribute_snapshot_position"
        ),
        CheckConstraint("source_column_ordinal >= 1", name="ck_raw_attribute_position_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("product_snapshots.id"), nullable=False, index=True
    )
    source_column_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    source_header: Mapped[str] = mapped_column(String(512), nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)

    snapshot: Mapped[ProductSnapshot] = relationship(back_populates="raw_attributes")


class ScoreResult(Base):
    __tablename__ = "score_results"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "score_name", "formula_version", name="uq_score_snapshot_name_version"
        ),
        CheckConstraint("score_value >= 0 AND score_value <= 100", name="ck_score_value_range"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("product_snapshots.id"), nullable=False, index=True
    )
    score_name: Mapped[str] = mapped_column(String(120), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(80), nullable=False)
    configuration_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    score_value: Mapped[int] = mapped_column(Integer, nullable=False)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)

    snapshot: Mapped[ProductSnapshot] = relationship(back_populates="score_results")


class StrategyRecommendation(Base):
    __tablename__ = "strategy_recommendations"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "rules_version", name="uq_recommendation_snapshot_rules_version"
        ),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 100",
            name="ck_recommendation_confidence_range",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("product_snapshots.id"), nullable=False, index=True
    )
    strategy: Mapped[str] = mapped_column(String(80), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(80), nullable=False)
    configuration_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)

    snapshot: Mapped[ProductSnapshot] = relationship(back_populates="recommendations")


@event.listens_for(RawAttribute, "before_update")
@event.listens_for(ScoreResult, "before_update")
@event.listens_for(StrategyRecommendation, "before_update")
def _prevent_snapshot_evidence_update(
    _mapper: Any,
    _connection: Any,
    _target: RawAttribute | ScoreResult | StrategyRecommendation,
) -> None:
    raise ValueError("Imported snapshot evidence is immutable")


@event.listens_for(RawAttribute, "before_delete")
@event.listens_for(ScoreResult, "before_delete")
@event.listens_for(StrategyRecommendation, "before_delete")
def _prevent_snapshot_evidence_delete(
    _mapper: Any,
    _connection: Any,
    _target: RawAttribute | ScoreResult | StrategyRecommendation,
) -> None:
    raise ValueError("Imported snapshot evidence is immutable")


class CostProfile(Base):
    __tablename__ = "cost_profiles"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "marketplace_id",
            "profile_scope_key",
            "version",
            name="uq_cost_profile_scope_version",
        ),
        CheckConstraint("version >= 1", name="ck_cost_profile_version_positive"),
        CheckConstraint(
            "(product_id IS NULL AND profile_scope_key = 'marketplace_default') OR "
            "(product_id IS NOT NULL AND profile_scope_key = product_id)",
            name="ck_cost_profile_scope_key_matches_product",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_cost_profile_effective_window",
        ),
        CheckConstraint(
            "supplier_unit_cost >= 0 AND freight_cost >= 0 AND prep_packaging_cost >= 0 "
            "AND prep_cost >= 0 AND packaging_cost >= 0 AND overhead_cost >= 0",
            name="ck_cost_profile_money_nonnegative",
        ),
        CheckConstraint(
            "gst_rate_percent >= 0 AND gst_rate_percent <= 100 "
            "AND gst_recoverable_percent >= 0 AND gst_recoverable_percent <= 100 "
            "AND advertising_rate_percent >= 0 AND advertising_rate_percent <= 100 "
            "AND returns_rate_percent >= 0 AND returns_rate_percent <= 100 "
            "AND minimum_margin_percent >= 0 AND minimum_margin_percent < 100 "
            "AND target_margin_percent >= minimum_margin_percent "
            "AND target_margin_percent < 100",
            name="ck_cost_profile_percentages",
        ),
        CheckConstraint(
            "referral_fee_rate_percent IS NULL OR "
            "(referral_fee_rate_percent >= 0 AND referral_fee_rate_percent <= 100)",
            name="ck_cost_profile_referral_percentage",
        ),
        CheckConstraint(
            "fulfilment_fee IS NULL OR fulfilment_fee >= 0",
            name="ck_cost_profile_fulfilment_nonnegative",
        ),
        CheckConstraint(
            "closing_fee IS NULL OR closing_fee >= 0",
            name="ck_cost_profile_closing_nonnegative",
        ),
        CheckConstraint(
            "storage_fee IS NULL OR storage_fee >= 0",
            name="ck_cost_profile_storage_nonnegative",
        ),
        Index(
            "ix_cost_profiles_scope_effective",
            "organisation_id",
            "marketplace_id",
            "profile_scope_key",
            "effective_from",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id"), nullable=False, index=True
    )
    marketplace_id: Mapped[str] = mapped_column(
        ForeignKey("marketplaces.id"), nullable=False, index=True
    )
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), index=True)
    profile_scope_key: Mapped[str] = mapped_column(String(36), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("cost_profiles.id"), index=True
    )
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    selling_price_tax_basis: Mapped[SellingPriceTaxBasis | None] = mapped_column(
        SAEnum(SellingPriceTaxBasis)
    )
    supplier_unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    freight_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), default=Decimal("0.0000"), nullable=False
    )
    prep_packaging_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), default=Decimal("0.0000"), nullable=False
    )
    prep_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), default=Decimal("0.0000"), nullable=False
    )
    packaging_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), default=Decimal("0.0000"), nullable=False
    )
    gst_rate_percent: Mapped[Decimal] = mapped_column(
        Numeric(7, 4), default=Decimal("0.0000"), nullable=False
    )
    gst_recoverable_percent: Mapped[Decimal] = mapped_column(
        Numeric(7, 4), default=Decimal("0.0000"), nullable=False
    )
    advertising_rate_percent: Mapped[Decimal] = mapped_column(
        Numeric(7, 4), default=Decimal("0.0000"), nullable=False
    )
    returns_rate_percent: Mapped[Decimal] = mapped_column(
        Numeric(7, 4), default=Decimal("0.0000"), nullable=False
    )
    overhead_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), default=Decimal("0.0000"), nullable=False
    )
    referral_fee_rate_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    fulfilment_fee: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    closing_fee: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    storage_fee: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    fee_source: Mapped[str | None] = mapped_column(String(255))
    fee_effective_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    fee_status: Mapped[FeeInputStatus | None] = mapped_column(SAEnum(FeeInputStatus))
    minimum_margin_percent: Mapped[Decimal] = mapped_column(
        Numeric(7, 4), default=Decimal("0.0000"), nullable=False
    )
    target_margin_percent: Mapped[Decimal] = mapped_column(
        Numeric(7, 4), default=Decimal("0.0000"), nullable=False
    )
    configuration_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(UTCDateTime(), active_history=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)

    product: Mapped[Product | None] = relationship(back_populates="cost_profiles")


@event.listens_for(CostProfile, "before_insert")
def _require_new_cost_profile_tax_basis(
    _mapper: Any, _connection: Any, target: CostProfile
) -> None:
    if target.selling_price_tax_basis is None:
        raise ValueError("New cost profiles require an explicit selling-price tax basis")


@event.listens_for(CostProfile, "before_update")
def _allow_cost_profile_closure_only(mapper: Any, _connection: Any, target: CostProfile) -> None:
    state = sa_inspect(target)
    changed_columns = {
        column.key
        for column in mapper.column_attrs
        if state.attrs[column.key].history.has_changes()
    }
    history = state.attrs.effective_to.history
    new_value = history.added[0] if history.added else None
    old_value = history.deleted[0] if history.deleted else None
    if (
        changed_columns != {"effective_to"}
        or old_value is not None
        or not isinstance(new_value, datetime)
        or new_value.tzinfo is None
        or new_value.utcoffset() != timedelta(0)
    ):
        raise ValueError(
            "Cost profiles are append-only; only a one-time UTC effective_to closure is allowed"
        )


@event.listens_for(CostProfile, "before_delete")
def _prevent_cost_profile_delete(_mapper: Any, _connection: Any, _target: CostProfile) -> None:
    raise ValueError("Cost profiles are append-only")


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
    __table_args__ = (
        CheckConstraint("unit_cost >= 0", name="ck_supplier_offer_unit_cost_nonnegative"),
        CheckConstraint("minimum_order_quantity >= 1", name="ck_supplier_offer_moq_positive"),
        CheckConstraint("lead_time_days >= 0", name="ck_supplier_offer_lead_time_nonnegative"),
        Index(
            "ix_supplier_offers_scope_product_quoted",
            "organisation_id",
            "marketplace_id",
            "product_id",
            "quotation_date",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id"), nullable=False, index=True
    )
    marketplace_id: Mapped[str] = mapped_column(
        ForeignKey("marketplaces.id"), nullable=False, index=True
    )
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    supplier_name_at_quote: Mapped[str] = mapped_column(String(255), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    minimum_order_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    quotation_date: Mapped[date] = mapped_column(Date(), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)

    supplier: Mapped[Supplier] = relationship(back_populates="offers")
    product: Mapped[Product] = relationship(back_populates="supplier_offers")
    price_tiers: Mapped[list[SupplierOfferPriceTier]] = relationship(
        back_populates="offer",
        cascade="all, delete-orphan",
        order_by="SupplierOfferPriceTier.minimum_quantity",
    )


class SupplierOfferPriceTier(Base):
    __tablename__ = "supplier_offer_price_tiers"
    __table_args__ = (
        UniqueConstraint(
            "supplier_offer_id", "minimum_quantity", name="uq_supplier_offer_tier_quantity"
        ),
        CheckConstraint("minimum_quantity >= 1", name="ck_supplier_offer_tier_quantity_positive"),
        CheckConstraint("unit_cost >= 0", name="ck_supplier_offer_tier_cost_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    supplier_offer_id: Mapped[str] = mapped_column(
        ForeignKey("supplier_offers.id"), nullable=False, index=True
    )
    minimum_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)

    offer: Mapped[SupplierOffer] = relationship(back_populates="price_tiers")


@event.listens_for(SupplierOfferPriceTier, "before_insert")
def _only_insert_tiers_with_new_offer(
    _mapper: Any, _connection: Any, target: SupplierOfferPriceTier
) -> None:
    offer = target.offer
    if offer is None or not sa_inspect(offer).pending:
        raise ValueError("Price tiers may only be inserted with a new supplier quotation")


class TestBuyRecommendation(Base):
    __tablename__ = "test_buy_recommendations"
    __table_args__ = (
        CheckConstraint("budget_amount >= 0", name="ck_test_buy_budget_nonnegative"),
        CheckConstraint("advisory_only = true", name="ck_test_buy_advisory_only"),
        Index(
            "ix_test_buy_scope_product_created",
            "organisation_id",
            "marketplace_id",
            "product_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id"), nullable=False, index=True
    )
    marketplace_id: Mapped[str] = mapped_column(
        ForeignKey("marketplaces.id"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    supplier_offer_id: Mapped[str] = mapped_column(
        ForeignKey("supplier_offers.id"), nullable=False, index=True
    )
    source_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("product_snapshots.id"), index=True
    )
    data_confidence_score_result_id: Mapped[str | None] = mapped_column(
        ForeignKey("score_results.id"), index=True
    )
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    budget_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(80), nullable=False)
    configuration_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    scenarios: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    notices: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    outcome: Mapped[TestBuyOutcome] = mapped_column(SAEnum(TestBuyOutcome), nullable=False)
    advisory_only: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)


@event.listens_for(SupplierOffer, "before_update")
@event.listens_for(SupplierOfferPriceTier, "before_update")
@event.listens_for(TestBuyRecommendation, "before_update")
def _prevent_sourcing_evidence_update(
    _mapper: Any,
    _connection: Any,
    _target: SupplierOffer | SupplierOfferPriceTier | TestBuyRecommendation,
) -> None:
    raise ValueError("Supplier quotations and test-buy recommendations are immutable")


@event.listens_for(SupplierOffer, "before_delete")
@event.listens_for(SupplierOfferPriceTier, "before_delete")
@event.listens_for(TestBuyRecommendation, "before_delete")
def _prevent_sourcing_evidence_delete(
    _mapper: Any,
    _connection: Any,
    _target: SupplierOffer | SupplierOfferPriceTier | TestBuyRecommendation,
) -> None:
    raise ValueError("Supplier quotations and test-buy recommendations are immutable")


class InventoryPosition(Base):
    __tablename__ = "inventory_positions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    units_on_hand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    units_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    measured_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)

    product: Mapped[Product] = relationship(back_populates="inventory_positions")


class ForecastScenario(Base):
    __tablename__ = "forecast_scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    assumptions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)


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
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id"), nullable=False, index=True
    )
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    actor_type: Mapped[str] = mapped_column(String(32), default="system", nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    causation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)


@event.listens_for(AuditEvent, "before_update")
def _prevent_audit_event_update(_mapper: Any, _connection: Any, _target: AuditEvent) -> None:
    raise ValueError("Audit events are immutable")


@event.listens_for(AuditEvent, "before_delete")
def _prevent_audit_event_delete(_mapper: Any, _connection: Any, _target: AuditEvent) -> None:
    raise ValueError("Audit events are immutable")
