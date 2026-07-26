from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApplicationError, ConflictError, NotFoundError
from app.models.domain import (
    AuditEvent,
    GstDocumentStatus,
    GstExceptionStatus,
    GstFilingPeriod,
    GstFilingStatus,
    GstRegistration,
    GstReturnDraft,
    GstSourceDocument,
    GstValidationException,
    Marketplace,
)
from app.modules.gst.kernel import (
    FORMULA_VERSION,
    gstin_from_filename,
    parse_amazon_gstr1,
    period_from_filename,
)
from app.modules.gst.schemas import (
    DocumentResponse,
    DraftResponse,
    ExceptionResponse,
    FiledCommand,
    FilingCreate,
    FilingListResponse,
    FilingResponse,
    RegistrationCreate,
    RegistrationResponse,
    Scope,
)
from app.modules.imports.storage import StagedUpload

_GSTIN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")


def create_registration(session: Session, command: RegistrationCreate) -> RegistrationResponse:
    marketplace = _marketplace(session, command.organisation_id, command.marketplace_id)
    if marketplace.code.upper() != "IN":
        raise ApplicationError(
            "gst_india_marketplace_required",
            "GST India requires an IN marketplace",
            status_code=422,
        )
    if not _GSTIN.fullmatch(command.gstin):
        raise ApplicationError(
            "invalid_gstin_format", "Enter a valid 15-character GSTIN format", status_code=422
        )
    registration = GstRegistration(
        organisation_id=command.organisation_id,
        marketplace_id=command.marketplace_id,
        gstin=command.gstin,
        legal_name=command.legal_name,
        filing_frequency=command.filing_frequency,
    )
    session.add(registration)
    try:
        session.flush()
        _audit(
            session,
            command.organisation_id,
            "gst.registration.created",
            "gst_registration",
            registration.id,
        )
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ConflictError(
            "gst_registration_exists", "This GSTIN already exists in the workspace"
        ) from error
    return _registration_response(registration)


def list_registrations(
    session: Session, organisation_id: str, marketplace_id: str
) -> list[RegistrationResponse]:
    _marketplace(session, organisation_id, marketplace_id)
    items = session.scalars(
        select(GstRegistration)
        .where(
            GstRegistration.organisation_id == organisation_id,
            GstRegistration.marketplace_id == marketplace_id,
        )
        .order_by(GstRegistration.created_at, GstRegistration.id)
    ).all()
    return [_registration_response(item) for item in items]


def create_filing(session: Session, command: FilingCreate) -> FilingResponse:
    registration = _registration(
        session, command.organisation_id, command.marketplace_id, command.gst_registration_id
    )
    filing = GstFilingPeriod(
        organisation_id=command.organisation_id,
        marketplace_id=command.marketplace_id,
        gst_registration_id=registration.id,
        period_month=command.period_month,
    )
    session.add(filing)
    try:
        session.flush()
        _audit(
            session,
            command.organisation_id,
            "gst.filing.created",
            "gst_filing_period",
            filing.id,
        )
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ConflictError(
            "gst_filing_period_exists", "This GST filing period already exists"
        ) from error
    return get_filing(session, filing.id, command.organisation_id, command.marketplace_id)


def list_filings(session: Session, organisation_id: str, marketplace_id: str) -> FilingListResponse:
    _marketplace(session, organisation_id, marketplace_id)
    filings = session.scalars(
        select(GstFilingPeriod)
        .where(
            GstFilingPeriod.organisation_id == organisation_id,
            GstFilingPeriod.marketplace_id == marketplace_id,
        )
        .order_by(GstFilingPeriod.period_month.desc(), GstFilingPeriod.id)
    ).all()
    return FilingListResponse(
        items=[get_filing(session, item.id, organisation_id, marketplace_id) for item in filings]
    )


def get_filing(
    session: Session, filing_id: str, organisation_id: str, marketplace_id: str
) -> FilingResponse:
    filing = _filing(session, filing_id, organisation_id, marketplace_id)
    registration = _registration(
        session, organisation_id, marketplace_id, filing.gst_registration_id
    )
    documents = session.scalars(
        select(GstSourceDocument)
        .where(GstSourceDocument.filing_period_id == filing.id)
        .order_by(GstSourceDocument.uploaded_at, GstSourceDocument.id)
    ).all()
    exceptions = session.scalars(
        select(GstValidationException)
        .where(GstValidationException.filing_period_id == filing.id)
        .order_by(GstValidationException.created_at, GstValidationException.id)
    ).all()
    draft = session.scalar(
        select(GstReturnDraft)
        .where(GstReturnDraft.filing_period_id == filing.id)
        .order_by(GstReturnDraft.version.desc())
        .limit(1)
    )
    return FilingResponse(
        id=filing.id,
        scope=Scope(organisation_id=organisation_id, marketplace_id=marketplace_id),
        registration=_registration_response(registration),
        period_month=filing.period_month,
        status=filing.status,
        completeness_confirmed=filing.completeness_confirmed,
        approved_at=filing.approved_at,
        filed_arn=filing.filed_arn,
        filed_at=filing.filed_at,
        documents=[
            DocumentResponse(
                id=item.id,
                source_type=item.source_type,
                original_filename=item.original_filename,
                status=item.status,
                schema_version=item.schema_version,
                row_counts={
                    key: int(value)
                    for key, value in item.parsed_payload.get("row_counts", {}).items()
                },
                uploaded_at=item.uploaded_at,
            )
            for item in documents
        ],
        exceptions=[
            ExceptionResponse(
                id=item.id,
                code=item.code,
                severity=item.severity,
                message=item.message,
                status=item.status,
            )
            for item in exceptions
        ],
        latest_draft=_draft_response(draft) if draft else None,
        next_step=_next_step(filing, bool(documents), bool(draft), exceptions),
    )


