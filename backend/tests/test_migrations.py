import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import Boolean, column, create_engine, create_mock_engine, inspect, table, text


def test_boolean_migration_predicate_is_portable() -> None:
    import_columns = table("import_columns", column("is_mapped", Boolean()))
    statement = import_columns.update().where(import_columns.c.is_mapped.is_(True))

    postgres = create_mock_engine("postgresql+psycopg://", lambda *_args, **_kwargs: None)
    sqlite = create_mock_engine("sqlite://", lambda *_args, **_kwargs: None)
    postgres_sql = str(statement.compile(dialect=postgres.dialect))
    sqlite_sql = str(statement.compile(dialect=sqlite.dialect))

    assert "is_mapped IS true" in postgres_sql
    assert "is_mapped IS 1" in sqlite_sql
    assert "is_mapped = 1" not in postgres_sql


def test_alembic_upgrade_and_downgrade(tmp_path: Path) -> None:
    backend_dir = Path(__file__).parents[1]
    database_path = tmp_path / "migration-test.db"
    database_url = f"sqlite:///{database_path}"
    environment = {**os.environ, "DATABASE_URL": database_url}

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    engine = create_engine(database_url)
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    assert "organisations" in table_names
    assert "product_snapshots" in table_names
    assert "supplier_offer_price_tiers" in table_names
    assert "test_buy_recommendations" in table_names
    cost_profile_columns = {column["name"] for column in inspector.get_columns("cost_profiles")}
    assert {
        "marketplace_id",
        "profile_scope_key",
        "version",
        "configuration_checksum",
        "selling_price_tax_basis",
        "fee_source",
        "fee_effective_at",
        "effective_to",
    }.issubset(cost_profile_columns)
    supplier_offer_columns = {column["name"] for column in inspector.get_columns("supplier_offers")}
    assert "supplier_name_at_quote" in supplier_offer_columns
    test_buy_columns = {
        column["name"] for column in inspector.get_columns("test_buy_recommendations")
    }
    assert {
        "source_snapshot_id",
        "data_confidence_score_result_id",
        "evidence",
        "outcome",
    }.issubset(test_buy_columns)
    import_columns = {column["name"] for column in inspector.get_columns("import_batches")}
    assert {
        "dataset_schema_id",
        "dataset_schema_version",
        "dataset_schema_match",
        "dataset_schema_checksum",
        "source_header_checksum",
        "source_column_count",
        "observation_date_candidates",
        "observed_on_suggestion",
        "observation_suggestion_source",
        "observed_on",
        "observed_on_source",
        "period_month",
        "dataset_revision",
    }.issubset(import_columns)
    snapshot_columns = {column["name"] for column in inspector.get_columns("product_snapshots")}
    assert {"observed_on", "observed_on_source", "source_payload"}.issubset(snapshot_columns)
    engine.dispose()

    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    engine = create_engine(database_url)
    assert "organisations" not in inspect(engine).get_table_names()
    engine.dispose()


