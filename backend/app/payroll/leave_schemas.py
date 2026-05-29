"""Pydantic schemas — leave request TSK-019."""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Reason = Annotated[str, StringConstraints(min_length=5, max_length=2000, strip_whitespace=True)]


class LeaveRequestStatus(str, enum.Enum):
    PENDING_L1 = "PENDING_L1"
    PENDING_L2 = "PENDING_L2"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


# ─── LeaveType ─────────────────────────────────────────────────────


class LeaveTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    default_days_per_year: int
    is_paid: bool


class LeaveTypeCreate(BaseModel):
    code: Annotated[str, StringConstraints(min_length=2, max_length=20, strip_whitespace=True)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    default_days_per_year: Annotated[int, Field(ge=0, le=365)] = 0
    is_paid: bool = True


# ─── LeaveBalance ──────────────────────────────────────────────────


class LeaveBalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    leave_type_id: UUID
    year: int
    allocated_days: int
    used_days: int
    carried_over_days: int

    # Derived
    remaining_days: int = 0
    leave_type_code: str | None = None
    leave_type_name: str | None = None


class EmployeeBalanceSummary(BaseModel):
    """Semua balance untuk 1 employee 1 tahun."""

    employee_id: UUID
    employee_nik: str | None = None
    employee_name: str | None = None
    year: int
    balances: list[LeaveBalanceOut]


# ─── LeaveRequest ──────────────────────────────────────────────────


class LeaveRequestCreate(BaseModel):
    employee_id: UUID
    leave_type_id: UUID
    start_date: date
    end_date: date
    reason: Reason | None = None


class LeaveRequestApprove(BaseModel):
    notes: str | None = None


class LeaveRequestReject(BaseModel):
    rejection_reason: Reason


class LeaveRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    leave_type_id: UUID
    start_date: date
    end_date: date
    days_count: int
    reason: str | None
    status: str

    layer1_approver_id: UUID | None
    layer1_approved_at: datetime | None
    layer1_notes: str | None
    layer2_approver_id: UUID | None
    layer2_approved_at: datetime | None
    layer2_notes: str | None
    rejected_by_user_id: UUID | None
    rejected_at: datetime | None
    rejection_reason: str | None
    cancelled_at: datetime | None

    created_at: datetime
    updated_at: datetime

    # Derived
    employee_nik: str | None = None
    employee_name: str | None = None
    leave_type_code: str | None = None
    leave_type_name: str | None = None
    layer1_approver_nik: str | None = None
    layer2_approver_nik: str | None = None


class LeaveRequestListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    employee_nik: str | None = None
    employee_name: str | None = None
    leave_type_code: str | None = None
    leave_type_name: str | None = None
    start_date: date
    end_date: date
    days_count: int
    status: str
    created_at: datetime


class LeaveRequestListResponse(BaseModel):
    items: list[LeaveRequestListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
