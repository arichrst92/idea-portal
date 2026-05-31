"""Attendance business logic — TSK-047 (EP-05).

Operation input monthly attendance per karyawan per periode.

Edge cases enforced:
- NC-OP-007-01: days_present + days_absent_paid + days_absent_unpaid ≤ calendar_working_days
- NC-OP-007-05: overtime_hours ≥ 0 (juga via Pydantic Field constraint)
- NC-OP-008-02: tidak bisa edit/insert kalau period.status != DRAFT
"""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.organization.models import Employee, EmployeeStatus
from app.payroll.attendance_schemas import (
    AttendanceBulkUpsert,
    AttendanceUpdate,
)
from app.payroll.models import Holiday, MonthlyAttendance, PayrollPeriod


# ─── Exceptions ────────────────────────────────────────────────────


class AttendanceError(Exception):
    """Base for attendance errors."""


class PeriodLockedError(AttendanceError):
    """Period sudah finalized — tidak bisa edit attendance."""


class PeriodNotFoundError(AttendanceError):
    pass


class AttendanceNotFoundError(AttendanceError):
    pass


class ExceedsWorkingDaysError(AttendanceError):
    """days_present + absent_paid + absent_unpaid > calendar_working_days."""


# ─── Helpers ───────────────────────────────────────────────────────


async def calculate_period_working_days(
    session: AsyncSession, year: int, month: int
) -> int:
    """Count business days in a given (year, month) — exclude weekend + holidays.

    Reused from leave_service.calculate_business_days pattern but for whole month.
    """
    # First and last day of month
    last_day = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)

    # Fetch holidays in period
    holidays_stmt = select(Holiday.holiday_date).where(
        and_(Holiday.holiday_date >= start, Holiday.holiday_date <= end)
    )
    holidays = {h for h in (await session.execute(holidays_stmt)).scalars().all()}

    count = 0
    cur = start
    while cur <= end:
        # weekday(): Mon=0, Sun=6 → exclude Sat(5) & Sun(6)
        if cur.weekday() < 5 and cur not in holidays:
            count += 1
        cur = date.fromordinal(cur.toordinal() + 1)
    return count


async def get_period_or_raise(
    session: AsyncSession, period_id: UUID
) -> PayrollPeriod:
    p = await session.get(PayrollPeriod, period_id)
    if p is None:
        raise PeriodNotFoundError(f"PayrollPeriod {period_id} not found")
    return p


def _validate_row_totals(
    row_days: tuple[int, int, int], working_days: int
) -> None:
    """NC-OP-007-01: total attendance days ≤ working_days."""
    total = sum(row_days)
    if total > working_days:
        raise ExceedsWorkingDaysError(
            f"Total hari ({total}) melebihi hari kerja periode ({working_days}). "
            "Cek days_present + days_absent_paid + days_absent_unpaid."
        )


# ─── Bulk upsert ───────────────────────────────────────────────────


async def bulk_upsert(
    session: AsyncSession,
    data: AttendanceBulkUpsert,
    input_by_user_id: UUID,
) -> list[MonthlyAttendance]:
    """Bulk upsert attendance untuk 1 periode.

    - Period harus status=DRAFT (NC-OP-008-02)
    - Setiap row validate total ≤ working_days
    - Existing rows di-update, baru di-insert
    """
    period = await get_period_or_raise(session, data.period_id)
    if period.status != "DRAFT":
        raise PeriodLockedError(
            f"Period {period.year}-{period.month:02d} status {period.status}, "
            f"tidak bisa edit attendance (NC-OP-008-02)"
        )

    working_days = await calculate_period_working_days(
        session, period.year, period.month
    )

    # Pre-validate semua row dulu (atomic — kalau ada yg invalid, rollback semua)
    for row in data.rows:
        _validate_row_totals(
            (row.days_present, row.days_absent_paid, row.days_absent_unpaid),
            working_days,
        )

    # Fetch existing untuk decide upsert
    existing_stmt = select(MonthlyAttendance).where(
        MonthlyAttendance.period_id == data.period_id,
        MonthlyAttendance.employee_id.in_([r.employee_id for r in data.rows]),
    )
    existing_rows = (await session.execute(existing_stmt)).scalars().all()
    existing_by_emp = {r.employee_id: r for r in existing_rows}

    upserted: list[MonthlyAttendance] = []
    for row in data.rows:
        ex = existing_by_emp.get(row.employee_id)
        if ex is None:
            new_row = MonthlyAttendance(
                employee_id=row.employee_id,
                period_id=data.period_id,
                days_present=row.days_present,
                days_absent_paid=row.days_absent_paid,
                days_absent_unpaid=row.days_absent_unpaid,
                overtime_hours=row.overtime_hours,
                notes=row.notes,
                input_by_user_id=input_by_user_id,
            )
            session.add(new_row)
            upserted.append(new_row)
        else:
            ex.days_present = row.days_present
            ex.days_absent_paid = row.days_absent_paid
            ex.days_absent_unpaid = row.days_absent_unpaid
            ex.overtime_hours = row.overtime_hours
            ex.notes = row.notes
            ex.input_by_user_id = input_by_user_id
            upserted.append(ex)

    await session.commit()
    for r in upserted:
        await session.refresh(r)
    return upserted