def test_phase_2_migration_preserves_legacy_combined_prep_packaging_cost(
    tmp_path: Path,
) -> None:
    backend_dir = Path(__file__).parents[1]
    database_path = tmp_path / "legacy-phase-2-migration.db"
    database_url = f"sqlite:///{database_path}"
    environment = {**os.environ, "DATABASE_URL": database_url}

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "0002_phase1_intelligence"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO organisations (id, name, created_at) "
                "VALUES (:id, :name, :created_at)"
            ),
            {
                "id": "legacy-cost-org",
                "name": "Synthetic legacy seller",
                "created_at": "2026-01-01 00:00:00+00:00",
            },
        )
        connection.execute(
            text(
                "INSERT INTO marketplaces "
                "(id, organisation_id, code, name, default_currency_code) "
                "VALUES (:id, :organisation_id, :code, :name, :currency_code)"
            ),
            {
                "id": "legacy-cost-market",
                "organisation_id": "legacy-cost-org",
                "code": "IN",
                "name": "Amazon India",
                "currency_code": "INR",
            },
        )
        connection.execute(
            text(
                "INSERT INTO products "
                "(id, organisation_id, marketplace_id, asin, created_at) "
                "VALUES (:id, :organisation_id, :marketplace_id, :asin, :created_at)"
            ),
            {
                "id": "legacy-cost-product",
                "organisation_id": "legacy-cost-org",
                "marketplace_id": "legacy-cost-market",
                "asin": "B000LEGACY",
                "created_at": "2026-01-01 00:00:00+00:00",
            },
        )
        connection.execute(
            text(
                "INSERT INTO cost_profiles "
                "(id, organisation_id, product_id, currency_code, supplier_unit_cost, "
                "freight_cost, prep_packaging_cost, effective_from) "
                "VALUES (:id, :organisation_id, :product_id, :currency_code, "
                ":supplier_unit_cost, :freight_cost, :prep_packaging_cost, :effective_from)"
            ),
            [
                {
                    "id": "legacy-cost-profile-1",
                    "organisation_id": "legacy-cost-org",
                    "product_id": "legacy-cost-product",
                    "currency_code": "INR",
                    "supplier_unit_cost": "10.00",
                    "freight_cost": "1.00",
                    "prep_packaging_cost": "3.25",
                    "effective_from": "2026-01-01 00:00:00+00:00",
                },
                {
                    "id": "legacy-cost-profile-2",
                    "organisation_id": "legacy-cost-org",
                    "product_id": "legacy-cost-product",
                    "currency_code": "INR",
                    "supplier_unit_cost": "11.00",
                    "freight_cost": "1.25",
                    "prep_packaging_cost": "4.75",
                    "effective_from": "2026-02-01 00:00:00+00:00",
                },
            ],
        )
    engine.dispose()

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    engine = create_engine(database_url)
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, marketplace_id, profile_scope_key, version, "
                "supersedes_profile_id, effective_from, effective_to, prep_packaging_cost, "
                "prep_cost, packaging_cost, selling_price_tax_basis "
                "FROM cost_profiles ORDER BY version"
            )
        ).all()
        current_count = connection.scalar(
            text("SELECT COUNT(*) FROM cost_profiles WHERE effective_to IS NULL")
        )
    engine.dispose()

    assert len(rows) == 2
    first, second = rows
    assert first.marketplace_id == second.marketplace_id == "legacy-cost-market"
    assert first.profile_scope_key == second.profile_scope_key == "legacy-cost-product"
    assert (first.version, second.version) == (1, 2)
    assert first.supersedes_profile_id is None
    assert second.supersedes_profile_id == "legacy-cost-profile-1"
    assert str(first.effective_to).startswith("2026-02-01 00:00:00")
    assert second.effective_to is None
    assert current_count == 1
    for row, expected_combined in (
        (first, Decimal("3.25")),
        (second, Decimal("4.75")),
    ):
        assert Decimal(str(row.prep_packaging_cost)) == expected_combined
        assert Decimal(str(row.prep_cost)) + Decimal(str(row.packaging_cost)) == expected_combined
        assert Decimal(str(row.prep_cost)) == expected_combined
        assert Decimal(str(row.packaging_cost)) == Decimal("0")
        assert row.selling_price_tax_basis is None


