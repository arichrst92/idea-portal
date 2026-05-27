"""HR & Payroll domain — 11 tabel per ERD knowledge.md sec.20.

Tabel:
- leave_types               — jenis cuti (Tahunan/Sakit/Melahirkan/Duka/Menikah)
- leave_requests            — submit + 2-layer approval
- payroll_configs           — komponen gaji per karyawan
- payroll_periods           — periode bulanan
- payroll_components        — komponen per slip
- payroll_slips             — slip gaji
- reimbursements            — transfer terpisah (BUKAN via payroll)
- procurement_requests      — pengadaan barang
- vendors                   — vendor master
- work_calendars            — config working days per dept
- holidays                  — national + joint leave dates

Schema detail full per EP-05 (M1.4) + EP-11/12/13 (M2.3).
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class LeaveType(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Jenis cuti per knowledge.md sec.10."""

    __tablename__ = "leave_types"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    default_days_per_year: Mapped[int] = mapped_column(default=0, nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LeaveRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Submit cuti dengan 2-layer approval."""

    __tablename__ = "leave_requests"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    leave_type_id: Mapped[UUID] = mapped_column(ForeignKey("leave_types.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days_count: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING_L1", nullable=False)
    layer1_approver_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    layer1_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    layer2_approver_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    layer2_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PayrollConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Komponen gaji per karyawan (gaji pokok, tunjangan tetap, BPJS basis)."""

    __tablename__ = "payroll_configs"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    basic_salary: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    fixed_allowance: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    bpjs_kesehatan_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=1.0, nullable=False)
    bpjs_ketenagakerjaan_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=2.0, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)


class PayrollPeriod(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Periode payroll bulanan."""

    __tablename__ = "payroll_periods"

    year: Mapped[int] = mapped_column(nullable=False)
    month: Mapped[int] = mapped_column(nullable=False)
    pay_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PayrollComponent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Komponen per slip (penghasilan + potongan)."""

    __tablename__ = "payroll_components"

    slip_id: Mapped[UUID] = mapped_column(ForeignKey("payroll_slips.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    component_type: Mapped[str] = mapped_column(String(20), nullable=False)  # INCOME/DEDUCTION
    is_variable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # e.g., "sales_commission:LEAD-001" untuk auto-flow komisi (US-EX-005)


class PayrollSlip(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Slip gaji bulanan."""

    __tablename__ = "payroll_slips"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    period_id: Mapped[UUID] = mapped_column(ForeignKey("payroll_periods.id"), nullable=False, index=True)
    slip_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    gross_income: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    total_deductions: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    take_home_pay: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Reimbursement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Reimbursement — transfer TERPISAH dari payroll (knowledge.md sec.12)."""

    __tablename__ = "reimbursements"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    request_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="IDR", nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    receipt_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING_L1", nullable=False)
    transferred_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class Vendor(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Vendor untuk procurement."""

    __tablename__ = "vendors"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_info: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProcurementRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Pengadaan barang dengan approval flow."""

    __tablename__ = "procurement_requests"

    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    item_description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(default=1, nullable=False)
    estimated_amount: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    vendor_id: Mapped[UUID | None] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    is_asset: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING_L1", nullable=False)


class WorkCalendar(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Config working days + dept override (TSK-026)."""

    __tablename__ = "work_calendars"

    year: Mapped[int] = mapped_column(nullable=False, index=True)
    department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    workdays_per_week: Mapped[int] = mapped_column(default=5, nullable=False)
    workhours_per_day: Mapped[int] = mapped_column(default=8, nullable=False)


class Holiday(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """National + joint leave dates."""

    __tablename__ = "holidays"

    holiday_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_joint_leave: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
