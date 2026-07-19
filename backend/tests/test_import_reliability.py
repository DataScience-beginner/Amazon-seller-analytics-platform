from __future__ import annotations

import logging
import sqlite3
from collections.abc import Generator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from openpyxl import Workbook
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import create_db_engine, get_db
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
from app.modules.imports import service as import_service


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


def _create_workspace(testing_session: sessionmaker[Session]) -> tuple[str, str]:
    with testing_session() as session:
        organisation = Organisation(name="Import Reliability Seller")
        marketplace = Marketplace(
            organisation=organisation,
            code="US",
            name="Amazon US",
            default_currency_code="USD",
        )
        session.add_all([organisation, marketplace])
        session.commit()
        return organisation.id, marketplace.id


def _configure_app(
    testing_session: sessionmaker[Session],
    settings: Settings,
) -> FastAPI:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    return app


class _SyntheticPostgresError(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__("synthetic driver failure")
        self.sqlstate = sqlstate


def test_operational_error_retry_classifier_is_closed_and_driver_aware() -> None:
    extended_busy = sqlite3.OperationalError("synthetic extended busy")
    extended_busy.sqlite_errorcode = sqlite3.SQLITE_BUSY | (2 << 8)
    sqlite_failure = OperationalError("statement", {}, extended_busy)
    postgres_retryable = OperationalError("statement", {}, _SyntheticPostgresError("40P01"))
    postgres_connection = OperationalError("statement", {}, _SyntheticPostgresError("08006"))
    postgres_permanent = OperationalError("statement", {}, _SyntheticPostgresError("23505"))

    assert import_service._is_retryable_operational_error(sqlite_failure) is True
    assert import_service._is_retryable_operational_error(postgres_retryable) is True
    assert import_service._is_retryable_operational_error(postgres_connection) is True
    assert import_service._is_retryable_operational_error(postgres_permanent) is False


@pytest.mark.anyio
async def test_locked_sqlite_confirmation_is_retryable_and_preserves_staged_import(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "locked-import.db"
    engine = create_db_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    organisation_id, marketplace_id = _create_workspace(testing_session)
    upload_directory = tmp_path / "uploads"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        upload_directory=upload_directory,
    )
    app = _configure_app(testing_session, settings)
    workbook = _workbook_bytes([["ASIN", "Title"], ["B000LOCK01", "Retryable lock product"]])
    scope = {"organisation_id": organisation_id, "marketplace_id": marketplace_id}
    locker: sqlite3.Connection | None = None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            upload = await client.post(
                "/api/v1/imports",
                data=scope,
                files={"file": ("lock.xlsx", workbook, "application/octet-stream")},
            )
            assert upload.status_code == 201, upload.text
            import_id = upload.json()["id"]

            with testing_session() as session:
                pending = session.get(ImportBatch, import_id)
                assert pending is not None
                assert pending.storage_key is not None
                storage_key = pending.storage_key
            staged_path = upload_directory / storage_key
            assert staged_path.is_file()

            locker = sqlite3.connect(database_path, timeout=0, isolation_level=None)
            locker.execute("BEGIN IMMEDIATE")
            confirmation = await client.post(
                f"/api/v1/imports/{import_id}/confirm",
                params=scope,
                json={},
            )

            assert confirmation.status_code == 503
            error = confirmation.json()["error"]
            assert error["code"] == "import_confirmation_retryable"
            assert error["details"] == {"import_id": import_id, "retryable": True}
            with testing_session() as session:
                retryable = session.get(ImportBatch, import_id)
                assert retryable is not None
                assert retryable.status.value == "pending"
                assert retryable.failure_code is None
                assert retryable.storage_key == storage_key
                assert retryable.total_rows == 0
                assert session.scalar(select(func.count(Product.id))) == 0
                assert session.scalar(select(func.count(ProductSnapshot.id))) == 0
            assert staged_path.is_file()

            locker.rollback()
            locker.close()
            locker = None

            retried = await client.post(
                f"/api/v1/imports/{import_id}/confirm",
                params=scope,
                json={},
            )
            assert retried.status_code == 200, retried.text
            assert retried.json()["status"] == "completed"
            assert retried.json()["summary"]["created"] == 1
            assert not staged_path.exists()
    finally:
        if locker is not None:
            if locker.in_transaction:
                locker.rollback()
            locker.close()
        engine.dispose()


@pytest.mark.anyio
async def test_wide_import_preserves_exact_raw_evidence_with_bounded_chunk_flushes(
    test_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    organisation_id, marketplace_id = _create_workspace(testing_session)
    settings = Settings(database_url="sqlite://", upload_directory=tmp_path / "uploads")
    app = _configure_app(testing_session, settings)
    unknown_headers = [f"Keepa Extra {index}" for index in range(1, 9)]
    row_count = 125
    workbook_rows: list[list[object]] = [["ASIN", "Title", "Buy Box: Current", *unknown_headers]]
    expected_raw_evidence: set[tuple[int, str, str]] = set()
    for index in range(row_count):
        source_row_number = index + 2
        unknown_values = [f"row-{index}-extra-{ordinal}" for ordinal in range(1, 9)]
        workbook_rows.append(
            [f"B{index:09d}", f"Synthetic product {index}", "19.99", *unknown_values]
        )
        expected_raw_evidence.update(
            (source_row_number, header, value)
            for header, value in zip(unknown_headers, unknown_values, strict=True)
        )

    chunk_sizes: list[int] = []
    original_flush_chunk = import_service._flush_snapshot_chunk

    def recording_flush_chunk(session: Session, persisted_rows: int) -> None:
        chunk_sizes.append(persisted_rows)
        original_flush_chunk(session, persisted_rows)

    monkeypatch.setattr(import_service, "_flush_snapshot_chunk", recording_flush_chunk)
    workbook = _workbook_bytes(workbook_rows)
    scope = {"organisation_id": organisation_id, "marketplace_id": marketplace_id}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        upload = await client.post(
            "/api/v1/imports",
            data=scope,
            files={"file": ("wide.xlsx", workbook, "application/octet-stream")},
        )
        assert upload.status_code == 201, upload.text
        confirmation = await client.post(
            f"/api/v1/imports/{upload.json()['id']}/confirm",
            params=scope,
            json={},
        )

    assert confirmation.status_code == 200, confirmation.text
    assert confirmation.json()["summary"] == {
        "total": row_count,
        "created": row_count,
        "matched": 0,
        "skipped": 0,
        "failed": 0,
        "row_error_count": 0,
    }
    assert chunk_sizes == [100, 25]

    with testing_session() as session:
        persisted_raw_evidence = {
            (source_row_number, source_header, value)
            for source_row_number, source_header, value in session.execute(
                select(
                    ProductSnapshot.source_row_number,
                    RawAttribute.source_header,
                    RawAttribute.value,
                ).join(RawAttribute, RawAttribute.snapshot_id == ProductSnapshot.id)
            )
        }
        assert persisted_raw_evidence == expected_raw_evidence
        assert session.scalar(select(func.count(Product.id))) == row_count
        assert (
            session.scalar(
                select(func.count(Product.id)).where(Product.latest_snapshot_id.is_not(None))
            )
            == row_count
        )
        assert (
            session.scalar(
                select(func.count(Product.id)).join(
                    ProductSnapshot,
                    (Product.latest_snapshot_id == ProductSnapshot.id)
                    & (Product.id == ProductSnapshot.product_id),
                )
            )
            == row_count
        )
        assert session.scalar(select(func.count(ProductSnapshot.id))) == row_count
        assert session.scalar(select(func.count(RawAttribute.id))) == row_count * len(
            unknown_headers
        )
        assert session.scalar(select(func.count(ScoreResult.id))) == row_count * 5
        assert session.scalar(select(func.count(StrategyRecommendation.id))) == row_count


@pytest.mark.anyio
async def test_unknown_operational_error_is_non_retryable_redacted_and_preserves_evidence(
    test_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    organisation_id, marketplace_id = _create_workspace(testing_session)
    upload_directory = tmp_path / "uploads"
    settings = Settings(database_url="sqlite://", upload_directory=upload_directory)
    app = _configure_app(testing_session, settings)
    secret = "PRIVATE-WORKBOOK-ROW-SENTINEL"
    workbook = _workbook_bytes([["ASIN", "Title"], ["B000DBERR1", secret]])
    scope = {"organisation_id": organisation_id, "marketplace_id": marketplace_id}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        upload = await client.post(
            "/api/v1/imports",
            data=scope,
            files={"file": ("unknown-db-error.xlsx", workbook, "application/octet-stream")},
        )
        assert upload.status_code == 201
        import_id = upload.json()["id"]
        with testing_session() as session:
            batch = session.get(ImportBatch, import_id)
            assert batch is not None and batch.storage_key is not None
            storage_key = batch.storage_key
        staged_path = upload_directory / storage_key

        def fail_with_unknown_operational_error(*_args: object, **_kwargs: object) -> None:
            raise OperationalError(
                "INSERT INTO products (title) VALUES (:private_title)",
                {"private_title": secret},
                RuntimeError("synthetic non-driver operational failure"),
            )

        monkeypatch.setattr(import_service, "_persist_rows", fail_with_unknown_operational_error)
        caplog.set_level(logging.ERROR, logger="app.modules.imports.service")
        confirmation = await client.post(
            f"/api/v1/imports/{import_id}/confirm",
            params=scope,
            json={},
        )

    assert confirmation.status_code == 500
    assert confirmation.json()["error"]["code"] == "import_confirmation_database_error"
    assert confirmation.json()["error"]["details"] == {
        "import_id": import_id,
        "retryable": False,
    }
    assert secret not in caplog.text
    with testing_session() as session:
        batch = session.get(ImportBatch, import_id)
        assert batch is not None
        assert batch.status.value == "pending"
        assert batch.storage_key == storage_key
        assert session.scalar(select(func.count(Product.id))) == 0
        assert session.scalar(select(func.count(ProductSnapshot.id))) == 0
    assert staged_path.is_file()


@pytest.mark.anyio
async def test_completed_cleanup_failure_is_nonfatal_retained_and_replayable(
    test_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    organisation_id, marketplace_id = _create_workspace(testing_session)
    upload_directory = tmp_path / "uploads"
    settings = Settings(database_url="sqlite://", upload_directory=upload_directory)
    app = _configure_app(testing_session, settings)
    workbook = _workbook_bytes(
        [
            [
                "ASIN",
                "Title",
            ],
            ["B000CLEAN1", "Cleanup replay product"],
        ]
    )
    scope = {"organisation_id": organisation_id, "marketplace_id": marketplace_id}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        upload = await client.post(
            "/api/v1/imports",
            data=scope,
            files={"file": ("cleanup.xlsx", workbook, "application/octet-stream")},
        )
        assert upload.status_code == 201
        import_id = upload.json()["id"]
        with testing_session() as session:
            batch = session.get(ImportBatch, import_id)
            assert batch is not None and batch.storage_key is not None
            storage_key = batch.storage_key
        staged_path = upload_directory / storage_key
        original_unlink = Path.unlink

        def fail_staged_unlink(path: Path, missing_ok: bool = False) -> None:
            if path == staged_path:
                raise OSError("synthetic cleanup failure")
            original_unlink(path, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", fail_staged_unlink)
        confirmation = await client.post(
            f"/api/v1/imports/{import_id}/confirm",
            params=scope,
            json={},
        )

        assert confirmation.status_code == 200
        assert confirmation.json()["status"] == "completed"
        with testing_session() as session:
            completed = session.get(ImportBatch, import_id)
            assert completed is not None
            assert completed.status.value == "completed"
            assert completed.storage_key == storage_key
        assert staged_path.is_file()

        monkeypatch.setattr(Path, "unlink", original_unlink)
        replay = await client.post(
            f"/api/v1/imports/{import_id}/confirm",
            params=scope,
            json={},
        )

    assert replay.status_code == 200
    assert not staged_path.exists()
    with testing_session() as session:
        completed = session.get(ImportBatch, import_id)
        assert completed is not None
        assert completed.storage_key is None


@pytest.mark.anyio
async def test_failed_import_cleanup_retains_reference_until_replayed(
    test_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    organisation_id, marketplace_id = _create_workspace(testing_session)
    upload_directory = tmp_path / "uploads"
    settings = Settings(database_url="sqlite://", upload_directory=upload_directory)
    app = _configure_app(testing_session, settings)
    workbook = _workbook_bytes(
        [
            [
                "ASIN",
                "Title",
            ],
            ["B000FAIL01", "Failure cleanup replay"],
        ]
    )
    scope = {"organisation_id": organisation_id, "marketplace_id": marketplace_id}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        upload = await client.post(
            "/api/v1/imports",
            data=scope,
            files={"file": ("failed-cleanup.xlsx", workbook, "application/octet-stream")},
        )
        import_id = upload.json()["id"]
        with testing_session() as session:
            batch = session.get(ImportBatch, import_id)
            assert batch is not None and batch.storage_key is not None
            storage_key = batch.storage_key
        staged_path = upload_directory / storage_key
        original_unlink = Path.unlink

        def fail_processing(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("synthetic processing failure")

        def fail_staged_unlink(path: Path, missing_ok: bool = False) -> None:
            if path == staged_path:
                raise OSError("synthetic cleanup failure")
            original_unlink(path, missing_ok=missing_ok)

        monkeypatch.setattr(import_service, "_persist_rows", fail_processing)
        monkeypatch.setattr(Path, "unlink", fail_staged_unlink)
        failed_response = await client.post(
            f"/api/v1/imports/{import_id}/confirm", params=scope, json={}
        )

        assert failed_response.status_code == 422
        with testing_session() as session:
            failed = session.get(ImportBatch, import_id)
            assert failed is not None
            assert failed.status.value == "failed"
            assert failed.storage_key == storage_key
        assert staged_path.is_file()

        monkeypatch.setattr(Path, "unlink", original_unlink)
        replay = await client.post(f"/api/v1/imports/{import_id}/confirm", params=scope, json={})

    assert replay.status_code == 409
    assert not staged_path.exists()
    with testing_session() as session:
        failed = session.get(ImportBatch, import_id)
        assert failed is not None
        assert failed.storage_key is None
