from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_SQLITE_BUSY_TIMEOUT_MS = 1_000


def create_db_engine(database_url: str, **engine_options: Any) -> Engine:
    url = make_url(database_url)
    is_sqlite = url.get_backend_name() == "sqlite"
    sqlite_database = url.database
    is_file_backed_sqlite = (
        is_sqlite
        and sqlite_database not in (None, "", ":memory:")
        and str(url.query.get("mode", "")).casefold() != "memory"
    )
    connect_args = dict(engine_options.pop("connect_args", {}))
    if is_sqlite:
        connect_args.setdefault("check_same_thread", False)
    if is_file_backed_sqlite:
        connect_args["timeout"] = _SQLITE_BUSY_TIMEOUT_MS / 1_000
    engine = create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
        **engine_options,
    )
    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _configure_sqlite_connection(dbapi_connection: Any, _connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
                if is_file_backed_sqlite:
                    cursor.execute(f"PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MS}")
                    cursor.execute("PRAGMA journal_mode=WAL")
            finally:
                cursor.close()

    return engine


settings = get_settings()
engine = create_db_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