def test_phase_2_preflight_guards_leave_0002_schema_retryable(tmp_path: Path) -> None:
    backend_dir = Path(__file__).parents[1]
    database_path = tmp_path / "phase-2-preflight.db"
    database_url = f"sqlite:///{database_path}"
    environment = {**os.environ, "DATABASE_URL": database_url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "0002_phase1_intelligence"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO organisations (id, name, created_at) "
                "VALUES ('preflight-org', 'Synthetic preflight seller', "
                "'2026-01-01 00:00:00+00:00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO marketplaces "
                "(id, organisation_id, code, name, default_currency_code) VALUES "
                "('preflight-market', 'preflight-org', 'IN', 'Amazon India', 'INR')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO products "
                "(id, organisation_id, marketplace_id, asin, created_at) VALUES "
                "('preflight-product', 'preflight-org', 'preflight-market', "
                "'B000PREFLT', '2026-01-01 00:00:00+00:00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO suppliers (id, organisation_id, name) VALUES "
                "('preflight-supplier', 'preflight-org', 'Synthetic supplier')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO cost_profiles "
                "(id, organisation_id, product_id, currency_code, supplier_unit_cost, "
                "freight_cost, prep_packaging_cost, effective_from) VALUES "
                "('ambiguous-default-cost', 'preflight-org', NULL, 'INR', 10, 1, 2, "
                "'2026-01-01 00:00:00+00:00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO supplier_offers "
                "(id, supplier_id, product_id, currency_code, unit_cost, "
                "minimum_order_quantity, lead_time_days, valid_until) VALUES "
                "('undated-legacy-offer', 'preflight-supplier', 'preflight-product', "
                "'INR', 9, 10, 14, NULL)"
            )
        )
    engine.dispose()

    default_failure = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert default_failure.returncode != 0
    assert "require explicit marketplace repair" in default_failure.stderr
    _assert_phase_2_preflight_left_schema_unchanged(database_url)

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM cost_profiles WHERE id = 'ambiguous-default-cost'"))
    engine.dispose()
    offer_failure = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert offer_failure.returncode != 0
    assert "require an explicit quotation date" in offer_failure.stderr
    _assert_phase_2_preflight_left_schema_unchanged(database_url)

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM supplier_offers WHERE id = 'undated-legacy-offer'"))
    engine.dispose()
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    engine = create_engine(database_url)
    assert "prep_cost" in {
        column["name"] for column in inspect(engine).get_columns("cost_profiles")
    }
    engine.dispose()


def test_phase_2_preflight_rejects_equal_effective_dates_before_ddl(tmp_path: Path) -> None:
    backend_dir = Path(__file__).parents[1]
    database_path = tmp_path / "phase-2-equal-effective-dates.db"
    database_url = f"sqlite:///{database_path}"
    environment = {**os.environ, "DATABASE_URL": database_url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "0002_phase1_intelligence"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO organisations (id, name, created_at) VALUES "
                "('equal-date-org', 'Synthetic equal-date seller', "
                "'2026-01-01 00:00:00+00:00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO marketplaces "
                "(id, organisation_id, code, name, default_currency_code) VALUES "
                "('equal-date-market', 'equal-date-org', 'IN', 'Amazon India', 'INR')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO products "
                "(id, organisation_id, marketplace_id, asin, created_at) VALUES "
                "('equal-date-product', 'equal-date-org', 'equal-date-market', "
                "'B000EQUAL1', '2026-01-01 00:00:00+00:00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO cost_profiles "
                "(id, organisation_id, product_id, currency_code, supplier_unit_cost, "
                "freight_cost, prep_packaging_cost, effective_from) VALUES "
                "(:id, 'equal-date-org', 'equal-date-product', 'INR', 10, 1, 2, "
                "'2026-01-01 00:00:00+00:00')"
            ),
            [{"id": "equal-date-profile-1"}, {"id": "equal-date-profile-2"}],
        )
    engine.dispose()

    failure = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert failure.returncode != 0
    assert "strictly increasing effective dates" in failure.stderr
    _assert_phase_2_preflight_left_schema_unchanged(database_url)

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM cost_profiles WHERE id = 'equal-date-profile-2'"))
    engine.dispose()
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def _assert_phase_2_preflight_left_schema_unchanged(database_url: str) -> None:
    engine = create_engine(database_url)
    inspector = inspect(engine)
    cost_columns = {column["name"] for column in inspector.get_columns("cost_profiles")}
    with engine.connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    assert revision == "0002_phase1_intelligence"
    assert "marketplace_id" not in cost_columns
    assert "prep_cost" not in cost_columns
    assert "supplier_offer_price_tiers" not in inspector.get_table_names()
    assert "test_buy_recommendations" not in inspector.get_table_names()
    engine.dispose()
