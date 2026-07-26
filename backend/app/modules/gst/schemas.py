from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.models.domain import GstDocumentStatus, GstExceptionStatus, GstFilingStatus

ScopeId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=36)]
Gstin = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=15, max_length=15)
]


class Scope(BaseModel):
    organisation_id: ScopeId
    marketplace_id: ScopeId


class RegistrationCreate(Scope):
    gstin: Gstin
    legal_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    filing_frequency: Literal["monthly", "quarterly"] = "monthly"


class RegistrationResponse(BaseModel):
    id: str
    organisation_id: str
    marketplace_id: str
    gstin_masked: str
    legal_name: str
    filing_frequency: str


class FilingCreate(Scope):
    gst_registration_id: ScopeId
    period_month: date

    @field_validator("period_month")
    @classmethod
    def first_of_month(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("period_month must be the first day of a month")
        return value


class DocumentResponse(BaseModel):
    id: str
    source_type: str
    original_filename: str
    status: GstDocumentStatus
    schema_version: str | None
    row_counts: dict[str, int]
    uploaded_at: datetime


class ExceptionResponse(BaseModel):
    id: str
    code: str
    severity: str
    message: str
    status: GstExceptionStatus


class DraftResponse(BaseModel):
    id: str
    version: int
    formula_version: str
    configuration_checksum: str
    sections: dict[str, list[dict[str, object]]]
    totals: dict[str, str]
    created_at: datetime


class FilingResponse(BaseModel):
    id: str
    scope: Scope
    registration: RegistrationResponse
    period_month: date
    status: GstFilingStatus
    completeness_confirmed: bool
    approved_at: datetime | None
    filed_arn: str | None
    filed_at: datetime | None
    documents: list[DocumentResponse] = Field(default_factory=list)
    exceptions: list[ExceptionResponse] = Field(default_factory=list)
    latest_draft: DraftResponse | None = None
    next_step: str


class FilingListResponse(BaseModel):
    items: list[FilingResponse]


class ApprovalCommand(BaseModel):
    completeness_confirmed: Literal[True]


class FiledCommand(BaseModel):
    arn: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=64)]
