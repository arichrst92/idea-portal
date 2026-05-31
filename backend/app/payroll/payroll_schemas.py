"""Pydantic schemas — payroll domain (TSK-046).

Hierarki: PayrollConfig (per employee) → PayrollPeriod (per bulan) →
          PayrollSlip (per employee per period) → PayrollComponent (income/deduction lines)
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


# ─── PayrollConfig ─────────────────────────────────────────────────


class PayrollConfigBase(BaseModel):
    employee_id: UUID
    basic_salary: Annotated[Decimal, Field(ge=0)]
    fixed_allowance: Annotated[Decimal, Field(ge=0)] = Decimal("0")
    bpjs_kesehatan_pct: Annotated[Decimal, Field(ge=0, le=100)] = Decimal("1.0")
    bpjs_ketenagakerjaan_pct: Annotated[Decimal, Field(ge=0, le=100)] = Decimal("2.0")
    effective_date: date


class PayrollConfigCreate(PayrollConfigBase):
    pass


class PayrollConfigUpdate(BaseModel):
    basic_salary: Decimal | None = None
    fixed_allowance: Decimal | None = None
    bpjs_kesehatan_pct: Decimal | None = None
    bpjs_ketenagakerjaan_pct: Decimal | None = None
    effective_date: date | None = None


class PayrollConfigOut(PayrollConfigBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
    employee_nik: str | None = None
    employee_name: str | None = None


# ─── PayrollPeriod ─────────────────────────────────────────────────


class PeriodStatus:
    DRAFT = "DRAFT"
    REVIEWING = "REVIEWING"
    PENDING_APPROVAL = "PENDING_APPROVAL"  # TSK-050 — Finance submitted, awaiting GM/C-Level
    APPROVED = "APPROVED"
    PAID = "PAID"
    LOCKED = "LOCKED"


class PayrollSubmitForApproval(BaseModel):
    """Finance submits payroll period for GM/C-Level approval (TSK-050)."""

    notes: str | None = None


class PayrollApproveRequest(BaseModel):
    """GM/C-Level approve payroll (TSK-050, US-FN-002 AC-06)."""

    notes: str | None = None


class PayrollRejectRequest(BaseModel):
    """GM/C-Level reject payroll — back to REVIEWING for Finance fix."""

    rejection_reason: Annotated[str, Field(min_length=3, max_length=500)]


class PayrollPeriodCreate(BaseModel):
    year: Annotated[int, Field(ge=2020, le=2099)]
    month: Annotated[int, Field(ge=1, le=12)]
    pay_date: date
    # TSK-055 — optional config (default null → use sensible defaults)
    cutoff_date: date | None = None  # attendance/komponen freeze (default: pay_date - 5)
    publish_date: date | None = None  # slip publish ke karyawan (default: pay_date)


class PayrollPeriodUpdate(BaseModel):
    """TSK-055 — update period config (only DRAFT)."""

    pay_date: date | None = None
    cutoff_date: date | None = None
    publish_date: date | None = None


class PayrollPeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    year: int
    month: int
    pay_date: date
    status: str
    locked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    # TSK-055 config
    cutoff_date: date | None = None
    publish_date: date | None = None

    # TSK-050 approval audit
    submitted_for_review_at: datetime | None = None
    submitted_by_user_id: UUID | None = None
    approved_at: datetime | None = None
    approved_by_user_id: UUID | None = None
    approval_notes: str | None = None
    rejected_at: datetime | None = None
    rejected_by_user_id: UUID | None = None
    rejection_reason: str | None = None

    # Derived
    slip_count: int = 0
    total_gross: Decimal | None = None
    total_take_home: Decimal | None = None


# ─── PayrollSlip & PayrollComponent ────────────────────────────────


class ComponentType:
    INCOME = "INCOME"
    DEDUCTION = "DEDUCTION"


class PayrollComponentCreate(BaseModel):
    code: Annotated[str, StringConstraints(min_length=1, max_length=50)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    component_type: Annotated[str, StringConstraints(pattern="^(INCOME|DEDUCTION)$")]
    is_variable: bool = True
    amount: Annotated[Decimal, Field(ge=0)]
    source_reference: str | None = None


class PayrollComponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slip_id: UUID
    code: str
    name: str
    component_type: str
    is_variable: bool
    amount: Decimal
    source_reference: str | None
    created_at: datetime


class PayrollSlipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    period_id: UUID
    slip_no: str
    gross_income: Decimal
    total_deductions: Decimal
    take_home_pay: Decimal
    pdf_url: str | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    # Derived
    employee_nik: str | None = None
    employee_name: str | None = None
    period_label: str | None = None  # e.g., "Mei 2026"
    components: list[PayrollComponentOut] = Field(default_factory=list)


class GenerateSlipsResponse(BaseModel):
    period_id: UUID
    generated: int
    skipped: int  # employee yg sudah punya slip
    errors: list[str] = Field(default_factory=list)


class CalculatePayrollResponse(BaseModel):
    """TSK-048 — Payroll Calculation Engine response.

    Run calc engine sekali untuk 1 period — attendance × config → slips.
    Validation steps di-report dalam response (anomaly, missing attendance).
    """

    period_id: UUID
    generated: int
    skipped: int
    total_gross_idr: Decimal
    total_deductions_idr: Decimal
    total_take_home_idr: Decimal
    employee_count: int
    anomaly_warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CalculatePayrollPreview(BaseModel):
    """Pre-flight check sebelum calc — show estimate + warnings without committing."""

    period_id: UUID
    calendar_working_days: int
    attendance_missing_count: int
    attendance_missing_employee_ids: list[UUID]
    estimated_employee_count: int
    can_proceed: bool
    blockers: list[str] = Field(default_factory=list)


class SetPph21Request(BaseModel):
    """Set PPh21 manual per slip (US-FN-002 AC-03)."""

    pph21_amount: Annotated[Decimal, Field(ge=0)]


class Pph21BulkRow(BaseModel):
    slip_id: UUID
    pph21_amount: Annotated[Decimal, Field(ge=0)]


class BulkSetPph21Request(BaseModel):
    """Bulk PPh21 input untuk semua slip dalam 1 period."""

    period_id: UUID
    rows: list[Pph21BulkRow]


class Pph21SuggestResponse(BaseModel):
    slip_id: UUID
    monthly_gross: Decimal
    annual_gross: Decimal
    ptkp: Decimal
    suggested_pph21: Decimal
    note: str = "Auto-calc berdasarkan bracket progresif × 12. Final keputusan Finance."
