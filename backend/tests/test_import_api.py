from collections.abc import Generator
from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, cast

import pytest
from httpx import ASGITransport, AsyncClient
from openpyxl import Workbook
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import create_app
from app.models.domain import (
    ImportBatch,
    ImportStatus,
    Marketplace,
    Organisation,
    Product,
    ProductSnapshot,
    RawAttribute,
    ScoreResult,
    StrategyRecommendation,
)
from app.modules.imports import service as import_service
from app.modules.imports.dataset_schema import ProductFinderDatasetSchema


def _workbook_bytes(rows: list[list[object]], *, sheet_name: str = "Keepa") -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = sheet_name
    for row in rows:
        worksheet.append(row)
    destination = BytesIO()
    workbook.save(destination)
    workbook.close()
    return destination.getvalue()


@pytest.mark.anyio
async def test_import_is_transactional_explainable_and_idempotent(
    test_engine: Engine,
    tmp_path: Path,
) -> None:
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    with testing_session() as session:
        organisation = Organisation(name="Synthetic Seller")
        marketplace = Marketplace(
            organisation=organisation,
            code="US",
            name="Amazon US",
            default_currency_code="USD",
        )
        session.add_all([organisation, marketplace])
        session.commit()
        organisation_id = organisation.id
        marketplace_id = marketplace.id

    settings = Settings(
        database_url="sqlite://",
        upload_directory=tmp_path / "uploads",
        max_upload_size_bytes=2 * 1024 * 1024,
    )
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    workbook = _workbook_bytes(
        [
            [
                "ASIN",
                "Title",
                "Buy Box: Current",
                "Sales Rank: Current",
                "Monthly Sold",
                "Unmapped Keepa Signal",
            ],
            [
                "B000TEST11",
                "Synthetic Product",
                "24.99",
                1500,
                "not-a-number",
                "preserve-me",
            ],
            ["B000TEST11", "Duplicate Product", "23.99", 1600, 80, "duplicate"],
            ["bad", "Invalid Product", "12.00", 5000, 20, "invalid"],
        ]
    )
    transport = ASGITransport(app=app)
    scope_params = {
        "organisation_id": organisation_id,
        "marketplace_id": marketplace_id,
    }
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        upload = await client.post(
            "/api/v1/imports",
            data={"organisation_id": organisation_id, "marketplace_id": marketplace_id},
            files={
                "file": (
                    "synthetic-keepa.xlsx",
                    workbook,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

        assert upload.status_code == 201, upload.text
        pending = upload.json()
        assert pending["status"] == "pending"
        assert pending["mapping"]["missing_required"] == []
        assert pending["mapping"]["columns"][-1]["classification"] == "unknown"
        assert len(pending["preview_rows"]) == 3

        confirmation = await client.post(
            f"/api/v1/imports/{pending['id']}/confirm",
            params=scope_params,
            json={"observed_on": "2026-01-15"},
        )
        assert confirmation.status_code == 200, confirmation.text
        completed = confirmation.json()
        assert completed["status"] == "completed"
        assert completed["summary"] == {
            "total": 3,
            "created": 1,
            "matched": 0,
            "skipped": 1,
            "failed": 1,
            "row_error_count": 3,
        }

        repeated_confirmation = await client.post(
            f"/api/v1/imports/{pending['id']}/confirm",
            params=scope_params,
            json={"observed_on": "2026-01-15"},
        )
        assert repeated_confirmation.status_code == 200
        assert repeated_confirmation.json()["summary"] == completed["summary"]

        dashboard = await client.get(
            "/api/v1/dashboard",
            params={"organisation_id": organisation_id, "marketplace_id": marketplace_id},
        )
        assert dashboard.status_code == 200, dashboard.text
        assert dashboard.json()["tracked_product_count"] == 1
        assert dashboard.json()["latest_import"]["id"] == pending["id"]

        portfolio = await client.get(
            "/api/v1/products",
            params={"organisation_id": organisation_id, "marketplace_id": marketplace_id},
        )
        assert portfolio.status_code == 200, portfolio.text
        assert portfolio.json()["pagination"]["total_items"] == 1
        product_id = portfolio.json()["items"][0]["product_id"]
        detail = await client.get(
            f"/api/v1/products/{product_id}",
            params={"organisation_id": organisation_id, "marketplace_id": marketplace_id},
        )
        assert detail.status_code == 200, detail.text
        assert len(detail.json()["latest_snapshot"]["scores"]) == 5
        assert len(detail.json()["latest_snapshot"]["recommendation"]["evidence"]) >= 2

        duplicate_upload = await client.post(
            "/api/v1/imports",
            data={"organisation_id": organisation_id, "marketplace_id": marketplace_id},
            files={
                "file": (
                    "same-content.xlsx",
                    workbook,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert duplicate_upload.status_code == 201
        assert duplicate_upload.json()["id"] == pending["id"]
        assert duplicate_upload.json()["duplicate"] is True

        next_month = _workbook_bytes(
            [
                [
                    "ASIN",
                    "Title",
                    "Buy Box: Current",
                    "Sales Rank: Current",
                    "Monthly Sold",
                    "Unmapped Keepa Signal",
                ],
                ["B000TEST11", "Synthetic Product Updated", "25.49", 1400, 95, "preserve-next"],
            ]
        )
        next_upload = await client.post(
            "/api/v1/imports",
            data={"organisation_id": organisation_id, "marketplace_id": marketplace_id},
            files={
                "file": (
                    "synthetic-keepa-next-month.xlsx",
                    next_month,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert next_upload.status_code == 201
        next_confirmation = await client.post(
            f"/api/v1/imports/{next_upload.json()['id']}/confirm",
            params=scope_params,
            json={"observed_on": "2026-02-15"},
        )
        assert next_confirmation.status_code == 200
        assert next_confirmation.json()["summary"] == {
            "total": 1,
            "created": 0,
            "matched": 1,
            "skipped": 0,
            "failed": 0,
            "row_error_count": 0,
        }

        history = await client.get(
            f"/api/v1/products/{product_id}",
            params={"organisation_id": organisation_id, "marketplace_id": marketplace_id},
        )
        assert len(history.json()["snapshot_history"]) == 2
        assert len(history.json()["strategy_history"]) == 2

    with testing_session() as session:
        assert session.scalar(select(func.count(ImportBatch.id))) == 2
        assert session.scalar(select(func.count(Product.id))) == 1
        assert session.scalar(select(func.count(ProductSnapshot.id))) == 2
        assert session.scalar(select(func.count(ScoreResult.id))) == 10
        assert session.scalar(select(func.count(StrategyRecommendation.id))) == 2
        raw_attributes = session.scalars(select(RawAttribute)).all()
        assert {raw.source_header for raw in raw_attributes} == {
            "Monthly Sold",
            "Unmapped Keepa Signal",
        }
        assert {raw.value for raw in raw_attributes} == {
            "not-a-number",
            "preserve-me",
            "preserve-next",
            95,
        }


@pytest.mark.anyio
async def test_mapping_decision_is_stored_and_replayed(
    test_engine: Engine,
    tmp_path: Path,
) -> None:
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    with testing_session() as session:
        organisation = Organisation(name="Mapping Seller")
        marketplace = Marketplace(
            organisation=organisation,
            code="GB",
            name="Amazon UK",
            default_currency_code="GBP",
        )
        other_organisation = Organisation(name="Other Mapping Seller")
        other_marketplace = Marketplace(
            organisation=other_organisation,
            code="US",
            name="Amazon US",
            default_currency_code="USD",
        )
        session.add_all([organisation, marketplace, other_organisation, other_marketplace])
        session.commit()
        organisation_id = organisation.id
        marketplace_id = marketplace.id
        invalid_scopes = (
            {
                "organisation_id": other_organisation.id,
                "marketplace_id": marketplace.id,
            },
            {
                "organisation_id": organisation.id,
                "marketplace_id": other_marketplace.id,
            },
        )

    settings = Settings(database_url="sqlite://", upload_directory=tmp_path / "uploads")
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    workbook = _workbook_bytes(
        [["ASIN", "Supplier Description"], ["B000TEST12", "Synthetic title"]]
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        upload = await client.post(
            "/api/v1/imports",
            data={"organisation_id": organisation_id, "marketplace_id": marketplace_id},
            files={"file": ("mapping.xlsx", workbook, "application/octet-stream")},
        )
        import_id = upload.json()["id"]
        for invalid_scope in invalid_scopes:
            cross_tenant_responses = (
                await client.get(f"/api/v1/imports/{import_id}", params=invalid_scope),
                await client.put(
                    f"/api/v1/imports/{import_id}/mapping",
                    params=invalid_scope,
                    json={"mappings": {"2": "title"}},
                ),
                await client.post(
                    f"/api/v1/imports/{import_id}/confirm",
                    params=invalid_scope,
                    json={"observed_on": "2026-01-15"},
                ),
            )
            for cross_tenant in cross_tenant_responses:
                assert cross_tenant.status_code == 404
                assert cross_tenant.json()["error"]["code"] == "resource_not_found"

        scope_params = {
            "organisation_id": organisation_id,
            "marketplace_id": marketplace_id,
        }
        update = await client.put(
            f"/api/v1/imports/{import_id}/mapping",
            params=scope_params,
            json={"mappings": {"2": "title"}},
        )
        assert update.status_code == 200, update.text
        mapped_column = update.json()["mapping"]["columns"][1]
        assert mapped_column["canonical_field"] == "title"
        assert mapped_column["classification"] == "optional"

        detail = await client.get(
            f"/api/v1/imports/{import_id}",
            params=scope_params,
        )
        assert detail.status_code == 200
        assert detail.json()["mapping"]["columns"][1]["canonical_field"] == "title"


@pytest.mark.anyio
async def test_non_xlsx_upload_has_safe_error_envelope(
    test_engine: Engine,
    tmp_path: Path,
) -> None:
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    settings = Settings(database_url="sqlite://", upload_directory=tmp_path / "uploads")
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/imports",
            data={"organisation_id": "org", "marketplace_id": "market"},
            files={"file": ("unsafe.csv", b"ASIN\nB000TEST13", "text/csv")},
        )

    assert response.status_code == 415
    payload = response.json()["error"]
    assert payload["code"] == "unsupported_file_type"
    assert payload["correlation_id"]
    assert "traceback" not in response.text.casefold()


@pytest.mark.anyio
async def test_corrupt_xlsx_is_recorded_failed_without_staged_content(
    test_engine: Engine,
    tmp_path: Path,
) -> None:
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    with testing_session() as session:
        organisation = Organisation(name="Validation Seller")
        marketplace = Marketplace(
            organisation=organisation,
            code="CA",
            name="Amazon Canada",
            default_currency_code="CAD",
        )
        session.add_all([organisation, marketplace])
        session.commit()
        organisation_id = organisation.id
        marketplace_id = marketplace.id

    upload_directory = tmp_path / "uploads"
    settings = Settings(database_url="sqlite://", upload_directory=upload_directory)
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/imports",
            data={"organisation_id": organisation_id, "marketplace_id": marketplace_id},
            files={"file": ("corrupt.xlsx", b"not-an-ooxml-archive", "application/octet-stream")},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "corrupt_workbook"
    with testing_session() as session:
        failed = session.scalar(select(ImportBatch))
        assert failed is not None
        assert failed.status.value == "failed"
        assert failed.failure_code == "corrupt_workbook"
        assert failed.storage_key is None
    assert list(upload_directory.iterdir()) == []


@pytest.mark.parametrize(
    ("failure_mode", "expected_status", "expected_code"),
    [
        ("corrupt", 422, "corrupt_workbook"),
        ("missing", 409, "import_file_unavailable"),
    ],
)
@pytest.mark.anyio
async def test_confirmation_file_failure_is_terminal_and_transactional(
    test_engine: Engine,
    tmp_path: Path,
    failure_mode: str,
    expected_status: int,
    expected_code: str,
) -> None:
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    with testing_session() as session:
        organisation = Organisation(name="Confirmation Failure Seller")
        marketplace = Marketplace(
            organisation=organisation,
            code="AU",
            name="Amazon Australia",
            default_currency_code="AUD",
        )
        session.add_all([organisation, marketplace])
        session.commit()
        scope_params = {
            "organisation_id": organisation.id,
            "marketplace_id": marketplace.id,
        }

    upload_directory = tmp_path / "uploads"
    settings = Settings(database_url="sqlite://", upload_directory=upload_directory)
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    workbook = _workbook_bytes([["ASIN", "Title"], ["B000TEST14", "Confirmation failure product"]])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        upload = await client.post(
            "/api/v1/imports",
            data=scope_params,
            files={"file": ("confirmation-failure.xlsx", workbook, "application/octet-stream")},
        )
        assert upload.status_code == 201, upload.text
        import_id = upload.json()["id"]

        with testing_session() as session:
            batch = session.get(ImportBatch, import_id)
            assert batch is not None
            assert batch.storage_key is not None
            staged_path = upload_directory / batch.storage_key

        if failure_mode == "corrupt":
            staged_path.write_bytes(b"not-an-ooxml-archive")
        else:
            staged_path.unlink()

        confirmation = await client.post(
            f"/api/v1/imports/{import_id}/confirm",
            params=scope_params,
            json={"observed_on": "2026-01-15"},
        )
        assert confirmation.status_code == expected_status
        assert confirmation.json()["error"]["code"] == expected_code

        detail = await client.get(
            f"/api/v1/imports/{import_id}",
            params=scope_params,
        )
        assert detail.status_code == 200
        assert detail.json()["status"] == "failed"
        assert detail.json()["failure"]["code"] == expected_code

    with testing_session() as session:
        failed = session.get(ImportBatch, import_id)
        assert failed is not None
        assert failed.status.value == "failed"
        assert failed.failure_code == expected_code
        assert failed.storage_key is None
        assert session.scalar(select(func.count(Product.id))) == 0
        assert session.scalar(select(func.count(ProductSnapshot.id))) == 0
    assert list(upload_directory.iterdir()) == []


@pytest.mark.anyio
async def test_exact_v1_dataset_requires_date_and_preserves_all_173_source_values(
    test_engine: Engine,
    tmp_path: Path,
) -> None:
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    with testing_session() as session:
        organisation = Organisation(name="Dated Dataset Seller")
        marketplace = Marketplace(
            organisation=organisation,
            code="IN",
            name="Amazon India",
            default_currency_code="INR",
        )
        session.add_all([organisation, marketplace])
        session.commit()
        scope = {
            "organisation_id": organisation.id,
            "marketplace_id": marketplace.id,
        }

    schema = ProductFinderDatasetSchema.default()
    values: list[object] = [None] * len(schema.headers)
    values[schema.headers.index("Locale")] = "in"
    values[schema.headers.index("Title")] = "Synthetic dated product"
    values[schema.headers.index("Buy Box: Current")] = "1299.00"
    values[schema.headers.index("ASIN")] = "B000DATE01"
    values[schema.headers.index("Business Discount: Percentage")] = "5"
    workbook = _workbook_bytes(
        [list(schema.headers), values],
        sheet_name="2026-05-26",
    )
    settings = Settings(database_url="sqlite://", upload_directory=tmp_path / "uploads")
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        upload = await client.post(
            "/api/v1/imports",
            data=scope,
            files={
                "file": (
                    "Synthetic-2026-05-26-ProductFinder.xlsx",
                    workbook,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert upload.status_code == 201, upload.text
        pending = upload.json()
        dataset = pending["dataset"]
        assert dataset["schema_id"] == "keepa.product_finder"
        assert dataset["schema_version"] == "1.0.0"
        assert dataset["schema_match"] == "exact"
        assert dataset["source_column_count"] == 173
        assert dataset["registered_column_count"] == 173
        assert dataset["matched_column_count"] == 173
        assert dataset["new_headers"] == []
        assert dataset["missing_headers"] == []
        assert dataset["observed_on"] is None
        assert dataset["date_status"] == "pending_confirmation"
        assert dataset["observation_date_candidates"] == [
            {"date": "2026-05-26", "source": "sheet_name"},
            {"date": "2026-05-26", "source": "filename"},
        ]
        assert dataset["observed_on_suggestion"] == "2026-05-26"
        assert dataset["suggestion_source"] == "sheet_name"
        assert len(dataset["dataset_schema_checksum"]) == 64
        assert len(dataset["source_header_checksum"]) == 64
        mapping_columns = pending["mapping"]["columns"]
        column_classes = [column["dataset_classification"] for column in mapping_columns]
        assert column_classes.count("registered_source") == 173
        assert column_classes.count("unrecognized") == 0
        assert sum(column["canonical_field"] is not None for column in mapping_columns) == 21
        assert (
            sum(
                column["dataset_classification"] == "registered_source"
                and column["canonical_field"] is None
                for column in mapping_columns
            )
            == 152
        )

        missing_command = await client.post(
            f"/api/v1/imports/{pending['id']}/confirm",
            params=scope,
        )
        assert missing_command.status_code == 422

        confirmation = await client.post(
            f"/api/v1/imports/{pending['id']}/confirm",
            params=scope,
            json={"observed_on": "2026-05-26"},
        )
        assert confirmation.status_code == 200, confirmation.text
        completed_dataset = confirmation.json()["dataset"]
        assert completed_dataset["observed_on"] == "2026-05-26"
        assert completed_dataset["date_status"] == "confirmed"
        assert completed_dataset["period_month"] == "2026-05-01"
        assert completed_dataset["revision"] == 1
        assert completed_dataset["observed_on_source"] == "user_confirmed"

        repeated = await client.post(
            f"/api/v1/imports/{pending['id']}/confirm",
            params=scope,
            json={"observed_on": "2026-05-26"},
        )
        assert repeated.status_code == 200
        conflicting = await client.post(
            f"/api/v1/imports/{pending['id']}/confirm",
            params=scope,
            json={"observed_on": "2026-05-27"},
        )
        assert conflicting.status_code == 409
        assert conflicting.json()["error"]["code"] == "import_observed_on_conflict"

        products = await client.get("/api/v1/products", params=scope)
        assert products.status_code == 200
        item = products.json()["items"][0]
        assert item["latest_observed_on"] == "2026-05-26"
        detail = await client.get(
            f"/api/v1/products/{item['product_id']}",
            params=scope,
        )
        assert detail.status_code == 200
        assert detail.json()["latest_snapshot"]["observed_on"] == "2026-05-26"
        dashboard = await client.get("/api/v1/dashboard", params=scope)
        assert dashboard.status_code == 200
        assert dashboard.json()["latest_import"]["observed_on"] == "2026-05-26"
        assert dashboard.json()["latest_import"]["period_month"] == "2026-05-01"

    with testing_session() as session:
        batch = session.get(ImportBatch, pending["id"])
        snapshot = session.scalar(select(ProductSnapshot))
        assert batch is not None
        assert snapshot is not None
        assert batch.uploaded_at.tzinfo is not None
        assert batch.confirmed_at is not None
        assert batch.observed_on is not None
        assert batch.observed_on.isoformat() == "2026-05-26"
        assert snapshot.snapshot_at.tzinfo is not None
        assert snapshot.observed_on is not None
        assert snapshot.observed_on.isoformat() == "2026-05-26"
        assert len(snapshot.source_payload) == 173
        assert snapshot.source_payload[0] == {
            "ordinal": 1,
            "header": "Locale",
            "value": "in",
        }
        assert snapshot.source_payload[106] == {
            "ordinal": 107,
            "header": "ASIN",
            "value": "B000DATE01",
        }
        assert session.scalar(select(func.count(RawAttribute.id))) == 0


@pytest.mark.anyio
async def test_legacy_pending_import_recomputes_date_suggestion_and_remains_confirmable(
    test_engine: Engine,
    tmp_path: Path,
) -> None:
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    with testing_session() as session:
        organisation = Organisation(name="Legacy Pending Seller")
        marketplace = Marketplace(
            organisation=organisation,
            code="US",
            name="Amazon US",
            default_currency_code="USD",
        )
        session.add_all([organisation, marketplace])
        session.commit()
        scope = {
            "organisation_id": organisation.id,
            "marketplace_id": marketplace.id,
        }

    settings = Settings(database_url="sqlite://", upload_directory=tmp_path / "uploads")
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    workbook = _workbook_bytes(
        [["ASIN", "Title"], ["B000DATE02", "Synthetic legacy pending product"]],
        sheet_name="2026-04-30",
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        upload = await client.post(
            "/api/v1/imports",
            data=scope,
            files={"file": ("legacy-pending.xlsx", workbook, "application/octet-stream")},
        )
        assert upload.status_code == 201
        import_id = upload.json()["id"]

        with testing_session() as session:
            batch = session.get(ImportBatch, import_id)
            assert batch is not None
            batch.dataset_schema_id = None
            batch.dataset_schema_version = None
            batch.dataset_schema_match = None
            batch.dataset_schema_checksum = None
            batch.source_header_checksum = None
            batch.source_column_count = 0
            batch.observed_on_suggestion = None
            batch.observation_suggestion_source = None
            session.commit()

        detail = await client.get(f"/api/v1/imports/{import_id}", params=scope)
        assert detail.status_code == 200
        assert detail.json()["dataset"]["observed_on_suggestion"] == "2026-04-30"
        assert detail.json()["dataset"]["suggestion_source"] == "sheet_name"

        confirmed = await client.post(
            f"/api/v1/imports/{import_id}/confirm",
            params=scope,
            json={"observed_on": "2026-04-30"},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["dataset"]["schema_id"] == "keepa.unregistered"
        assert confirmed.json()["dataset"]["schema_match"] == "unregistered"
        assert confirmed.json()["dataset"]["period_month"] == "2026-04-01"
        assert confirmed.json()["dataset"]["revision"] == 1


@pytest.mark.anyio
async def test_monthly_revisions_are_append_only_and_history_ignores_revisions_and_future_data(
    test_engine: Engine,
    tmp_path: Path,
) -> None:
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    with testing_session() as session:
        organisation = Organisation(name="Revision Seller")
        marketplace = Marketplace(
            organisation=organisation,
            code="US",
            name="Amazon US",
            default_currency_code="USD",
        )
        session.add_all([organisation, marketplace])
        session.commit()
        scope = {
            "organisation_id": organisation.id,
            "marketplace_id": marketplace.id,
        }

    settings = Settings(database_url="sqlite://", upload_directory=tmp_path / "uploads")
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    transport = ASGITransport(app=app)

    async def upload_and_confirm(
        client: AsyncClient,
        *,
        title: str,
        observed_on: str,
    ) -> dict[str, Any]:
        workbook = _workbook_bytes(
            [
                ["ASIN", "Title", "Sales Rank: Current"],
                ["B000DATE03", title, 1000],
            ]
        )
        upload = await client.post(
            "/api/v1/imports",
            data=scope,
            files={
                "file": (
                    f"{title}.xlsx",
                    workbook,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert upload.status_code == 201, upload.text
        confirmation = await client.post(
            f"/api/v1/imports/{upload.json()['id']}/confirm",
            params=scope,
            json={"observed_on": observed_on},
        )
        assert confirmation.status_code == 200, confirmation.text
        return cast(dict[str, Any], confirmation.json())

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        may_revision_1 = await upload_and_confirm(
            client,
            title="Synthetic May revision one",
            observed_on="2026-05-26",
        )
        may_revision_2 = await upload_and_confirm(
            client,
            title="Synthetic May revision two",
            observed_on="2026-05-26",
        )
        with testing_session() as session:
            product_id = session.scalar(select(Product.id))
            assert product_id is not None
            assert (
                import_service._history_months(
                    session,
                    {product_id},
                    through_period=date(2026, 5, 1),
                )[product_id]
                == 1
            )
        june = await upload_and_confirm(
            client,
            title="Synthetic June evidence",
            observed_on="2026-06-15",
        )
        with testing_session() as session:
            product_id = session.scalar(select(Product.id))
            assert product_id is not None
            assert (
                import_service._history_months(
                    session,
                    {product_id},
                    through_period=date(2026, 6, 1),
                )[product_id]
                == 2
            )
        april_out_of_order = await upload_and_confirm(
            client,
            title="Synthetic April evidence",
            observed_on="2026-04-10",
        )
        with testing_session() as session:
            product_id = session.scalar(select(Product.id))
            assert product_id is not None
            assert (
                import_service._history_months(
                    session,
                    {product_id},
                    through_period=date(2026, 4, 1),
                )[product_id]
                == 1
            )

        assert may_revision_1["dataset"]["revision"] == 1
        assert may_revision_2["dataset"]["revision"] == 2
        assert june["dataset"]["revision"] == 1
        assert april_out_of_order["dataset"]["revision"] == 1

        products = await client.get("/api/v1/products", params=scope)
        product_item = products.json()["items"][0]
        assert product_item["title"] == "Synthetic June evidence"
        assert product_item["latest_observed_on"] == "2026-06-15"

    with testing_session() as session:
        snapshots = session.scalars(
            select(ProductSnapshot).order_by(ProductSnapshot.snapshot_at, ProductSnapshot.id)
        ).all()
        assert len(snapshots) == 4
        assert {
            snapshot.observed_on.isoformat() for snapshot in snapshots if snapshot.observed_on
        } == {
            "2026-04-10",
            "2026-05-26",
            "2026-06-15",
        }
        product_records = session.scalars(select(Product)).all()
        assert len(product_records) == 1
        product = product_records[0]
        assert product.latest_snapshot is not None
        assert product.latest_snapshot.observed_on is not None
        assert product.latest_snapshot.observed_on.isoformat() == "2026-06-15"

        assert session.scalar(select(func.count(StrategyRecommendation.id))) == 4


@pytest.mark.anyio
async def test_legacy_completed_import_exposes_unconfirmed_date_state(
    test_engine: Engine,
    tmp_path: Path,
) -> None:
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    with testing_session() as session:
        organisation = Organisation(name="Legacy Completed Seller")
        marketplace = Marketplace(
            organisation=organisation,
            code="US",
            name="Amazon US",
            default_currency_code="USD",
        )
        session.add_all([organisation, marketplace])
        session.flush()
        batch = ImportBatch(
            organisation_id=organisation.id,
            marketplace_id=marketplace.id,
            original_filename="legacy-completed.xlsx",
            checksum="legacy-completed-checksum",
            file_size_bytes=100,
            status=ImportStatus.completed,
            completed_at=datetime.now(UTC),
        )
        session.add(batch)
        session.commit()
        scope = {
            "organisation_id": organisation.id,
            "marketplace_id": marketplace.id,
        }
        import_id = batch.id

    settings = Settings(database_url="sqlite://", upload_directory=tmp_path / "uploads")
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        detail = await client.get(f"/api/v1/imports/{import_id}", params=scope)

    assert detail.status_code == 200
    dataset = detail.json()["dataset"]
    assert dataset["date_status"] == "legacy_unconfirmed"
    assert dataset["observed_on"] is None
    assert dataset["period_month"] is None
    assert dataset["revision"] is None
    assert dataset["observed_on_source"] is None
