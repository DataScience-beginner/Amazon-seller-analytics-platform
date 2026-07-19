from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_db
from app.main import create_app


@pytest.mark.anyio
async def test_health_endpoint_reports_database_ok(test_engine: Engine) -> None:
    app = create_app()
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[Session, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "application": "SellerOS", "database": "ok"}
