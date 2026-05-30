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
    APPROVED = "APPROVED"
    PAID = "PAID"
    LOCKED = "LOCKED"


class PayrollPeriodCreate(BaseModel):
    year: Annotated[int, Field(ge=2020, le=2099)]
    month: Annotated[int, Field(ge=1, le=12)]
    pay_date: date


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


class SetPph21Request(BaseModel):
    """Set PPh21 manual per slip (US-TK-049)."""

    pph21_amount: Annotated[Decimal, Field(ge=0)]
