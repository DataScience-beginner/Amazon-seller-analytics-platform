from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.imports.schemas import ImportDetailResponse, ImportListResponse, MappingUpdate
from app.modules.imports.service import (
    confirm_import,
    create_import_for_workspace,
    get_import,
    list_imports,
    update_mapping,
)
from app.modules.imports.storage import stage_xlsx_upload

router = APIRouter(prefix="/imports", tags=["imports"])


@router.get("", response_model=ImportListResponse)
def get_imports(
    organisation_id: Annotated[str, Query(min_length=1, max_length=36)],
    marketplace_id: Annotated[str, Query(min_length=1, max_length=36)],
    session: Annotated[Session, Depends(get_db)],
) -> ImportListResponse:
    return list_imports(
        session,
        organisation_id=organisation_id,
        marketplace_id=marketplace_id,
    )


@router.post("", response_model=ImportDetailResponse, status_code=status.HTTP_201_CREATED)
def post_import(
    file: Annotated[UploadFile, File()],
    organisation_id: Annotated[str, Form(min_length=1, max_length=36)],
    marketplace_id: Annotated[str, Form(min_length=1, max_length=36)],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImportDetailResponse:
    staged = stage_xlsx_upload(file, settings)
    try:
        return create_import_for_workspace(
            session,
            staged,
            settings,
            organisation_id=organisation_id,
            marketplace_id=marketplace_id,
        )
    except Exception:
        staged.path.unlink(missing_ok=True)
        raise


@router.get("/{import_id}", response_model=ImportDetailResponse)
def get_import_detail(
    import_id: str,
    organisation_id: Annotated[str, Query(min_length=1, max_length=36)],
    marketplace_id: Annotated[str, Query(min_length=1, max_length=36)],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImportDetailResponse:
    return get_import(
        session,
        import_id,
        settings,
        organisation_id=organisation_id,
        marketplace_id=marketplace_id,
    )


@router.put("/{import_id}/mapping", response_model=ImportDetailResponse)
def put_import_mapping(
    import_id: str,
    command: MappingUpdate,
    organisation_id: Annotated[str, Query(min_length=1, max_length=36)],
    marketplace_id: Annotated[str, Query(min_length=1, max_length=36)],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImportDetailResponse:
    return update_mapping(
        session,
        import_id,
        command,
        settings,
        organisation_id=organisation_id,
        marketplace_id=marketplace_id,
    )


@router.post("/{import_id}/confirm", response_model=ImportDetailResponse)
def post_import_confirmation(
    import_id: str,
    organisation_id: Annotated[str, Query(min_length=1, max_length=36)],
    marketplace_id: Annotated[str, Query(min_length=1, max_length=36)],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImportDetailResponse:
    return confirm_import(
        session,
        import_id,
        settings,
        organisation_id=organisation_id,
        marketplace_id=marketplace_id,
    )
