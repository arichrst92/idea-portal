"""Payroll service — TSK-046.

Workflow:
1. Configure PayrollConfig per employee (basic_salary, fixed_allowance, BPJS pct).
2. Create PayrollPeriod per bulan (year + month + pay_date).
3. Generate slips for all active employees with a valid config (auto-create
   PayrollSlip + PayrollComponent untuk INCOME basic + allowance + DEDUCTION BPJS).
4. Add variable components (komisi sales, bonus, tunjangan variabel) via
   create_component endpoint — recomputes gross/deductions/take_home.
5. Set PPh21 manual per slip (US-TK-049) via set_pph21.
6. Lock period — slip tidak bisa diubah lagi.

PPh21 strategy: tidak auto-calc bracket (US-TK-049 = manual input).
Tax bracket helper disediakan kalau mau future auto-calc.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.organization.models import Employee, EmployeeStatus
from app.payroll.models import (
    PayrollComponent,
    PayrollConfig,
    PayrollPeriod,
    PayrollSlip,
)
from app.payroll.payroll_schemas import (
    PayrollComponentCreate,
    PayrollConfigCreate,
    PayrollConfigUpdate,
    PayrollPeriodCreate,
)


# ─── Exceptions ────────────────────────────────────────────────────


class ConfigNotFoundError(Exception):
    pass


class PeriodNotFoundError(Exception):
    pass


class SlipNotFoundError(Exception):
    pass


class PeriodLockedError(Exception):
    pass


class DuplicatePeriodError(Exception):
    pass


class DuplicateSlipError(Exception):
    pass


# ─── PayrollConfig ─────────────────────────────────────────────────


async def list_configs(
    session: AsyncSession,
    employee_id: UUID | None = None,
) -> list[PayrollConfig]:
    stmt = select(PayrollConfig)
    if employee_id is not None:
        stmt = stmt.where(PayrollConfig.employee_id == employee_id)
    stmt = stmt.order_by(PayrollConfig.effective_date.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_active_config(
    session: AsyncSession, employee_id: UUID, as_of: datetime | None = None
) -> PayrollConfig | None:
    """Active config = latest dengan effective_date <= as_of (default today)."""
    from datetime import date

    cutoff = (as_of or datetime.now(UTC)).date() if as_of else date.today()
    stmt = (
        select(PayrollConfig)
        .where(
            PayrollConfig.employee_id == employee_id,
            PayrollConfig.effective_date <= cutoff,
        )
        .order_by(PayrollConfig.effective_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_config(
    session: AsyncSession, data: PayrollConfigCreate
) -> PayrollConfig:
    """Insert new config (effective_dating — historical config dipertahankan)."""
    config = PayrollConfig(
        employee_id=data.employee_id,
        basic_salary=data.basic_salary,
        fixed_allowance=data.fixed_allowance,
        bpjs_kesehatan_pct=data.bpjs_kesehatan_pct,
        bpjs_ketenagakerjaan_pct=data.bpjs_ketenagakerjaan_pct,
        effective_date=data.effective_date,
    )
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return config


async def update_config(
    session: AsyncSession, config_id: UUID, data: PayrollConfigUpdate
) -> PayrollConfig:
    stmt = select(PayrollConfig).where(PayrollConfig.id == config_id)
    result = await session.execute(stmt)
    config = result.scalar_one_or_none()
    if config is None:
        raise ConfigNotFoundError(f"Config {config_id} not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(config, field, value)
    await session.commit()
    await session.refresh(config)
    return config


# ─── PayrollPeriod ─────────────────────────────────────────────────


async def list_periods(session: AsyncSession) -> list[PayrollPeriod]:
    stmt = select(PayrollPeriod).order_by(
        PayrollPeriod.year.desc(), PayrollPeriod.month.desc()
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_period(session: AsyncSession, period_id: UUID) -> PayrollPeriod:
    stmt = select(PayrollPeriod).where(PayrollPeriod.id == period_id)
    result = await session.execute(stmt)
    p = result.scalar_one_or_none()
    if p is None:
        raise PeriodNotFoundError(f"Period {period_id} not found")
    return p


async def create_period(
    session: AsyncSession, data: PayrollPeriodCreate
) -> PayrollPeriod:
    # Check duplicate
    dup_stmt = select(PayrollPeriod).where(
        PayrollPeriod.year == data.year, PayrollPeriod.month == data.month
    )
    if (await session.execute(dup_stmt)).scalar_one_or_none():
        raise DuplicatePeriodError(f"Period {data.year}-{data.month:02d} sudah ada")

    period = PayrollPeriod(
        year=data.year,
        month=data.month,
        pay_date=data.pay_date,
        status="DRAFT",
    )
    session.add(period)
    await session.commit()
    await session.refresh(period)
    return period


async def lock_period(session: AsyncSession, period_id: UUID) -> PayrollPeriod:
    period = await get_period(session, period_id)
    period.status = "LOCKED"
    period.locked_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(period)
    return period


# ─── Slip Generation ───────────────────────────────────────────────


async def generate_slips_for_period(
    session: AsyncSession, period_id: UUID
):
    """Generate PayrollSlip + standard components untuk semua employee ACTIVE
    yang punya config. Plus auto-inject pending SalesCommissions sebagai
    variable INCOME line (TSK-194).

    Returns: GenerateSlipsResponse
    """
    from app.payroll.payroll_schemas import GenerateSlipsResponse
    period = await get_period(session, period_id)
    if period.status == "LOCKED":
        raise PeriodLockedError(f"Period {period.year}-{period.month:02d} locked")

    # Get all active employees + their nik via User join
    from app.identity.models import User as _User
    emp_stmt = (
        select(Employee, _User.nik.label("nik"))
        .join(_User, Employee.user_id == _User.id)
        .where(
            Employee.deleted_at.is_(None),
            Employee.status.in_([EmployeeStatus.ACTIVE, EmployeeStatus.PROBATION]),
        )
    )
    employees_with_nik = list((await session.execute(emp_stmt)).all())

    generated = 0
    skipped = 0
    errors: list[str] = []

    for emp, emp_nik in employees_with_nik:
        # Skip kalau sudah punya slip untuk period ini
        existing_stmt = select(PayrollSlip).where(
            PayrollSlip.employee_id == emp.id,
            PayrollSlip.period_id == period_id,
        )
        if (await session.execute(existing_stmt)).scalar_one_or_none():
            skipped += 1
            continue

        config = await get_active_config(session, emp.id)
        if config is None:
            errors.append(f"{emp_nik}: no payroll config")
            continue

        # Build slip + standard components
        slip_no = f"SLIP-{period.year}{period.month:02d}-{emp_nik}"

        basic = Decimal(str(config.basic_salary))
        allowance = Decimal(str(config.fixed_allowance))
        bpjs_kes = (basic * Decimal(str(config.bpjs_kesehatan_pct)) / Decimal("100")).quantize(Decimal("0.01"))
        bpjs_jht = (basic * Decimal(str(config.bpjs_ketenagakerjaan_pct)) / Decimal("100")).quantize(Decimal("0.01"))

        gross = basic + allowance
        deductions = bpjs_kes + bpjs_jht
        take_home = gross - deductions

        slip = PayrollSlip(
            employee_id=emp.id,
            period_id=period_id,
            slip_no=slip_no,
            gross_income=gross,
            total_deductions=deductions,
            take_home_pay=take_home,
        )
        session.add(slip)
        await session.flush()  # supaya slip.id ter-set untuk FK

        # Standard components
        components = [
            PayrollComponent(
                slip_id=slip.id, code="BASIC", name="Gaji Pokok",
                component_type="INCOME", is_variable=False, amount=basic,
            ),
        ]
        if allowance > 0:
            components.append(PayrollComponent(
                slip_id=slip.id, code="ALLOWANCE", name="Tunjangan Tetap",
                component_type="INCOME", is_variable=False, amount=allowance,
            ))
        if bpjs_kes > 0:
            components.append(PayrollComponent(
                slip_id=slip.id, code="BPJS_KES", name="BPJS Kesehatan",
                component_type="DEDUCTION", is_variable=False, amount=bpjs_kes,
            ))
        if bpjs_jht > 0:
            components.append(PayrollComponent(
                slip_id=slip.id, code="BPJS_JHT", name="BPJS Ketenagakerjaan",
                component_type="DEDUCTION", is_variable=False, amount=bpjs_jht,
            ))
        session.add_all(components)

        # ─── TSK-194: inject pending sales commission sebagai variable INCOME ──
        # Sales commission ada di SalesCommission, link via sales_user_id → users.id
        # Employee → User: via User.employee_id == emp.id
        commission_total, applied_count = await _apply_pending_commissions_to_slip(
            session, slip.id, emp.id, period_id,
        )
        if commission_total > 0:
            # Update slip totals
            slip.gross_income = Decimal(str(slip.gross_income)) + commission_total
            slip.take_home_pay = (
                Decimal(str(slip.gross_income)) - Decimal(str(slip.total_deductions))
            )
        generated += 1

    await session.commit()
    return GenerateSlipsResponse(
        period_id=period_id,
        generated=generated,
        skipped=skipped,
        errors=errors,
    )


async def _apply_pending_commissions_to_slip(
    session: AsyncSession,
    slip_id: UUID,
    employee_id: UUID,
    period_id: UUID,
) -> tuple[Decimal, int]:
    """Pull pending SalesCommission untuk employee ini → create PayrollComponent
    variable INCOME. Mark commission as APPLIED + set target_payroll_period_id.

    Returns: (total_commission_amount, applied_count)
    """
    from app.sales.models import SalesCommission

    # Find user_id for this employee — User doesn't have employee_id; use Employee.user_id
    user_stmt = select(Employee.user_id).where(Employee.id == employee_id)
    user_id_row = (await session.execute(user_stmt)).scalar_one_or_none()
    if user_id_row is None:
        return Decimal("0"), 0

    # Pending commissions untuk user ini (status PENDING + no target_payroll_period_id)
    comm_stmt = select(SalesCommission).where(
        SalesCommission.sales_user_id == user_id_row,
        SalesCommission.status == "PENDING",
        SalesCommission.target_payroll_period_id.is_(None),
    )
    commissions = list((await session.execute(comm_stmt)).scalars().all())
    if not commissions:
        return Decimal("0"), 0

    total = Decimal("0")
    for comm in commissions:
        amount = Decimal(str(comm.commission_amount))
        total += amount
        component = PayrollComponent(
            slip_id=slip_id,
            code=f"SALES_COMMISSION_{str(comm.lead_id)[:8]}",
            name="Komisi Sales (Closed Won)",
            component_type="INCOME",
            is_variable=True,
            amount=amount,
            source_reference=f"sales_commission:{comm.id}",
        )
        session.add(component)
        comm.target_payroll_period_id = period_id
        comm.status = "APPLIED"

    return total, len(commissions)


# ─── Slip Read ─────────────────────────────────────────────────────


async def list_slips(
    session: AsyncSession,
    period_id: UUID | None = None,
    employee_id: UUID | None = None,
) -> list[PayrollSlip]:
    stmt = select(PayrollSlip)
    if period_id is not None:
        stmt = stmt.where(PayrollSlip.period_id == period_id)
    if employee_id is not None:
        stmt = stmt.where(PayrollSlip.employee_id == employee_id)
    stmt = stmt.order_by(PayrollSlip.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_slip(session: AsyncSession, slip_id: UUID) -> PayrollSlip:
    stmt = select(PayrollSlip).where(PayrollSlip.id == slip_id)
    result = await session.execute(stmt)
    s = result.scalar_one_or_none()
    if s is None:
        raise SlipNotFoundError(f"Slip {slip_id} not found")
    return s


async def list_components(
    session: AsyncSession, slip_id: UUID
) -> list[PayrollComponent]:
    stmt = (
        select(PayrollComponent)
        .where(PayrollComponent.slip_id == slip_id)
        .order_by(
            PayrollComponent.component_type.desc(),  # INCOME before DEDUCTION
            PayrollComponent.created_at,
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ─── Slip Mutation ────────────────────────────────────────────────


async def _recompute_slip_totals(
    session: AsyncSession, slip_id: UUID
) -> PayrollSlip:
    components = await list_components(session, slip_id)
    gross = sum((Decimal(str(c.amount)) for c in components if c.component_type == "INCOME"), Decimal("0"))
    deductions = sum((Decimal(str(c.amount)) for c in components if c.component_type == "DEDUCTION"), Decimal("0"))
    slip = await get_slip(session, slip_id)
    slip.gross_income = gross
    slip.total_deductions = deductions
    slip.take_home_pay = gross - deductions
    await session.commit()
    await session.refresh(slip)
    return slip


async def add_component(
    session: AsyncSession, slip_id: UUID, data: PayrollComponentCreate
) -> PayrollComponent:
    slip = await get_slip(session, slip_id)
    period = await get_period(session, slip.period_id)
    if period.status == "LOCKED":
        raise PeriodLockedError("Cannot add component to locked period")

    comp = PayrollComponent(
        slip_id=slip_id,
        code=data.code,
        name=data.name,
        component_type=data.component_type,
        is_variable=data.is_variable,
        amount=data.amount,
        source_reference=data.source_reference,
    )
    session.add(comp)
    await session.commit()
    await session.refresh(comp)
    await _recompute_slip_totals(session, slip_id)
    return comp


async def delete_component(
    session: AsyncSession, component_id: UUID
) -> None:
    stmt = select(PayrollComponent).where(PayrollComponent.id == component_id)
    result = await session.execute(stmt)
    comp = result.scalar_one_or_none()
    if comp is None:
        return
    slip_id = comp.slip_id
    slip = await get_slip(session, slip_id)
    period = await get_period(session, slip.period_id)
    if period.status == "LOCKED":
        raise PeriodLockedError("Cannot delete component from locked period")
    await session.delete(comp)
    await session.commit()
    await _recompute_slip_totals(session, slip_id)


async def set_pph21(
    session: AsyncSession, slip_id: UUID, pph21_amount: Decimal
) -> PayrollSlip:
    """Replace or insert PPh21 component (manual input US-TK-049)."""
    slip = await get_slip(session, slip_id)
    period = await get_period(session, slip.period_id)
    if period.status == "LOCKED":
        raise PeriodLockedError("Cannot set PPh21 on locked period")

    # Hapus existing PPh21 component kalau ada
    stmt = select(PayrollComponent).where(
        PayrollComponent.slip_id == slip_id, PayrollComponent.code == "PPH21"
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        await session.delete(existing)
        await session.commit()

    if pph21_amount > 0:
        comp = PayrollComponent(
            slip_id=slip_id,
            code="PPH21",
            name="PPh 21 (Pajak Penghasilan)",
            component_type="DEDUCTION",
            is_variable=False,
            amount=pph21_amount,
        )
        session.add(comp)
        await session.commit()

    return await _recompute_slip_totals(session, slip_id)


# ─── PPh21 Helper (informational, not used in auto-calc) ──────────


def compute_pph21_progressive(annual_gross: Decimal, ptkp: Decimal = Decimal("54000000")) -> Decimal:
    """PPh21 progressive bracket (Indonesia 2024+).

    Brackets (annual PKP after PTKP deduction):
    - 0 – 60jt: 5%
    - 60jt – 250jt: 15%
    - 250jt – 500jt: 25%
    - 500jt – 5B: 30%
    - >5B: 35%

    PTKP default: TK/0 (lajang) = 54jt/tahun.
    """
    pkp = max(annual_gross - ptkp, Decimal("0"))
    if pkp == 0:
        return Decimal("0")

    brackets = [
        (Decimal("60000000"), Decimal("0.05")),
        (Decimal("250000000"), Decimal("0.15")),
        (Decimal("500000000"), Decimal("0.25")),
        (Decimal("5000000000"), Decimal("0.30")),
    ]
    tax = Decimal("0")
    prev_cap = Decimal("0")
    for cap, rate in brackets:
        if pkp <= prev_cap:
            break
        taxable = min(pkp, cap) - prev_cap
        tax += taxable * rate
        prev_cap = cap
    if pkp > prev_cap:
        tax += (pkp - prev_cap) * Decimal("0.35")
    return tax.quantize(Decimal("0.01"))


# ─── Aggregation helpers ──────────────────────────────────────────


async def count_slips_in_period(session: AsyncSession, period_id: UUID) -> int:
    stmt = select(func.count(PayrollSlip.id)).where(PayrollSlip.period_id == period_id)
    return int((await session.execute(stmt)).scalar_one())


async def sum_gross_in_period(session: AsyncSession, period_id: UUID) -> Decimal:
    stmt = select(func.sum(PayrollSlip.gross_income)).where(
        PayrollSlip.period_id == period_id
    )
    val = (await session.execute(stmt)).scalar_one_or_none()
    return Decimal(str(val)) if val is not None else Decimal("0")


async def sum_take_home_in_period(session: AsyncSession, period_id: UUID) -> Decimal:
    stmt = select(func.sum(PayrollSlip.take_home_pay)).where(
        PayrollSlip.period_id == period_id
    )
    val = (await session.execute(stmt)).scalar_one_or_none()
    return Decimal(str(val)) if val is not None else Decimal("0")
