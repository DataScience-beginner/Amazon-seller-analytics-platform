from collections.abc import Generator
from io import BytesIO
from pathlib import Path

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
    Marketplace,
    Organisation,
    Product,
    ProductSnapshot,
    RawAttribute,
    ScoreResult,
    StrategyRecommendation,
)


def _workbook_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = "Keepa"
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
            json={},
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
            json={},
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
            json={},
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
                    json={},
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
            json={},
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