# ─── Update single ─────────────────────────────────────────────────


async def update_attendance(
    session: AsyncSession,
    att_id: UUID,
    data: AttendanceUpdate,
    input_by_user_id: UUID,
) -> MonthlyAttendance:
    att = await session.get(MonthlyAttendance, att_id)
    if att is None:
        raise AttendanceNotFoundError(f"Attendance {att_id} not found")

    period = await session.get(PayrollPeriod, att.period_id)
    if period and period.status != "DRAFT":
        raise PeriodLockedError(
            f"Period {period.year}-{period.month:02d} status {period.status}, "
            "tidak bisa edit attendance"
        )

    # Compute new values
    new_present = data.days_present if data.days_present is not None else att.days_present
    new_paid = data.days_absent_paid if data.days_absent_paid is not None else att.days_absent_paid
    new_unpaid = data.days_absent_unpaid if data.days_absent_unpaid is not None else att.days_absent_unpaid

    working_days = await calculate_period_working_days(
        session, period.year, period.month
    )
    _validate_row_totals((new_present, new_paid, new_unpaid), working_days)

    att.days_present = new_present
    att.days_absent_paid = new_paid
    att.days_absent_unpaid = new_unpaid
    if data.overtime_hours is not None:
        att.overtime_hours = data.overtime_hours
    if data.notes is not None:
        att.notes = data.notes
    att.input_by_user_id = input_by_user_id

    await session.commit()
    await session.refresh(att)
    return att


# ─── Query ─────────────────────────────────────────────────────────


async def list_for_period(
    session: AsyncSession, period_id: UUID
) -> tuple[PayrollPeriod, list[tuple[MonthlyAttendance, Employee]], int, int]:
    """List attendance + Employee untuk 1 periode.

    Returns: (period, [(attendance, employee), ...], working_days, total_active_emp)
    """
    period = await get_period_or_raise(session, period_id)
    working_days = await calculate_period_working_days(
        session, period.year, period.month
    )

    # All active employees
    active_count_stmt = select(func.count(Employee.id)).where(
        Employee.status == EmployeeStatus.ACTIVE,
        Employee.deleted_at.is_(None),
    )
    total_active = int((await session.execute(active_count_stmt)).scalar_one())

    # Attendance rows joined with Employee
    join_stmt = (
        select(MonthlyAttendance, Employee)
        .join(Employee, MonthlyAttendance.employee_id == Employee.id)
        .where(MonthlyAttendance.period_id == period_id)
        .order_by(Employee.full_name)
    )
    rows = list((await session.execute(join_stmt)).all())
    rows_paired = [(r[0], r[1]) for r in rows]

    return period, rows_paired, working_days, total_active


async def completeness(
    session: AsyncSession, period_id: UUID
) -> tuple[PayrollPeriod, int, int, int, list[UUID]]:
    """Completeness summary: (period, working_days, total_active, submitted_count, missing_emp_ids).

    Used by frontend to display progress + by TSK-048 to block payroll calc.
    """
    period = await get_period_or_raise(session, period_id)
    working_days = await calculate_period_working_days(
        session, period.year, period.month
    )

    # Active employees set
    emp_stmt = select(Employee.id).where(
        Employee.status == EmployeeStatus.ACTIVE,
        Employee.deleted_at.is_(None),
    )
    all_active = {e for e in (await session.execute(emp_stmt)).scalars().all()}

    # Submitted set
    sub_stmt = select(MonthlyAttendance.employee_id).where(
        MonthlyAttendance.period_id == period_id
    )
    submitted = {e for e in (await session.execute(sub_stmt)).scalars().all()}

    missing = all_active - submitted
    return period, working_days, len(all_active), len(submitted), sorted(missing, key=str)
