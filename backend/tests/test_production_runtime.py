from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.main import create_app


def test_railway_postgres_url_selects_installed_psycopg_driver() -> None:
    settings = Settings(
        database_url="postgresql://seller:secret@postgres.railway.internal:5432/selleros"
    )

    assert settings.database_url == (
        "postgresql+psycopg://seller:secret@postgres.railway.internal:5432/selleros"
    )


def test_production_configuration_fails_closed_without_preview_login() -> None:
    with pytest.raises(ValidationError, match="PREVIEW_BASIC_AUTH_USERNAME"):
        Settings(environment="production")


@pytest.mark.anyio
async def test_production_frontend_serves_assets_and_spa_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frontend = tmp_path / "frontend-dist"
    assets = frontend / "assets"
    assets.mkdir(parents=True)
    (frontend / "index.html").write_text("<main>SellerOS production shell</main>")
    (assets / "app.js").write_text("window.sellerOS = true;")
    settings = Settings(
        database_url="sqlite://",
        upload_directory=tmp_path / "uploads",
        frontend_dist_directory=frontend,
    )
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    get_settings.cache_clear()

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        page = await client.get("/dashboard")
        asset = await client.get("/assets/app.js")
        missing_api = await client.get("/api/v1/not-a-route")

    assert page.status_code == 200
    assert "SellerOS production shell" in page.text
    assert asset.status_code == 200
    assert asset.text == "window.sellerOS = true;"
    assert missing_api.status_code == 404
    assert missing_api.json()["error"]["code"] == "http_error"


@pytest.mark.anyio
async def test_preview_login_protects_frontend_and_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frontend = tmp_path / "frontend-dist"
    frontend.mkdir()
    (frontend / "index.html").write_text("<main>Protected SellerOS</main>")
    settings = Settings(
        environment="production",
        database_url="sqlite://",
        upload_directory=tmp_path / "uploads",
        frontend_dist_directory=frontend,
        preview_basic_auth_username="seller",
        preview_basic_auth_password="synthetic-password-123",
    )
    monkeypatch.setattr("app.main.get_settings", lambda: settings)

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        denied = await client.get("/dashboard")
        allowed = await client.get("/dashboard", auth=("seller", "synthetic-password-123"))

    assert denied.status_code == 401
    assert denied.headers["www-authenticate"] == 'Basic realm="SellerOS Preview"'
    assert allowed.status_code == 200
    assert "Protected SellerOS" in allowed.text


def test_configured_frontend_requires_built_index(tmp_path: Path) -> None:
    settings = Settings(
        database_url="sqlite://",
        upload_directory=tmp_path / "uploads",
        frontend_dist_directory=tmp_path / "missing-build",
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("app.main.get_settings", lambda: settings)
        with pytest.raises(RuntimeError, match="does not contain an index.html"):
            create_app()
