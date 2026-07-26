"""phase 2 unit economics and sourcing

Revision ID: 0003_phase2_economics_sourcing
Revises: 0002_phase1_intelligence
Create Date: 2026-07-19
"""

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0003_phase2_economics_sourcing"
down_revision: str | None = "0002_phase1_intelligence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


fee_input_status = sa.Enum("observed", "estimated", "user_confirmed", name="feeinputstatus")
selling_price_tax_basis = sa.Enum("tax_inclusive", "tax_exclusive", name="sellingpricetaxbasis")
test_buy_outcome = sa.Enum("recommended", "blocked", name="testbuyoutcome")


def _legacy_cost_profile_rows(connection: sa.Connection) -> list[sa.Row[object]]:
    return list(
        connection.execute(
            sa.text(
                "SELECT cp.id, cp.organisation_id, cp.product_id, cp.effective_from, "
                "p.marketplace_id, p.organisation_id AS product_organisation_id, "
                "m.organisation_id AS marketplace_organisation_id "
                "FROM cost_profiles cp "
                "LEFT JOIN products p ON p.id = cp.product_id "
                "LEFT JOIN marketplaces m ON m.id = p.marketplace_id "
                "ORDER BY cp.organisation_id, p.marketplace_id, cp.product_id, "
                "cp.effective_from, cp.id"
            )
        ).all()
    )


