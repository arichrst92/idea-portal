"""Pydantic schemas — separation TSK-017."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.separation.models import SeparationStatus, SeparationType

Reason = Annotated[str, StringConstraints(min_length=10, max_length=2000, strip_whitespace=True)]


# ─── Create + Submit ───────────────────────────────────────────────


class SeparationCreate(BaseModel):
    employee_id: UUID
    separation_type: SeparationType
    reason: Reason
    effective_date: date
    notice_period_days: Annotated[int, Field(ge=0, le=365)] = 30
    severance_amount: Decimal | None = None
    currency: Annotated[str, StringConstraints(min_length=3, max_length=3)] = "IDR"
    assets_to_return: list[dict] | None = None
    related_warning_letter_id: UUID | None = None


class SeparationApproveRequest(BaseModel):
    """L1 atau L2 approver memberikan note."""

    notes: str | None = None


class SeparationRejectRequest(BaseModel):
    rejection_reason: Reason


class SeparationCancelRequest(BaseModel):
    cancellation_reason: Reason


class ExitInterviewRequest(BaseModel):
    notes: Annotated[str, StringConstraints(min_length=20, max_length=5000)]


# ─── Response ──────────────────────────────────────────────────────


class SeparationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    separation_type: SeparationType
    status: SeparationStatus
    effective_date: date
    created_at: datetime

    # Derived
    employee_nik: str | None = None
    employee_name: str | None = None
    employee_department: str | None = None
    initiated_by_nik: str | None = None


class SeparationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    separation_type: SeparationType
    status: SeparationStatus

    reason: str
    effective_date: date
    notice_period_days: int
    severance_amount: Decimal | None
    currency: str
    assets_to_return: list[dict] | None
    related_warning_letter_id: UUID | None

    exit_interview_notes: str | None
    exit_interview_completed_at: datetime | None

    initiated_by_user_id: UUID
    approval_l1_user_id: UUID | None
    approval_l1_at: datetime | None
    approval_l1_notes: str | None
    approval_l2_user_id: UUID | None
    approval_l2_at: datetime | None
    approval_l2_notes: str | None
    rejected_by_user_id: UUID | None
    rejected_at: datetime | None
    rejection_reason: str | None
    executed_by_user_id: UUID | None
    executed_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None

    created_at: datetime
    updated_at: datetime

    # Derived
    employee_nik: str | None = None
    employee_name: str | None = None
    employee_department: str | None = None
    initiated_by_nik: str | None = None
    approval_l1_nik: str | None = None
    approval_l2_nik: str | None = None


class SeparationListResponse(BaseModel):
    items: list[SeparationListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
