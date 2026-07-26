from collections.abc import Generator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import create_app


@pytest.mark.anyio
async def test_local_workspace_bootstrap_and_listing(test_engine: Engine) -> None:
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="sqlite://",
        allow_unauthenticated_workspace_bootstrap=True,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/api/v1/workspaces",
            json={
                "organisation_name": "Synthetic Seller",
                "marketplace_code": "us",
                "marketplace_name": "Amazon US",
                "currency_code": "usd",
            },
        )
        listed = await client.get("/api/v1/workspaces")

    assert created.status_code == 201, created.text
    assert created.json()["marketplaces"][0]["code"] == "US"
    assert created.json()["marketplaces"][0]["default_currency_code"] == "USD"
    assert listed.status_code == 200
    assert listed.json()["items"] == [created.json()]


@pytest.mark.anyio
async def test_workspace_bootstrap_is_disabled_by_default(test_engine: Engine) -> None:
    testing_session = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="sqlite://",
        allow_unauthenticated_workspace_bootstrap=False,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/workspaces")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "workspace_bootstrap_disabled"
