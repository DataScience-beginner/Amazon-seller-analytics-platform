from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.gst.schemas import (
    ApprovalCommand,
    FiledCommand,
    FilingCreate,
    FilingListResponse,
    FilingResponse,
    RegistrationCreate,
    RegistrationResponse,
)
from app.modules.gst.service import (
    add_amazon_gstr1,
    approve_filing,
    confirm_filed,
    create_filing,
    create_registration,
    export_working_paper,
    get_filing,
    list_filings,
    list_registrations,
)
from app.modules.imports.storage import stage_xlsx_upload

router = APIRouter(prefix="/financials/gst-india", tags=["gst-india"])


@router.get("/registrations", response_model=list[RegistrationResponse])
def registrations(
    organisation_id: Annotated[str, Query(min_length=1, max_length=36)],
    marketplace_id: Annotated[str, Query(min_length=1, max_length=36)],
    session: Annotated[Session, Depends(get_db)],
) -> list[RegistrationResponse]:
    return list_registrations(session, organisation_id, marketplace_id)


@router.post(
    "/registrations", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED
)
def post_registration(
    command: RegistrationCreate, session: Annotated[Session, Depends(get_db)]
) -> RegistrationResponse:
    return create_registration(session, command)


@router.get("/filings", response_model=FilingListResponse)
def filings(
    organisation_id: Annotated[str, Query(min_length=1, max_length=36)],
    marketplace_id: Annotated[str, Query(min_length=1, max_length=36)],
    session: Annotated[Session, Depends(get_db)],
) -> FilingListResponse:
    return list_filings(session, organisation_id, marketplace_id)


@router.post("/filings", response_model=FilingResponse, status_code=status.HTTP_201_CREATED)
def post_filing(
    command: FilingCreate, session: Annotated[Session, Depends(get_db)]
) -> FilingResponse:
    return create_filing(session, command)


@router.get("/filings/{filing_id}", response_model=FilingResponse)
def filing(
    filing_id: str,
    organisation_id: Annotated[str, Query(min_length=1, max_length=36)],
    marketplace_id: Annotated[str, Query(min_length=1, max_length=36)],
    session: Annotated[Session, Depends(get_db)],
) -> FilingResponse:
    return get_filing(session, filing_id, organisation_id, marketplace_id)


@router.post("/filings/{filing_id}/amazon-gstr1", response_model=FilingResponse)
def post_amazon_gstr1(
    filing_id: str,
    file: Annotated[UploadFile, File()],
    organisation_id: Annotated[str, Form(min_length=1, max_length=36)],
    marketplace_id: Annotated[str, Form(min_length=1, max_length=36)],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FilingResponse:
    staged = stage_xlsx_upload(file, settings, purpose="GST report")
    try:
        return add_amazon_gstr1(session, filing_id, organisation_id, marketplace_id, staged)
    except Exception:
        staged.path.unlink(missing_ok=True)
        raise


@router.post("/filings/{filing_id}/approve", response_model=FilingResponse)
def post_approval(
    filing_id: str,
    command: Annotated[ApprovalCommand, Body()],
    organisation_id: Annotated[str, Query(min_length=1, max_length=36)],
    marketplace_id: Annotated[str, Query(min_length=1, max_length=36)],
    session: Annotated[Session, Depends(get_db)],
) -> FilingResponse:
    assert command.completeness_confirmed
    return approve_filing(session, filing_id, organisation_id, marketplace_id)


@router.post("/filings/{filing_id}/working-paper")
def working_paper(
    filing_id: str,
    organisation_id: Annotated[str, Query(min_length=1, max_length=36)],
    marketplace_id: Annotated[str, Query(min_length=1, max_length=36)],
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    filename, content = export_working_paper(session, filing_id, organisation_id, marketplace_id)
    return Response(
        content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/filings/{filing_id}/confirm-filed", response_model=FilingResponse)
def post_filed_confirmation(
    filing_id: str,
    command: FiledCommand,
    organisation_id: Annotated[str, Query(min_length=1, max_length=36)],
    marketplace_id: Annotated[str, Query(min_length=1, max_length=36)],
    session: Annotated[Session, Depends(get_db)],
) -> FilingResponse:
    return confirm_filed(session, filing_id, organisation_id, marketplace_id, command)
