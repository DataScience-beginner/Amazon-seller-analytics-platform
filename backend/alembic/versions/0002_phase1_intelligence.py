"""phase 1 ingestion and portfolio intelligence

Revision ID: 0002_phase1_intelligence
Revises: 0001_initial_domain
Create Date: 2026-07-19
"""

from collections import defaultdict
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_phase1_intelligence"
down_revision: str | None = "0001_initial_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


mapping_status = sa.Enum("mapped", "unknown", "ambiguous", name="mappingstatus")
mapping_source = sa.Enum("registry", "user", "unmapped", name="mappingsource")
row_error_severity = sa.Enum("error", "warning", name="rowerrorseverity")


def _backfill_positions(table_name: str, partition_column: str, target_column: str) -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            f"SELECT id, {partition_column} AS partition_id "
            f"FROM {table_name} ORDER BY {partition_column}, id"
        )
    )
    next_position: defaultdict[str, int] = defaultdict(int)
    for row in rows:
        partition_id = str(row.partition_id)
        position = next_position[partition_id]
        connection.execute(
            sa.text(f"UPDATE {table_name} SET {target_column} = :position WHERE id = :id"),
            {"position": position, "id": row.id},
        )
        next_position[partition_id] += 1


def upgrade() -> None:
    bind = op.get_bind()
    mapping_status.create(bind, checkfirst=True)
    mapping_source.create(bind, checkfirst=True)
    row_error_severity.create(bind, checkfirst=True)

    with op.batch_alter_table("import_batches") as batch_op:
        batch_op.drop_constraint("uq_import_org_checksum", type_="unique")
        batch_op.add_column(
            sa.Column(
                "checksum_algorithm", sa.String(length=32), server_default="sha256", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column("file_size_bytes", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(sa.Column("content_type", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("storage_key", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("workbook_sheet_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("header_row_number", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("alias_registry_version", sa.String(length=80), nullable=True)
        )
        batch_op.add_column(sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column("total_rows", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("created_rows", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("matched_rows", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("skipped_rows", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("failed_rows", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(sa.Column("failure_code", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("failure_message", sa.String(length=500), nullable=True))
        batch_op.create_unique_constraint(
            "uq_import_org_marketplace_checksum",
            ["organisation_id", "marketplace_id", "checksum"],
        )
        batch_op.create_check_constraint("ck_import_file_size_nonnegative", "file_size_bytes >= 0")
        batch_op.create_check_constraint(
            "ck_import_header_row_positive",
            "header_row_number IS NULL OR header_row_number >= 1",
        )
        batch_op.create_check_constraint(
            "ck_import_counts_nonnegative",
            "total_rows >= 0 AND created_rows >= 0 AND matched_rows >= 0 "
            "AND skipped_rows >= 0 AND failed_rows >= 0",
        )
        batch_op.create_index(
            "ix_import_batches_org_marketplace_uploaded",
            ["organisation_id", "marketplace_id", "uploaded_at"],
            unique=False,
        )

    op.add_column("import_columns", sa.Column("source_column_ordinal", sa.Integer(), nullable=True))
    _backfill_positions("import_columns", "import_batch_id", "source_column_ordinal")
    op.execute("UPDATE import_columns SET source_column_ordinal = source_column_ordinal + 1")
    with op.batch_alter_table("import_columns") as batch_op:
        batch_op.drop_constraint("uq_import_column_header", type_="unique")
        batch_op.alter_column("source_column_ordinal", nullable=False)
        batch_op.add_column(
            sa.Column("normalized_header", sa.String(length=512), server_default="", nullable=False)
        )
        batch_op.add_column(
            sa.Column("mapping_status", mapping_status, server_default="unknown", nullable=False)
        )
        batch_op.add_column(
            sa.Column("mapping_source", mapping_source, server_default="unmapped", nullable=False)
        )
        batch_op.add_column(
            sa.Column("mapping_candidates", sa.JSON(), server_default="[]", nullable=False)
        )
        batch_op.add_column(
            sa.Column("sample_values", sa.JSON(), server_default="[]", nullable=False)
        )
        batch_op.create_unique_constraint(
            "uq_import_column_position", ["import_batch_id", "source_column_ordinal"]
        )
        batch_op.create_check_constraint(
            "ck_import_column_position_positive", "source_column_ordinal >= 1"
        )

    op.execute("UPDATE import_columns SET normalized_header = source_header")
    import_columns = sa.table(
        "import_columns",
        sa.column("mapping_status", mapping_status),
        sa.column("mapping_source", mapping_source),
        sa.column("is_mapped", sa.Boolean()),
    )
    op.execute(
        import_columns.update()
        .where(import_columns.c.is_mapped.is_(True))
        .values(mapping_status="mapped", mapping_source="registry")
    )

    with op.batch_alter_table("import_row_errors") as batch_op:
        batch_op.add_column(
            sa.Column(
                "error_code", sa.String(length=120), server_default="legacy_error", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column("severity", row_error_severity, server_default="error", nullable=False)
        )
        batch_op.create_check_constraint("ck_import_row_error_row_positive", "row_number >= 1")

    with op.batch_alter_table("products") as batch_op:
        batch_op.add_column(sa.Column("category", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("subcategory", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("image_url", sa.String(length=2000), nullable=True))
        batch_op.add_column(sa.Column("amazon_url", sa.String(length=2000), nullable=True))
        batch_op.add_column(sa.Column("latest_snapshot_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_product_latest_snapshot", "product_snapshots", ["latest_snapshot_id"], ["id"]
        )
        batch_op.create_index(
            "ix_products_latest_snapshot_id", ["latest_snapshot_id"], unique=False
        )
        batch_op.create_index(
            "ix_products_org_marketplace_category",
            ["organisation_id", "marketplace_id", "category"],
            unique=False,
        )

    with op.batch_alter_table("product_snapshots") as batch_op:
        batch_op.add_column(sa.Column("title", sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column("brand", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("category", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("subcategory", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("buy_box_price", sa.Numeric(14, 2), nullable=True))
        batch_op.add_column(sa.Column("buy_box_price_90d", sa.Numeric(14, 2), nullable=True))
        batch_op.add_column(sa.Column("currency_code", sa.String(length=3), nullable=True))
        batch_op.add_column(sa.Column("sales_rank", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("sales_rank_90d", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("sales_rank_drops_90d", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("review_rating", sa.Numeric(3, 2), nullable=True))
        batch_op.add_column(sa.Column("review_count", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("new_offer_count", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("total_offer_count", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("buy_box_winner_count_90d", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("buy_box_oos_percentage_90d", sa.Numeric(5, 2), nullable=True)
        )
        batch_op.add_column(sa.Column("monthly_sold", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("is_fba", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("image_url", sa.String(length=2000), nullable=True))
        batch_op.add_column(sa.Column("amazon_url", sa.String(length=2000), nullable=True))
        batch_op.create_unique_constraint(
            "uq_snapshot_import_batch_product", ["import_batch_id", "product_id"]
        )
        batch_op.create_check_constraint(
            "ck_snapshot_oos_percentage",
            "buy_box_oos_percentage_90d IS NULL OR "
            "(buy_box_oos_percentage_90d >= 0 AND buy_box_oos_percentage_90d <= 100)",
        )
        batch_op.create_check_constraint(
            "ck_snapshot_review_rating",
            "review_rating IS NULL OR (review_rating >= 0 AND review_rating <= 5)",
        )

    op.add_column("raw_attributes", sa.Column("source_column_ordinal", sa.Integer(), nullable=True))
    _backfill_positions("raw_attributes", "snapshot_id", "source_column_ordinal")
    op.execute("UPDATE raw_attributes SET source_column_ordinal = source_column_ordinal + 1")
    with op.batch_alter_table("raw_attributes") as batch_op:
        batch_op.drop_constraint("uq_raw_attribute_snapshot_header", type_="unique")
        batch_op.alter_column("source_column_ordinal", nullable=False)
        batch_op.create_unique_constraint(
            "uq_raw_attribute_snapshot_position", ["snapshot_id", "source_column_ordinal"]
        )
        batch_op.create_check_constraint(
            "ck_raw_attribute_position_positive", "source_column_ordinal >= 1"
        )

    with op.batch_alter_table("score_results") as batch_op:
        batch_op.add_column(
            sa.Column(
                "configuration_checksum",
                sa.String(length=64),
                server_default="legacy",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_score_value_range", "score_value >= 0 AND score_value <= 100"
        )

    with op.batch_alter_table("strategy_recommendations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "configuration_checksum",
                sa.String(length=64),
                server_default="legacy",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("confidence_score", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.create_unique_constraint(
            "uq_recommendation_snapshot_rules_version", ["snapshot_id", "rules_version"]
        )
        batch_op.create_check_constraint(
            "ck_recommendation_confidence_range",
            "confidence_score >= 0 AND confidence_score <= 100",
        )

    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.add_column(
            sa.Column("actor_type", sa.String(length=32), server_default="system", nullable=False)
        )
        batch_op.add_column(sa.Column("correlation_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("causation_id", sa.String(length=64), nullable=True))
        batch_op.create_index("ix_audit_events_correlation_id", ["correlation_id"], unique=False)
        batch_op.create_index("ix_audit_events_causation_id", ["causation_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.drop_index("ix_audit_events_causation_id")
        batch_op.drop_index("ix_audit_events_correlation_id")
        batch_op.drop_column("causation_id")
        batch_op.drop_column("correlation_id")
        batch_op.drop_column("actor_type")

    with op.batch_alter_table("strategy_recommendations") as batch_op:
        batch_op.drop_constraint("ck_recommendation_confidence_range", type_="check")
        batch_op.drop_constraint("uq_recommendation_snapshot_rules_version", type_="unique")
        batch_op.drop_column("confidence_score")
        batch_op.drop_column("configuration_checksum")

    with op.batch_alter_table("score_results") as batch_op:
        batch_op.drop_constraint("ck_score_value_range", type_="check")
        batch_op.drop_column("created_at")
        batch_op.drop_column("configuration_checksum")

    with op.batch_alter_table("raw_attributes") as batch_op:
        batch_op.drop_constraint("ck_raw_attribute_position_positive", type_="check")
        batch_op.drop_constraint("uq_raw_attribute_snapshot_position", type_="unique")
        batch_op.create_unique_constraint(
            "uq_raw_attribute_snapshot_header", ["snapshot_id", "source_header"]
        )
        batch_op.drop_column("source_column_ordinal")

    with op.batch_alter_table("product_snapshots") as batch_op:
        batch_op.drop_constraint("ck_snapshot_review_rating", type_="check")
        batch_op.drop_constraint("ck_snapshot_oos_percentage", type_="check")
        batch_op.drop_constraint("uq_snapshot_import_batch_product", type_="unique")
        for column_name in (
            "amazon_url",
            "image_url",
            "is_fba",
            "monthly_sold",
            "buy_box_oos_percentage_90d",
            "buy_box_winner_count_90d",
            "total_offer_count",
            "new_offer_count",
            "review_count",
            "review_rating",
            "sales_rank_drops_90d",
            "sales_rank_90d",
            "sales_rank",
            "currency_code",
            "buy_box_price_90d",
            "buy_box_price",
            "subcategory",
            "category",
            "brand",
            "title",
        ):
            batch_op.drop_column(column_name)

    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_index("ix_products_org_marketplace_category")
        batch_op.drop_index("ix_products_latest_snapshot_id")
        batch_op.drop_constraint("fk_product_latest_snapshot", type_="foreignkey")
        batch_op.drop_column("latest_snapshot_id")
        batch_op.drop_column("amazon_url")
        batch_op.drop_column("image_url")
        batch_op.drop_column("subcategory")
        batch_op.drop_column("category")

    with op.batch_alter_table("import_row_errors") as batch_op:
        batch_op.drop_constraint("ck_import_row_error_row_positive", type_="check")
        batch_op.drop_column("severity")
        batch_op.drop_column("error_code")

    with op.batch_alter_table("import_columns") as batch_op:
        batch_op.drop_constraint("ck_import_column_position_positive", type_="check")
        batch_op.drop_constraint("uq_import_column_position", type_="unique")
        batch_op.create_unique_constraint(
            "uq_import_column_header", ["import_batch_id", "source_header"]
        )
        batch_op.drop_column("sample_values")
        batch_op.drop_column("mapping_candidates")
        batch_op.drop_column("mapping_source")
        batch_op.drop_column("mapping_status")
        batch_op.drop_column("normalized_header")
        batch_op.drop_column("source_column_ordinal")

    with op.batch_alter_table("import_batches") as batch_op:
        batch_op.drop_index("ix_import_batches_org_marketplace_uploaded")
        batch_op.drop_constraint("ck_import_counts_nonnegative", type_="check")
        batch_op.drop_constraint("ck_import_header_row_positive", type_="check")
        batch_op.drop_constraint("ck_import_file_size_nonnegative", type_="check")
        batch_op.drop_constraint("uq_import_org_marketplace_checksum", type_="unique")
        batch_op.create_unique_constraint("uq_import_org_checksum", ["organisation_id", "checksum"])
        for column_name in (
            "failure_message",
            "failure_code",
            "failed_rows",
            "skipped_rows",
            "matched_rows",
            "created_rows",
            "total_rows",
            "confirmed_at",
            "alias_registry_version",
            "header_row_number",
            "workbook_sheet_name",
            "storage_key",
            "content_type",
            "file_size_bytes",
            "checksum_algorithm",
        ):
            batch_op.drop_column(column_name)

    row_error_severity.drop(op.get_bind(), checkfirst=True)
    mapping_source.drop(op.get_bind(), checkfirst=True)
    mapping_status.drop(op.get_bind(), checkfirst=True)
