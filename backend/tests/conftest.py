from collections.abc import Generator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import create_db_engine


@pytest.fixture()
def test_engine() -> Generator[Engine, None, None]:
    engine = create_db_engine(
        "sqlite://",
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        # Disposing the sole StaticPool connection destroys this in-memory database.
        # Calling drop_all() is unsafe here because SQLite cannot defer the intentional
        # Product <-> latest snapshot foreign-key cycle while dropping tables.
        engine.dispose()


@pytest.fixture()
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    with testing_session() as session:
        yield session


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"