def _legacy_effective_at(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RuntimeError("Legacy cost profile has an invalid effective timestamp") from exc
    else:
        raise RuntimeError("Legacy cost profile has an invalid effective timestamp")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _preflight_legacy_data() -> None:
    """Reject ambiguous evidence before non-transactional SQLite DDL starts."""
    connection = op.get_bind()
    rows = _legacy_cost_profile_rows(connection)
    unresolved = [
        row.id
        for row in rows
        if row.product_id is None
        or row.marketplace_id is None
        or row.product_organisation_id != row.organisation_id
        or row.marketplace_organisation_id != row.organisation_id
    ]
    if unresolved:
        raise RuntimeError(
            "Legacy default or cross-scope cost profiles require explicit marketplace repair "
            "before Phase 2 migration"
        )

    previous_effective_at: dict[tuple[str, str, str], datetime] = {}
    for row in rows:
        key = (str(row.organisation_id), str(row.marketplace_id), str(row.product_id))
        effective_at = _legacy_effective_at(row.effective_from)
        previous = previous_effective_at.get(key)
        if previous is not None and effective_at <= previous:
            raise RuntimeError(
                "Legacy cost profile revisions must have strictly increasing effective dates "
                "before Phase 2 migration"
            )
        previous_effective_at[key] = effective_at

    offer_count = int(connection.scalar(sa.text("SELECT COUNT(*) FROM supplier_offers")) or 0)
    if offer_count:
        raise RuntimeError(
            "Legacy supplier offers require an explicit quotation date before Phase 2 migration"
        )


def _prepare_legacy_cost_profiles() -> None:
    # Phase 0 stored no actor/correlation evidence for these rows. Do not invent audit events.
    connection = op.get_bind()
    rows = _legacy_cost_profile_rows(connection)
    versions: defaultdict[tuple[str, str, str], int] = defaultdict(int)
    previous_rows: dict[tuple[str, str, str], str] = {}
    for row in rows:
        key = (str(row.organisation_id), str(row.marketplace_id), str(row.product_id))
        versions[key] += 1
        previous_id = previous_rows.get(key)
        if previous_id is not None:
            connection.execute(
                sa.text("UPDATE cost_profiles SET effective_to = :effective_to WHERE id = :id"),
                {"effective_to": row.effective_from, "id": previous_id},
            )
        connection.execute(
            sa.text(
                "UPDATE cost_profiles SET marketplace_id = :marketplace_id, "
                "profile_scope_key = :scope_key, version = :version, "
                "supersedes_profile_id = :supersedes_profile_id, "
                "configuration_checksum = :checksum, "
                "prep_cost = prep_packaging_cost, packaging_cost = 0 "
                "WHERE id = :id"
            ),
            {
                "marketplace_id": row.marketplace_id,
                "scope_key": row.product_id,
                "version": versions[key],
                "supersedes_profile_id": previous_id,
                "checksum": "legacy-unverified",
                "id": row.id,
            },
        )
        previous_rows[key] = str(row.id)


def upgrade() -> None:
    _preflight_legacy_data()
    bind = op.get_bind()
    fee_input_status.create(bind, checkfirst=True)
    selling_price_tax_basis.create(bind, checkfirst=True)

    with op.batch_alter_table("cost_profiles") as batch_op:
        batch_op.add_column(sa.Column("marketplace_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("selling_price_tax_basis", selling_price_tax_basis))
        batch_op.add_column(sa.Column("profile_scope_key", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("supersedes_profile_id", sa.String(length=36)))
        batch_op.add_column(
            sa.Column("prep_cost", sa.Numeric(14, 4), server_default="0.0000", nullable=False)
        )
        batch_op.add_column(
            sa.Column("packaging_cost", sa.Numeric(14, 4), server_default="0.0000", nullable=False)
        )
        batch_op.add_column(
            sa.Column("gst_rate_percent", sa.Numeric(7, 4), server_default="0.0000", nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "gst_recoverable_percent",
                sa.Numeric(7, 4),
                server_default="0.0000",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "advertising_rate_percent",
                sa.Numeric(7, 4),
                server_default="0.0000",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "returns_rate_percent",
                sa.Numeric(7, 4),
                server_default="0.0000",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("overhead_cost", sa.Numeric(14, 4), server_default="0.0000", nullable=False)
        )
        batch_op.add_column(sa.Column("referral_fee_rate_percent", sa.Numeric(7, 4)))
        batch_op.add_column(sa.Column("fulfilment_fee", sa.Numeric(14, 4)))
        batch_op.add_column(sa.Column("closing_fee", sa.Numeric(14, 4)))
        batch_op.add_column(sa.Column("storage_fee", sa.Numeric(14, 4)))
        batch_op.add_column(sa.Column("fee_source", sa.String(length=255)))
        batch_op.add_column(sa.Column("fee_effective_at", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("fee_status", fee_input_status))
        batch_op.add_column(
            sa.Column(
                "minimum_margin_percent",
                sa.Numeric(7, 4),
                server_default="0.0000",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "target_margin_percent",
                sa.Numeric(7, 4),
                server_default="0.0000",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("configuration_checksum", sa.String(length=64)))
        batch_op.add_column(sa.Column("effective_to", sa.DateTime(timezone=True)))
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            )
        )

    _prepare_legacy_cost_profiles()

    with op.batch_alter_table("cost_profiles") as batch_op:
        batch_op.alter_column(
            "supplier_unit_cost",
            existing_type=sa.Numeric(12, 2),
            type_=sa.Numeric(14, 4),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "freight_cost",
            existing_type=sa.Numeric(12, 2),
            type_=sa.Numeric(14, 4),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "prep_packaging_cost",
            existing_type=sa.Numeric(12, 2),
            type_=sa.Numeric(14, 4),
            existing_nullable=False,
        )
        batch_op.alter_column("marketplace_id", nullable=False)
        batch_op.alter_column("profile_scope_key", nullable=False)
        batch_op.alter_column("version", nullable=False)
        batch_op.alter_column("configuration_checksum", nullable=False)
        batch_op.create_foreign_key(
            "fk_cost_profile_marketplace", "marketplaces", ["marketplace_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_cost_profile_supersedes", "cost_profiles", ["supersedes_profile_id"], ["id"]
        )
        batch_op.create_unique_constraint(
            "uq_cost_profile_scope_version",
            ["organisation_id", "marketplace_id", "profile_scope_key", "version"],
        )
        batch_op.create_check_constraint("ck_cost_profile_version_positive", "version >= 1")
        batch_op.create_check_constraint(
            "ck_cost_profile_scope_key_matches_product",
            "(product_id IS NULL AND profile_scope_key = 'marketplace_default') OR "
            "(product_id IS NOT NULL AND profile_scope_key = product_id)",
        )
        batch_op.create_check_constraint(
            "ck_cost_profile_effective_window",
            "effective_to IS NULL OR effective_to > effective_from",
        )
        batch_op.create_check_constraint(
            "ck_cost_profile_money_nonnegative",
            "supplier_unit_cost >= 0 AND freight_cost >= 0 AND prep_packaging_cost >= 0 "
            "AND prep_cost >= 0 AND packaging_cost >= 0 AND overhead_cost >= 0",
        )
        batch_op.create_check_constraint(
            "ck_cost_profile_percentages",
            "gst_rate_percent >= 0 AND gst_rate_percent <= 100 "
            "AND gst_recoverable_percent >= 0 AND gst_recoverable_percent <= 100 "
            "AND advertising_rate_percent >= 0 AND advertising_rate_percent <= 100 "
            "AND returns_rate_percent >= 0 AND returns_rate_percent <= 100 "
            "AND minimum_margin_percent >= 0 AND minimum_margin_percent < 100 "
            "AND target_margin_percent >= minimum_margin_percent "
            "AND target_margin_percent < 100",
        )
        batch_op.create_check_constraint(
            "ck_cost_profile_referral_percentage",
            "referral_fee_rate_percent IS NULL OR "
            "(referral_fee_rate_percent >= 0 AND referral_fee_rate_percent <= 100)",
        )
        batch_op.create_check_constraint(
            "ck_cost_profile_fulfilment_nonnegative",
            "fulfilment_fee IS NULL OR fulfilment_fee >= 0",
        )
        batch_op.create_check_constraint(
            "ck_cost_profile_closing_nonnegative", "closing_fee IS NULL OR closing_fee >= 0"
        )
        batch_op.create_check_constraint(
            "ck_cost_profile_storage_nonnegative", "storage_fee IS NULL OR storage_fee >= 0"
        )
        batch_op.create_index("ix_cost_profiles_marketplace_id", ["marketplace_id"], unique=False)
        batch_op.create_index(
            "ix_cost_profiles_supersedes_profile_id", ["supersedes_profile_id"], unique=False
        )
        batch_op.create_index(
            "ix_cost_profiles_scope_effective",
            ["organisation_id", "marketplace_id", "profile_scope_key", "effective_from"],
            unique=False,
        )

    with op.batch_alter_table("supplier_offers") as batch_op:
        batch_op.add_column(sa.Column("organisation_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("marketplace_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("supplier_name_at_quote", sa.String(length=255)))
        batch_op.add_column(sa.Column("quotation_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("notes", sa.Text()))
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            )
        )
        batch_op.alter_column(
            "unit_cost",
            existing_type=sa.Numeric(12, 2),
            type_=sa.Numeric(14, 4),
            existing_nullable=False,
        )
        batch_op.alter_column("organisation_id", nullable=False)
        batch_op.alter_column("marketplace_id", nullable=False)
        batch_op.alter_column("supplier_name_at_quote", nullable=False)
        batch_op.alter_column("quotation_date", nullable=False)
        batch_op.create_foreign_key(
            "fk_supplier_offer_organisation", "organisations", ["organisation_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_supplier_offer_marketplace", "marketplaces", ["marketplace_id"], ["id"]
        )
        batch_op.create_check_constraint(
            "ck_supplier_offer_unit_cost_nonnegative", "unit_cost >= 0"
        )
        batch_op.create_check_constraint(
            "ck_supplier_offer_moq_positive", "minimum_order_quantity >= 1"
        )
        batch_op.create_check_constraint(
            "ck_supplier_offer_lead_time_nonnegative", "lead_time_days >= 0"
        )
        batch_op.create_index(
            "ix_supplier_offers_organisation_id", ["organisation_id"], unique=False
        )
        batch_op.create_index("ix_supplier_offers_marketplace_id", ["marketplace_id"], unique=False)
        batch_op.create_index(
            "ix_supplier_offers_scope_product_quoted",
            ["organisation_id", "marketplace_id", "product_id", "quotation_date"],
            unique=False,
        )

    op.create_table(
        "supplier_offer_price_tiers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("supplier_offer_id", sa.String(length=36), nullable=False),
        sa.Column("minimum_quantity", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False),
        sa.CheckConstraint(
            "minimum_quantity >= 1", name="ck_supplier_offer_tier_quantity_positive"
        ),
        sa.CheckConstraint("unit_cost >= 0", name="ck_supplier_offer_tier_cost_nonnegative"),
        sa.ForeignKeyConstraint(["supplier_offer_id"], ["supplier_offers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "supplier_offer_id", "minimum_quantity", name="uq_supplier_offer_tier_quantity"
        ),
    )
    op.create_index(
        "ix_supplier_offer_price_tiers_supplier_offer_id",
        "supplier_offer_price_tiers",
        ["supplier_offer_id"],
    )

    op.create_table(
        "test_buy_recommendations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("marketplace_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("supplier_offer_id", sa.String(length=36), nullable=False),
        sa.Column("source_snapshot_id", sa.String(length=36)),
        sa.Column("data_confidence_score_result_id", sa.String(length=36)),
        sa.Column("budget_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("budget_currency_code", sa.String(length=3), nullable=False),
        sa.Column("formula_version", sa.String(length=80), nullable=False),
        sa.Column("configuration_checksum", sa.String(length=64), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("scenarios", sa.JSON(), nullable=False),
        sa.Column("notices", sa.JSON(), nullable=False),
        sa.Column("outcome", test_buy_outcome, nullable=False),
        sa.Column("advisory_only", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("budget_amount >= 0", name="ck_test_buy_budget_nonnegative"),
        sa.CheckConstraint("advisory_only = true", name="ck_test_buy_advisory_only"),
        sa.ForeignKeyConstraint(["marketplace_id"], ["marketplaces.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["source_snapshot_id"], ["product_snapshots.id"]),
        sa.ForeignKeyConstraint(["data_confidence_score_result_id"], ["score_results.id"]),
        sa.ForeignKeyConstraint(["supplier_offer_id"], ["supplier_offers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column_name in (
        "organisation_id",
        "marketplace_id",
        "product_id",
        "supplier_offer_id",
        "source_snapshot_id",
        "data_confidence_score_result_id",
    ):
        op.create_index(
            f"ix_test_buy_recommendations_{column_name}",
            "test_buy_recommendations",
            [column_name],
        )
    op.create_index(
        "ix_test_buy_scope_product_created",
        "test_buy_recommendations",
        ["organisation_id", "marketplace_id", "product_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_test_buy_scope_product_created", table_name="test_buy_recommendations")
    for column_name in (
        "supplier_offer_id",
        "data_confidence_score_result_id",
        "source_snapshot_id",
        "product_id",
        "marketplace_id",
        "organisation_id",
    ):
        op.drop_index(
            f"ix_test_buy_recommendations_{column_name}",
            table_name="test_buy_recommendations",
        )
    op.drop_table("test_buy_recommendations")
    op.drop_index(
        "ix_supplier_offer_price_tiers_supplier_offer_id",
        table_name="supplier_offer_price_tiers",
    )
    op.drop_table("supplier_offer_price_tiers")

    with op.batch_alter_table("supplier_offers") as batch_op:
        batch_op.drop_index("ix_supplier_offers_scope_product_quoted")
        batch_op.drop_index("ix_supplier_offers_marketplace_id")
        batch_op.drop_index("ix_supplier_offers_organisation_id")
        batch_op.drop_constraint("ck_supplier_offer_lead_time_nonnegative", type_="check")
        batch_op.drop_constraint("ck_supplier_offer_moq_positive", type_="check")
        batch_op.drop_constraint("ck_supplier_offer_unit_cost_nonnegative", type_="check")
        batch_op.drop_constraint("fk_supplier_offer_marketplace", type_="foreignkey")
        batch_op.drop_constraint("fk_supplier_offer_organisation", type_="foreignkey")
        batch_op.alter_column(
            "unit_cost",
            existing_type=sa.Numeric(14, 4),
            type_=sa.Numeric(12, 2),
            existing_nullable=False,
        )
        batch_op.drop_column("created_at")
        batch_op.drop_column("notes")
        batch_op.drop_column("quotation_date")
        batch_op.drop_column("supplier_name_at_quote")
        batch_op.drop_column("marketplace_id")
        batch_op.drop_column("organisation_id")

    with op.batch_alter_table("cost_profiles") as batch_op:
        batch_op.drop_index("ix_cost_profiles_scope_effective")
        batch_op.drop_index("ix_cost_profiles_supersedes_profile_id")
        batch_op.drop_index("ix_cost_profiles_marketplace_id")
        batch_op.drop_constraint("ck_cost_profile_storage_nonnegative", type_="check")
        batch_op.drop_constraint("ck_cost_profile_closing_nonnegative", type_="check")
        batch_op.drop_constraint("ck_cost_profile_fulfilment_nonnegative", type_="check")
        batch_op.drop_constraint("ck_cost_profile_referral_percentage", type_="check")
        batch_op.drop_constraint("ck_cost_profile_percentages", type_="check")
        batch_op.drop_constraint("ck_cost_profile_money_nonnegative", type_="check")
        batch_op.drop_constraint("ck_cost_profile_effective_window", type_="check")
        batch_op.drop_constraint("ck_cost_profile_scope_key_matches_product", type_="check")
        batch_op.drop_constraint("ck_cost_profile_version_positive", type_="check")
        batch_op.drop_constraint("uq_cost_profile_scope_version", type_="unique")
        batch_op.drop_constraint("fk_cost_profile_supersedes", type_="foreignkey")
        batch_op.drop_constraint("fk_cost_profile_marketplace", type_="foreignkey")
        batch_op.alter_column(
            "prep_packaging_cost",
            existing_type=sa.Numeric(14, 4),
            type_=sa.Numeric(12, 2),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "freight_cost",
            existing_type=sa.Numeric(14, 4),
            type_=sa.Numeric(12, 2),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "supplier_unit_cost",
            existing_type=sa.Numeric(14, 4),
            type_=sa.Numeric(12, 2),
            existing_nullable=False,
        )
        for column_name in (
            "created_at",
            "effective_to",
            "configuration_checksum",
            "target_margin_percent",
            "minimum_margin_percent",
            "fee_status",
            "fee_effective_at",
            "fee_source",
            "storage_fee",
            "closing_fee",
            "fulfilment_fee",
            "referral_fee_rate_percent",
            "overhead_cost",
            "returns_rate_percent",
            "advertising_rate_percent",
            "gst_recoverable_percent",
            "gst_rate_percent",
            "packaging_cost",
            "prep_cost",
            "supersedes_profile_id",
            "version",
            "profile_scope_key",
            "marketplace_id",
            "selling_price_tax_basis",
        ):
            batch_op.drop_column(column_name)

    test_buy_outcome.drop(op.get_bind(), checkfirst=True)
    selling_price_tax_basis.drop(op.get_bind(), checkfirst=True)
    fee_input_status.drop(op.get_bind(), checkfirst=True)
