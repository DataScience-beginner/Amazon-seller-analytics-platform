from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ApplicationError
from app.db.session import get_db
from app.modules.workspaces.schemas import (
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceResponse,
)
from app.modules.workspaces.service import create_workspace, list_workspaces

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _ensure_bootstrap_enabled(settings: Settings) -> None:
    if not settings.allow_unauthenticated_workspace_bootstrap:
        raise ApplicationError(
            "workspace_bootstrap_disabled",
            "Workspace bootstrap is disabled in this environment",
            status_code=403,
        )


@router.get("", response_model=WorkspaceListResponse)
def get_workspaces(
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkspaceListResponse:
    _ensure_bootstrap_enabled(settings)
    return list_workspaces(session)


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def post_workspace(
    command: WorkspaceCreate,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkspaceResponse:
    _ensure_bootstrap_enabled(settings)
    return create_workspace(session, command)
