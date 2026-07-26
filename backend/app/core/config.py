from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SellerOS"
    environment: str = "local"
    database_url: str = "sqlite:///./selleros.db"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    upload_directory: Path = Path("uploads")
    max_upload_size_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    max_workbook_uncompressed_bytes: int = Field(default=200 * 1024 * 1024, gt=0)
    max_workbook_sheets: int = Field(default=20, ge=1, le=100)
    max_workbook_rows: int = Field(default=100_000, ge=1)
    max_workbook_columns: int = Field(default=500, ge=1)
    import_preview_rows: int = Field(default=5, ge=1, le=20)
    allow_unauthenticated_workspace_bootstrap: bool = False
    frontend_dist_directory: Path | None = None
    preview_basic_auth_username: str | None = None
    preview_basic_auth_password: str | None = None

    @field_validator("database_url")
    @classmethod
    def select_psycopg3_driver(cls, value: str) -> str:
        """Make Railway's generic PostgreSQL URL explicit for the installed driver."""
        if value.startswith("postgres://"):
            return f"postgresql+psycopg://{value.removeprefix('postgres://')}"
        if value.startswith("postgresql://"):
            return f"postgresql+psycopg://{value.removeprefix('postgresql://')}"
        return value

    @model_validator(mode="after")
    def require_preview_access_lock_in_production(self) -> Self:
        if self.environment.casefold() != "production":
            return self
        if not self.preview_basic_auth_username or not self.preview_basic_auth_password:
            raise ValueError(
                "Production requires PREVIEW_BASIC_AUTH_USERNAME and "
                "PREVIEW_BASIC_AUTH_PASSWORD until tenant authentication is implemented"
            )
        if len(self.preview_basic_auth_password) < 16:
            raise ValueError("PREVIEW_BASIC_AUTH_PASSWORD must contain at least 16 characters")
        return self

    model_config = SettingsConfigDict(
        env_file=(Path(__file__).resolve().parents[3] / ".env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
