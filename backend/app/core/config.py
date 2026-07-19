from functools import lru_cache
from pathlib import Path

from pydantic import Field
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

    model_config = SettingsConfigDict(
        env_file=(Path(__file__).resolve().parents[3] / ".env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
