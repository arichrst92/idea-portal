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

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
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
    """Submit cuti dengan 2-layer approval.

    Status flow:
    PENDING_L1 → PENDING_L2 (L1 approve)
             → REJECTED (L1 reject)
             → CANCELLED (employee cancel)
    PENDING_L2 → APPROVED (L2 approve, auto-deduct saldo)
             → REJECTED (L2 reject)
    """

    __tablename__ = "leave_requests"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    leave_type_id: Mapped[UUID] = mapped_column(ForeignKey("leave_types.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days_count: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING_L1", nullable=False, index=True)

    # Approval audit
    layer1_approver_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    layer1_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    layer1_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    layer2_approver_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    layer2_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    layer2_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Rejection / Cancellation
    rejected_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LeaveBalance(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Saldo cuti per employee per leave type per tahun.

    Auto-create saat employee first request leave di tahun tersebut
    (atau via batch yearly reset).
    """

    __tablename__ = "leave_balances"

    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    leave_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("leave_types.id"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(nullable=False, index=True)
    allocated_days: Mapped[int] = mapped_column(nullable=False, default=0)
    used_days: Mapped[int] = mapped_column(nullable=False, default=0)
    carried_over_days: Mapped[int] = mapped_column(nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "leave_type_id",
            "year",
            name="uq_balance_employee_type_year",
        ),
        Index("ix_balance_employee_year", "employee_id", "year"),
    )


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
    """Periode payroll bulanan dengan approval workflow (TSK-050).

    Status transitions:
      DRAFT → REVIEWING (calc engine done — TSK-048)
      REVIEWING → PENDING_APPROVAL (Finance submit for review — TSK-050)
      PENDING_APPROVAL → APPROVED (GM/C-Level approve — TSK-050)
      PENDING_APPROVAL → REVIEWING (GM reject, back to Finance — TSK-050)
      APPROVED → PAID (slip PDF published, future TSK)
      any → LOCKED (immutable — existing)
    """

    __tablename__ = "payroll_periods"

    year: Mapped[int] = mapped_column(nullable=False)
    month: Mapped[int] = mapped_column(nullable=False)
    pay_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ─── TSK-050 Approval workflow audit ──────────────────────
    submitted_for_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submitted_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approval_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejected_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


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
    """Reimbursement — transfer TERPISAH dari payroll (knowledge.md sec.12).

    Status flow: PENDING_L1 → PENDING_L2 → APPROVED → TRANSFERRED
                          → REJECTED / CANCELLED
    """

    __tablename__ = "reimbursements"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    request_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="OTHER", index=True)
    # MEDICAL, TRANSPORT, MEAL, BUSINESS_TRIP, COMMUNICATION, ENTERTAINMENT, OTHER
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="IDR", nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    receipt_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True
    )  # opsional, untuk billable expense

    status: Mapped[str] = mapped_column(String(20), default="PENDING_L1", nullable=False, index=True)

    # Approval audit
    layer1_approver_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    layer1_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    layer1_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    layer2_approver_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    layer2_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    layer2_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejected_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Transfer
    transferred_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    transferred_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    transfer_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Vendor(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Vendor untuk procurement."""

    __tablename__ = "vendors"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_info: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProcurementRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Pengadaan barang dengan approval flow.

    Status flow: PENDING_L1 → PENDING_L2 → APPROVED → ORDERED → DELIVERED
                          → REJECTED / CANCELLED
    """

    __tablename__ = "procurement_requests"

    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    request_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    item_description: Mapped[str] = mapped_column(Text, nullable=False)
    item_category: Mapped[str] = mapped_column(String(50), default="OTHER", nullable=False)
    # IT_EQUIPMENT, OFFICE_SUPPLIES, FURNITURE, SOFTWARE_LICENSE, MARKETING, OTHER
    quantity: Mapped[int] = mapped_column(default=1, nullable=False)
    estimated_amount: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    actual_amount: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="IDR", nullable=False)
    vendor_id: Mapped[UUID | None] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    is_asset: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="PENDING_L1", nullable=False, index=True)

    # Approval audit
    layer1_approver_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    layer1_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    layer1_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    layer2_approver_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    layer2_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    layer2_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejected_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # PO + Delivery tracking
    po_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ordered_at: Mapped[date | None] = mapped_column(Date, nullable=True)


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


class MonthlyAttendance(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Monthly attendance per karyawan per periode — TSK-047 (EP-05).

    Operation input data ini sepanjang bulan (knowledge.md sec.12 timeline:
    "Sepanjang bulan → cuti, lembur input Operation; H-5 → rekap submit Finance").

    Linked to PayrollPeriod (bukan year/month langsung) untuk lock state mgmt.
    Unique constraint: 1 row per (employee, period).

    Edge cases enforced di service layer:
    - NC-OP-007-01: days_present + days_absent_paid + days_absent_unpaid ≤ calendar_working_days
    - NC-OP-007-05: overtime_hours ≥ 0
    - NC-OP-008-02: tidak bisa edit kalau period.status != DRAFT
    """

    __tablename__ = "monthly_attendances"

    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("employees.id"), nullable=False, index=True
    )
    period_id: Mapped[UUID] = mapped_column(
        ForeignKey("payroll_periods.id"), nullable=False, index=True
    )

    # Attendance counts (days per month)
    days_present: Mapped[int] = mapped_column(default=0, nullable=False)
    days_absent_paid: Mapped[int] = mapped_column(default=0, nullable=False)  # leave approved
    days_absent_unpaid: Mapped[int] = mapped_column(default=0, nullable=False)  # alpha
    overtime_hours: Mapped[float] = mapped_column(Numeric(6, 2), default=0, nullable=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audit
    input_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("employee_id", "period_id", name="uq_attendance_employee_period"),
        Index("ix_attendance_period_employee", "period_id", "employee_id"),
    )
