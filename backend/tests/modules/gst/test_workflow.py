from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.core.errors import ApplicationError, ConflictError
from app.models.domain import GstFilingStatus, Marketplace, Organisation
from app.modules.gst.schemas import FiledCommand, FilingCreate, RegistrationCreate
from app.modules.gst.service import (
    add_amazon_gstr1,
    approve_filing,
    confirm_filed,
    create_filing,
    create_registration,
    export_working_paper,
)
from app.modules.imports.storage import StagedUpload

HEADERS = {
    "B2B": ["Taxable Value", "Cess Amount"],
    "B2B CN (cdnr)": ["Taxable Value", "Cess Amount"],
    "B2CL CN (cdnur)": ["Taxable Value", "Cess Amount"],
    "B2C Large": ["Taxable Value", "Cess Amount"],
    "B2C Small": [
        "Type",
        "Place Of Supply",
        "Rate",
        "Taxable Value",
        "Cess Amount",
    ],
    "HSN Summary": [
        "HSN",
        "Total Value",
        "Taxable Value",
        "Integrated Tax Amount",
        "Central Tax Amount",
        "State/UT Tax Amount",
        "Cess Amount",
    ],
}


def _workbook(path: Path) -> None:
    workbook = Workbook()
    active = workbook.active
    assert active is not None
    workbook.remove(active)
    for name, headers in HEADERS.items():
        sheet = workbook.create_sheet(name)
        sheet.append([])
        sheet.append([])
        sheet.append([])
        sheet.append(headers)
        if name == "B2C Small":
            sheet.append(["OE", "29-Karnataka", 18, "1000.00", "0"])
        if name == "HSN Summary":
            sheet.append(["9503", "1180.00", "1000.00", "180.00", "0", "0", "0"])
    workbook.save(path)


def _workspace(session: Session) -> tuple[Organisation, Marketplace]:
    organisation = Organisation(name="Synthetic GST seller")
    marketplace = Marketplace(
        organisation=organisation,
        code="IN",
        name="Amazon India",
        default_currency_code="INR",
    )
    session.add_all([organisation, marketplace])
    session.commit()
    return organisation, marketplace


def _staged(path: Path, filename: str) -> StagedUpload:
    content = path.read_bytes()
    return StagedUpload(
        original_filename=filename,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        storage_key=path.name,
        path=path,
        size_bytes=len(content),
        checksum_sha256=hashlib.sha256(content).hexdigest(),
    )


def test_guided_gst_workflow_requires_approval_and_user_filing_confirmation(
    db_session: Session, tmp_path: Path
) -> None:
    organisation, marketplace = _workspace(db_session)
    registration = create_registration(
        db_session,
        RegistrationCreate(
            organisation_id=organisation.id,
            marketplace_id=marketplace.id,
            gstin="29ABCDE1234F1Z5",
            legal_name="Synthetic GST Seller",
        ),
    )
    filing = create_filing(
        db_session,
        FilingCreate(
            organisation_id=organisation.id,
            marketplace_id=marketplace.id,
            gst_registration_id=registration.id,
            period_month=date(2026, 4, 1),
        ),
    )
    workbook_path = tmp_path / "GSTR1-APRIL-2026-SYNTHETIC.xlsx"
    _workbook(workbook_path)
    filing = add_amazon_gstr1(
        db_session,
        filing.id,
        organisation.id,
        marketplace.id,
        _staged(workbook_path, workbook_path.name),
    )

    assert filing.status == GstFilingStatus.draft_ready
    assert filing.latest_draft is not None
    assert filing.latest_draft.totals["outward_taxable_value"] == "1000.00"
    assert filing.latest_draft.totals["hsn_integrated_tax_amount"] == "180.00"
    assert filing.documents[0].row_counts["B2C Small"] == 1
    with pytest.raises(ConflictError, match="Approve the draft"):
        export_working_paper(db_session, filing.id, organisation.id, marketplace.id)

    approved = approve_filing(db_session, filing.id, organisation.id, marketplace.id)
    assert approved.status == GstFilingStatus.approved
    filename, content = export_working_paper(db_session, filing.id, organisation.id, marketplace.id)
    assert filename.endswith("2026-04.json")
    assert b"not proof of filing" in content
    filed = confirm_filed(
        db_session,
        filing.id,
        organisation.id,
        marketplace.id,
        FiledCommand(arn="AA2904261234567"),
    )
    assert filed.status == GstFilingStatus.user_confirmed_filed
    assert filed.filed_arn == "AA2904261234567"


def test_amazon_gstr1_filename_period_must_match_selected_period(
    db_session: Session, tmp_path: Path
) -> None:
    organisation, marketplace = _workspace(db_session)
    registration = create_registration(
        db_session,
        RegistrationCreate(
            organisation_id=organisation.id,
            marketplace_id=marketplace.id,
            gstin="29ABCDE1234F1Z5",
            legal_name="Synthetic GST Seller",
        ),
    )
    filing = create_filing(
        db_session,
        FilingCreate(
            organisation_id=organisation.id,
            marketplace_id=marketplace.id,
            gst_registration_id=registration.id,
            period_month=date(2026, 4, 1),
        ),
    )
    workbook_path = tmp_path / "GSTR1-MAY-2026-SYNTHETIC.xlsx"
    _workbook(workbook_path)

    with pytest.raises(ApplicationError, match="does not match"):
        add_amazon_gstr1(
            db_session,
            filing.id,
            organisation.id,
            marketplace.id,
            _staged(workbook_path, workbook_path.name),
        )
