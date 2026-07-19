from pathlib import Path

from sqlalchemy.pool import StaticPool

from app.db.session import create_db_engine


def test_file_backed_sqlite_enables_integrity_wal_and_bounded_wait(tmp_path: Path) -> None:
    database_path = tmp_path / "selleros-test.db"
    engine = create_db_engine(f"sqlite:///{database_path}")
    try:
        with engine.connect() as connection:
            foreign_keys = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
            busy_timeout = connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one()
            journal_mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar_one()

        assert foreign_keys == 1
        assert busy_timeout == 1_000
        assert journal_mode == "wal"
    finally:
        engine.dispose()


def test_in_memory_sqlite_keeps_foreign_keys_without_forcing_wal() -> None:
    engine = create_db_engine("sqlite://", poolclass=StaticPool)
    try:
        with engine.connect() as connection:
            foreign_keys = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
            journal_mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar_one()

        assert foreign_keys == 1
        assert journal_mode == "memory"
    finally:
        engine.dispose()
