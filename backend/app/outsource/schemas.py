"""Pydantic schemas — outsource domain (TSK-100)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.outsource.models import BillingType


# ─── Placement ─────────────────────────────────────────────────────


class PlacementCreate(BaseModel):
    employee_id: UUID
    client_id: UUID
    role_at_client: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    start_date: date
    end_date: date | None = None
    billing_type: BillingType
    billing_rate: Annotated[Decimal, Field(ge=0)]


class PlacementUpdate(BaseModel):
    role_at_client: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    billing_type: BillingType | None = None
    billing_rate: Decimal | None = None
    is_active: bool | None = None


class PlacementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    client_id: UUID
    role_at_client: str
    start_date: date
    end_date: date | None
    billing_type: BillingType
    billing_rate: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Derived
    employee_nik: str | None = None
    employee_name: str | None = None
    client_code: str | None = None
    client_name: str | None = None
    monthly_billing_estimate: Decimal | None = None
    duration_days: int | None = None
    days_until_end: int | None = None


class PlacementListResponse(BaseModel):
    items: list[PlacementOut]
    total: int
    active_count: int
    expiring_30d: int


# ─── Client ────────────────────────────────────────────────────────


class ClientCreate(BaseModel):
    code: Annotated[str, StringConstraints(min_length=2, max_length=50)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    pic_name: str | None = None
    pic_email: str | None = None
    pic_phone: str | None = None
    address: str | None = None


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    pic_name: str | None
    pic_email: str | None
    pic_phone: str | None
    address: str | None
    is_active: bool
    created_at: datetime

    placement_count: int = 0
    active_placement_count: int = 0


# ─── Timesheet (TSK-103+104) ───────────────────────────────────────


class TimesheetCreate(BaseModel):
    placement_id: UUID
    year: Annotated[int, Field(ge=2020, le=2099)]
    month: Annotated[int, Field(ge=1, le=12)]


class TimesheetItemUpsert(BaseModel):
    work_date: date
    is_present: bool = True
    notes: str | None = None


class TimesheetItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    timesheet_id: UUID
    work_date: date
    is_present: bool
    notes: str | None


class TimesheetApprove(BaseModel):
    notes: str | None = None


class TimesheetReject(BaseModel):
    rejection_reason: Annotated[str, StringConstraints(min_length=5, max_length=1000)]


class TimesheetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    placement_id: UUID
    year: int
    month: int
    workdays_count: int
    status: str
    submitted_at: date | None
    approved_at: date | None
    created_at: datetime
    updated_at: datetime

    # Derived
    period_label: str | None = None
    placement_employee_nik: str | None = None
    placement_employee_name: str | None = None
    placement_client_code: str | None = None
    placement_client_name: str | None = None
    placement_role: str | None = None
    items: list[TimesheetItemOut] = Field(default_factory=list)
    present_count: int = 0
    absent_count: int = 0


# ─── Berita Acara (TSK-105) ───────────────────────────────────────


class BeritaAcaraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    timesheet_id: UUID
    ba_no: str
    pdf_url: str | None
    signed_by_ide: bool
    signed_by_client: bool
    client_signed_at: date | None
    created_at: datetime

    # Derived
    timesheet_period_label: str | None = None
    employee_name: str | None = None
    client_name: str | None = None
    download_url: str | None = None  # presigned


# ─── Client Complaint (TSK-148) ───────────────────────────────────


class ComplaintSeverity:
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ClientComplaintCreate(BaseModel):
    placement_id: UUID
    complaint_date: date
    severity: Annotated[str, StringConstraints(pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")] = "MEDIUM"
    description: Annotated[str, StringConstraints(min_length=10, max_length=2000)]


class ClientComplaintUpdate(BaseModel):
    resolved_at: date | None = None
    description: str | None = None


class ClientComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    placement_id: UUID
    complaint_date: date
    severity: str
    description: str
    logged_by_user_id: UUID | None
    resolved_at: date | None
    created_at: datetime

    # Derived
    placement_employee_nik: str | None = None
    placement_employee_name: str | None = None
    placement_client_code: str | None = None
    placement_client_name: str | None = None
    placement_role: str | None = None
    logged_by_nik: str | None = None
    spo_count: int = 0  # SP-O yang sudah di-issue dari complaint ini


# ─── SP-O Outsource (TSK-148) ─────────────────────────────────────


class SpoLevel:
    SPO1 = "SP-O1"
    SPO2 = "SP-O2"
    SPO3 = "SP-O3"


class SpoCreate(BaseModel):
    placement_id: UUID
    triggered_by_complaint_id: UUID | None = None
    issued_date: date
    reason: Annotated[str, StringConstraints(min_length=10, max_length=2000)]
    # Level auto-assigned dari history (SP-O1 → SP-O2 → SP-O3)


# ─── Placement Amendment (TSK-107) ────────────────────────────────


class PlacementRenewRequest(BaseModel):
    effective_date: date
    new_end_date: date | None = None
    new_billing_rate: Annotated[Decimal, Field(ge=0)] | None = None
    document_url: str | None = None
    notes: str | None = None


class PlacementAmendmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    placement_id: UUID
    amendment_no: str
    effective_date: date
    old_end_date: date | None
    old_billing_rate: Decimal | None
    new_end_date: date | None
    new_billing_rate: Decimal | None
    document_url: str | None
    notes: str | None
    created_by_user_id: UUID | None
    created_at: datetime

    created_by_nik: str | None = None
    download_url: str | None = None


class SpoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    placement_id: UUID
    level: str
    issued_date: date
    triggered_by_complaint_id: UUID | None
    reason: str
    evaluation_end_date: date | None
    triggers_replacement: bool
    created_at: datetime

    # Derived
    placement_employee_nik: str | None = None
    placement_employee_name: str | None = None
    placement_client_code: str | None = None
    placement_client_name: str | None = None
    placement_role: str | None = None
    complaint_severity: str | None = None
    complaint_description: str | None = None