def add_amazon_gstr1(
    session: Session,
    filing_id: str,
    organisation_id: str,
    marketplace_id: str,
    staged: StagedUpload,
) -> FilingResponse:
    filing = _filing(session, filing_id, organisation_id, marketplace_id)
    registration = _registration(
        session, organisation_id, marketplace_id, filing.gst_registration_id
    )
    if filing.status in {
        GstFilingStatus.approved,
        GstFilingStatus.exported,
        GstFilingStatus.user_confirmed_filed,
    }:
        raise ConflictError(
            "gst_filing_locked", "Approved or filed periods cannot accept new evidence"
        )
    detected_period = period_from_filename(staged.original_filename)
    if detected_period is not None and detected_period != filing.period_month:
        raise ApplicationError(
            "gst_document_period_mismatch",
            "The workbook period does not match the selected filing month",
            status_code=422,
        )
    detected_gstin = gstin_from_filename(staged.original_filename)
    if detected_gstin is not None and detected_gstin != registration.gstin:
        raise ApplicationError(
            "gst_document_registration_mismatch",
            "The workbook GSTIN does not match the selected GST registration",
            status_code=422,
        )
    if session.scalar(
        select(GstSourceDocument.id).where(
            GstSourceDocument.filing_period_id == filing.id,
            GstSourceDocument.checksum == staged.checksum_sha256,
        )
    ):
        raise ConflictError(
            "gst_document_duplicate", "This workbook is already attached to the period"
        )
    filing.status = GstFilingStatus.validating
    try:
        parsed = parse_amazon_gstr1(staged.path)
    except ValueError as error:
        session.rollback()
        raise ApplicationError("invalid_amazon_gstr1", str(error), status_code=422) from error
    document = GstSourceDocument(
        filing_period_id=filing.id,
        source_type="amazon_gstr1_ready_to_file",
        original_filename=staged.original_filename,
        checksum=staged.checksum_sha256,
        storage_key=staged.storage_key,
        status=GstDocumentStatus.parsed,
        schema_version=FORMULA_VERSION,
        parsed_payload={
            "row_counts": parsed.row_counts,
            "sections": parsed.sections,
            "totals": parsed.totals,
        },
    )
    session.add(document)
    version = (
        int(
            session.scalar(
                select(func.coalesce(func.max(GstReturnDraft.version), 0)).where(
                    GstReturnDraft.filing_period_id == filing.id
                )
            )
            or 0
        )
        + 1
    )
    session.add(
        GstReturnDraft(
            filing_period_id=filing.id,
            version=version,
            formula_version=FORMULA_VERSION,
            configuration_checksum=parsed.configuration_checksum,
            sections=parsed.sections,
            totals=parsed.totals,
        )
    )
    session.flush()
    _audit(
        session,
        organisation_id,
        "gst.amazon_gstr1.parsed",
        "gst_filing_period",
        filing.id,
        {"document_id": document.id, "draft_version": version},
    )
    filing.status = GstFilingStatus.draft_ready
    session.commit()
    return get_filing(session, filing.id, organisation_id, marketplace_id)


def approve_filing(
    session: Session, filing_id: str, organisation_id: str, marketplace_id: str
) -> FilingResponse:
    filing = _filing(session, filing_id, organisation_id, marketplace_id)
    draft = session.scalar(
        select(GstReturnDraft.id).where(GstReturnDraft.filing_period_id == filing.id).limit(1)
    )
    open_errors = session.scalar(
        select(func.count())
        .select_from(GstValidationException)
        .where(
            GstValidationException.filing_period_id == filing.id,
            GstValidationException.status == GstExceptionStatus.open,
            GstValidationException.severity == "error",
        )
    )
    if not draft or open_errors:
        raise ConflictError(
            "gst_draft_not_approvable", "Resolve all errors and generate a draft first"
        )
    filing.completeness_confirmed = True
    filing.approved_at = datetime.now(UTC)
    filing.status = GstFilingStatus.approved
    _audit(session, organisation_id, "gst.filing.approved", "gst_filing_period", filing.id)
    session.commit()
    return get_filing(session, filing.id, organisation_id, marketplace_id)


