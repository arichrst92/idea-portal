"""THR business logic — TSK-053.

Per US-FN-003 AC-02: prorata untuk karyawan < 1 tahun masa kerja.
Rumus: thr_amount = base_salary × min(months_worked / 12, 1).

knowledge.md sec.12: THR = configurable, transfer terpisah dari payroll.
NC tidak ada eksplisit — prorata rule self-evident dari spec.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.organization.models import Employee, EmployeeStatus
from app.payroll.models import PayrollConfig, ThrPayment
from app.payroll.thr_schemas import ThrGenerateRequest, ThrGenerateResponse

logger = logging.getLogger(__name__)


class ThrNotFoundError(Exception):
    pass


class ThrAlreadyPaidError(Exception):
    pass


def _months_worked(joined_date: date, reference_date: date) -> Decimal:
    """Hitung bulan kerja sampai reference_date.

    Rumus standar Kemnaker:
    - Karyawan ≥ 12 bulan kerja → 1 bulan basic salary (full)
    - Karyawan < 12 bulan → (months_worked / 12) × basic salary
    - Karyawan < 1 bulan kerja → tidak eligible THR (return 0)
    """
    if joined_date > reference_date:
        return Decimal("0")

    # Hitung selisih bulan, dibulatkan ke desimal 0.01
    years = reference_date.year - joined_date.year
    months = reference_date.month - joined_date.month
    days = reference_date.day - joined_date.day

    total_months = years * 12 + months
    if days < 0:
        total_months -= 1
        # Tambah hari (dalam fraksi bulan)
        from calendar import monthrange
        last_month_days = monthrange(reference_date.year, reference_date.month)[1]
        total_months += (last_month_days + days) / last_month_days
    elif days > 0:
        # Fraksi bulan dari hari sisa
        from calendar import monthrange
        ref_month_days = monthrange(reference_date.year, reference_date.month)[1]
        total_months += days / ref_month_days

    return Decimal(str(round(max(total_months, 0), 2)))


def _compute_thr_amount(base_salary: Decimal, months_worked: Decimal) -> Decimal:
    """thr = base × min(months/12, 1)."""
    factor = months_worked / Decimal("12")
    if factor > Decimal("1"):
        factor = Decimal("1")
    if factor < Decimal("0"):
        factor = Decimal("0")
    return (base_salary * factor).quantize(Decimal("0.01"))


async def generate_thr_bulk(
    session: AsyncSession,
    data: ThrGenerateRequest,
    generator_user_id: UUID,
) -> ThrGenerateResponse:
    """Bulk generate THR untuk semua active+probation employee yang eligible."""
    # Get all eligible employees
    emp_stmt = select(Employee).where(
        Employee.deleted_at.is_(None),
        Employee.status.in_([EmployeeStatus.ACTIVE, EmployeeStatus.PROBATION]),
        Employee.joined_date.isnot(None),
    )
    employees = list((await session.execute(emp_stmt)).scalars().all())

    # Existing THR untuk year ini (untuk skip / overwrite logic)
    existing_stmt = select(ThrPayment).where(ThrPayment.thr_year == data.thr_year)
    existing_by_emp = {
        t.employee_id: t
        for t in (await session.execute(existing_stmt)).scalars().all()
    }

    generated = 0
    skipped = 0
    errors: list[str] = []
    total_amount = Decimal("0")

    for emp in employees:
        # Get active payroll config
        config_stmt = (
            select(PayrollConfig)
            .where(PayrollConfig.employee_id == emp.id)
            .where(PayrollConfig.effective_date <= data.reference_date)
            .order_by(PayrollConfig.effective_date.desc())
            .limit(1)
        )
        config = (await session.execute(config_stmt)).scalar_one_or_none()
        if config is None:
            errors.append(f"{emp.full_name}: no payroll config")
            continue

        base = Decimal(str(config.basic_salary))
        months = _months_worked(emp.joined_date, data.reference_date)
        if months <= Decimal("0"):
            # Belum cukup masa kerja
            errors.append(f"{emp.full_name}: not eligible (< 1 bulan masa kerja)")
            continue

        thr_amount = _compute_thr_amount(base, months)

        existing = existing_by_emp.get(emp.id)
        if existing and not data.overwrite_existing:
            skipped += 1
            continue
        elif existing and data.overwrite_existing:
            if existing.status == "PAID":
                errors.append(
                    f"{emp.full_name}: THR sudah PAID, tidak bisa di-overwrite"
                )
                continue
            existing.base_salary = base
            existing.months_worked = months
            existing.thr_amount = thr_amount
            existing.generated_by_user_id = generator_user_id
            total_amount += thr_amount
            generated += 1
        else:
            row = ThrPayment(
                employee_id=emp.id,
                thr_year=data.thr_year,
                base_salary=base,
                months_worked=months,
                thr_amount=thr_amount,
                currency="IDR",
                status="GENERATED",
                generated_by_user_id=generator_user_id,
            )
            session.add(row)
            total_amount += thr_amount
            generated += 1

    await session.commit()

    # Notify each employee (best-effort, non-blocking)
    try:
        from app.notification.models import NotificationType
        from app.notification.templates import notify_from_template

        for emp in employees:
            t = existing_by_emp.get(emp.id) if not data.overwrite_existing else None
            if t and not data.overwrite_existing:
                continue
            if not emp.user_id:
                continue
            await notify_from_template(
                session,
                user_id=emp.user_id,
                type=NotificationType.SYSTEM,
                context={
                    "title": f"THR {data.thr_year} di-generate",
                    "body": "Detail THR Anda dapat dilihat di portal payroll.",
                    "link": "/my-payslips",
                },
            )
        await session.commit()
    except Exception:  # noqa: BLE001
        pass

    return ThrGenerateResponse(
        thr_year=data.thr_year,
        generated=generated,
        skipped=skipped,
        total_amount_idr=total_amount,
        employee_count=len(employees),
        errors=errors,
    )


async def list_thr(
    session: AsyncSession,
    thr_year: int | None = None,
    status: str | None = None,
) -> list[ThrPayment]:
    stmt = select(ThrPayment)
    if thr_year is not None:
        stmt = stmt.where(ThrPayment.thr_year == thr_year)
    if status is not None:
        stmt = stmt.where(ThrPayment.status == status)
    stmt = stmt.order_by(ThrPayment.thr_year.desc(), ThrPayment.created_at.desc())
    return list((await session.execute(stmt)).scalars().all())


async def get_thr(session: AsyncSession, thr_id: UUID) -> ThrPayment:
    t = await session.get(ThrPayment, thr_id)
    if t is None:
        raise ThrNotFoundError(f"THR {thr_id} not found")
    return t


async def list_my_thr(
    session: AsyncSession, user_id: UUID
) -> list[ThrPayment]:
    """Self-service THR list untuk current user."""
    emp_stmt = select(Employee.id).where(Employee.user_id == user_id)
    employee_id = (await session.execute(emp_stmt)).scalar_one_or_none()
    if employee_id is None:
        return []

    stmt = (
        select(ThrPayment)
        .where(ThrPayment.employee_id == employee_id)
        .where(ThrPayment.status.in_(("APPROVED", "PAID")))
        .order_by(ThrPayment.thr_year.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def mark_thr_paid(
    session: AsyncSession,
    thr_id: UUID,
    payment_date: date,
    transfer_ref: str | None,
) -> ThrPayment:
    t = await get_thr(session, thr_id)
    if t.status == "PAID":
        raise ThrAlreadyPaidError(f"THR {t.id} sudah PAID pada {t.payment_date}")
    if t.status == "CANCELLED":
        raise ThrAlreadyPaidError(f"THR {t.id} status CANCELLED, tidak bisa mark paid")
    t.status = "PAID"
    t.paid_at = datetime.now(UTC)
    t.payment_date = payment_date
    t.transfer_ref = transfer_ref
    await session.commit()
    await session.refresh(t)
    return t
