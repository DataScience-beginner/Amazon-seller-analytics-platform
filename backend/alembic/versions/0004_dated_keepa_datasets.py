"""dated Keepa dataset evidence

Revision ID: 0004_dated_keepa_datasets
Revises: 0003_phase2_economics_sourcing
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_dated_keepa_datasets"
down_revision: str | None = "0003_phase2_economics_sourcing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("import_batches") as batch_op:
        batch_op.add_column(sa.Column("dataset_schema_id", sa.String(length=80)))
        batch_op.add_column(sa.Column("dataset_schema_version", sa.String(length=80)))
        batch_op.add_column(sa.Column("dataset_schema_match", sa.String(length=32)))
        batch_op.add_column(sa.Column("dataset_schema_checksum", sa.String(length=64)))
        batch_op.add_column(sa.Column("source_header_checksum", sa.String(length=64)))
        batch_op.add_column(
            sa.Column("source_column_count", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(sa.Column("observed_on_suggestion", sa.Date()))
        batch_op.add_column(sa.Column("observation_suggestion_source", sa.String(length=32)))
        batch_op.add_column(
            sa.Column(
                "observation_date_candidates",
                sa.JSON(),
                server_default="[]",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("observed_on", sa.Date()))
        batch_op.add_column(sa.Column("observed_on_source", sa.String(length=32)))
        batch_op.add_column(sa.Column("period_month", sa.Date()))
        batch_op.add_column(sa.Column("dataset_revision", sa.Integer()))
        batch_op.create_unique_constraint(
            "uq_import_dataset_period_revision",
            [
                "organisation_id",
                "marketplace_id",
                "dataset_schema_id",
                "period_month",
                "dataset_revision",
            ],
        )
        batch_op.create_check_constraint(
            "ck_import_source_columns_nonnegative",
            "source_column_count >= 0",
        )
        batch_op.create_check_constraint(
            "ck_import_dataset_revision_positive",
            "dataset_revision IS NULL OR dataset_revision >= 1",
        )
        batch_op.create_check_constraint(
            "ck_import_observation_metadata_complete",
            "(observed_on IS NULL AND period_month IS NULL "
            "AND dataset_revision IS NULL AND observed_on_source IS NULL) OR "
            "(observed_on IS NOT NULL AND period_month IS NOT NULL "
            "AND dataset_revision IS NOT NULL AND observed_on_source IS NOT NULL)",
        )
        batch_op.create_index(
            "ix_import_batches_org_marketplace_period",
            [
                "organisation_id",
                "marketplace_id",
                "dataset_schema_id",
                "period_month",
            ],
            unique=False,
        )

    op.execute(
        "UPDATE import_batches SET source_column_count = "
        "(SELECT COUNT(*) FROM import_columns "
        "WHERE import_columns.import_batch_id = import_batches.id)"
    )

    with op.batch_alter_table("product_snapshots") as batch_op:
        batch_op.add_column(sa.Column("observed_on", sa.Date()))
        batch_op.add_column(sa.Column("observed_on_source", sa.String(length=32)))
        batch_op.add_column(
            sa.Column("source_payload", sa.JSON(), server_default="[]", nullable=False)
        )
        batch_op.create_index(
            "ix_snapshots_product_observed_on",
            ["product_id", "observed_on"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("product_snapshots") as batch_op:
        batch_op.drop_index("ix_snapshots_product_observed_on")
        batch_op.drop_column("source_payload")
        batch_op.drop_column("observed_on_source")
        batch_op.drop_column("observed_on")

    with op.batch_alter_table("import_batches") as batch_op:
        batch_op.drop_index("ix_import_batches_org_marketplace_period")
        batch_op.drop_constraint("ck_import_observation_metadata_complete", type_="check")
        batch_op.drop_constraint("ck_import_dataset_revision_positive", type_="check")
        batch_op.drop_constraint("ck_import_source_columns_nonnegative", type_="check")
        batch_op.drop_constraint("uq_import_dataset_period_revision", type_="unique")
        batch_op.drop_column("dataset_revision")
        batch_op.drop_column("period_month")
        batch_op.drop_column("observed_on_source")
        batch_op.drop_column("observed_on")
        batch_op.drop_column("observation_suggestion_source")
        batch_op.drop_column("observed_on_suggestion")
        batch_op.drop_column("observation_date_candidates")
        batch_op.drop_column("source_column_count")
        batch_op.drop_column("source_header_checksum")
        batch_op.drop_column("dataset_schema_checksum")
        batch_op.drop_column("dataset_schema_match")
        batch_op.drop_column("dataset_schema_version")
        batch_op.drop_column("dataset_schema_id")