def export_working_paper(
    session: Session, filing_id: str, organisation_id: str, marketplace_id: str
) -> tuple[str, bytes]:
    filing = _filing(session, filing_id, organisation_id, marketplace_id)
    if filing.status not in {GstFilingStatus.approved, GstFilingStatus.exported}:
        raise ConflictError("gst_approval_required", "Approve the draft before downloading")
    draft = session.scalar(
        select(GstReturnDraft)
        .where(GstReturnDraft.filing_period_id == filing.id)
        .order_by(GstReturnDraft.version.desc())
        .limit(1)
    )
    if draft is None:
        raise NotFoundError("GST draft")
    filing.status = GstFilingStatus.exported
    _audit(session, organisation_id, "gst.working_paper.exported", "gst_filing_period", filing.id)
    session.commit()
    payload = {
        "label": "Calculated SellerOS GST working paper — not proof of filing",
        "period_month": filing.period_month.isoformat(),
        "formula_version": draft.formula_version,
        "configuration_checksum": draft.configuration_checksum,
        "sections": draft.sections,
        "totals": draft.totals,
    }
    return f"selleros-gst-working-paper-{filing.period_month:%Y-%m}.json", json.dumps(
        payload, indent=2, sort_keys=True
    ).encode()


def confirm_filed(
    session: Session,
    filing_id: str,
    organisation_id: str,
    marketplace_id: str,
    command: FiledCommand,
) -> FilingResponse:
    filing = _filing(session, filing_id, organisation_id, marketplace_id)
    if filing.status != GstFilingStatus.exported:
        raise ConflictError("gst_export_required", "Download the approved working paper first")
    filing.filed_arn = command.arn
    filing.filed_at = datetime.now(UTC)
    filing.status = GstFilingStatus.user_confirmed_filed
    _audit(
        session,
        organisation_id,
        "gst.filing.user_confirmed",
        "gst_filing_period",
        filing.id,
    )
    session.commit()
    return get_filing(session, filing.id, organisation_id, marketplace_id)


def _marketplace(session: Session, organisation_id: str, marketplace_id: str) -> Marketplace:
    marketplace = session.scalar(
        select(Marketplace).where(
            Marketplace.id == marketplace_id, Marketplace.organisation_id == organisation_id
        )
    )
    if marketplace is None:
        raise NotFoundError("Marketplace")
    return marketplace


def _registration(
    session: Session, organisation_id: str, marketplace_id: str, registration_id: str
) -> GstRegistration:
    registration = session.scalar(
        select(GstRegistration).where(
            GstRegistration.id == registration_id,
            GstRegistration.organisation_id == organisation_id,
            GstRegistration.marketplace_id == marketplace_id,
        )
    )
    if registration is None:
        raise NotFoundError("GST registration")
    return registration


def _filing(
    session: Session, filing_id: str, organisation_id: str, marketplace_id: str
) -> GstFilingPeriod:
    filing = session.scalar(
        select(GstFilingPeriod).where(
            GstFilingPeriod.id == filing_id,
            GstFilingPeriod.organisation_id == organisation_id,
            GstFilingPeriod.marketplace_id == marketplace_id,
        )
    )
    if filing is None:
        raise NotFoundError("GST filing period")
    return filing


def _registration_response(item: GstRegistration) -> RegistrationResponse:
    return RegistrationResponse(
        id=item.id,
        organisation_id=item.organisation_id,
        marketplace_id=item.marketplace_id,
        gstin_masked=f"{item.gstin[:2]}•••••••••••{item.gstin[-2:]}",
        legal_name=item.legal_name,
        filing_frequency=item.filing_frequency,
    )


def _draft_response(item: GstReturnDraft) -> DraftResponse:
    return DraftResponse(
        id=item.id,
        version=item.version,
        formula_version=item.formula_version,
        configuration_checksum=item.configuration_checksum,
        sections=item.sections,
        totals={key: str(value) for key, value in item.totals.items()},
        created_at=item.created_at,
    )


def _next_step(
    filing: GstFilingPeriod,
    has_document: bool,
    has_draft: bool,
    exceptions: Sequence[GstValidationException],
) -> str:
    if filing.status == GstFilingStatus.user_confirmed_filed:
        return "Filing evidence recorded. Retain the ARN and filed return."
    if filing.status == GstFilingStatus.exported:
        return "File on the GST Portal, then record the ARN."
    if filing.status == GstFilingStatus.approved:
        return "Download the calculated working paper."
    if any(item.status == GstExceptionStatus.open for item in exceptions):
        return "Resolve the open validation exceptions."
    if has_draft:
        return "Review the draft and confirm all outward supplies are included."
    if has_document:
        return "Wait for validation to complete."
    return "Upload the Amazon GST Ready-to-File GSTR-1 workbook."


def _audit(
    session: Session,
    organisation_id: str,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditEvent(
            organisation_id=organisation_id,
            actor_type="user",
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            event_payload=payload or {},
        )
    )
