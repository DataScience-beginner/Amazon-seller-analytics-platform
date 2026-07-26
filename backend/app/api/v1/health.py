from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health(
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    settings = get_settings()
    db.execute(text("SELECT 1"))
    return {"status": "ok", "application": settings.app_name, "database": "ok"}
