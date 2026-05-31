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
    MonthlyAttendance,
    PayrollComponent,
    PayrollConfig,
    PayrollPeriod,
    PayrollSlip,
)
from app.payroll.payroll_schemas import (
    CalculatePayrollPreview,
    CalculatePayrollResponse,
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
    """Create payroll period. NC-OP-008-02: prevent duplicate (year, month).

    Two-layer guard:
    1. Application check via SELECT (early fail with clear message)
    2. DB UniqueConstraint(year, month) — race-safe (TSK-056)
    """
    # Application-level pre-check (NC-OP-008-02)
    dup_stmt = select(PayrollPeriod).where(
        PayrollPeriod.year == data.year, PayrollPeriod.month == data.month
    )
    existing = (await session.execute(dup_stmt)).scalar_one_or_none()
    if existing:
        raise DuplicatePeriodError(
            f"Period {data.year}-{data.month:02d} sudah ada (status: {existing.status}, "
            f"id: {existing.id}). NC-OP-008-02 prevents duplicate periods."
        )

    period = PayrollPeriod(
        year=data.year,
        month=data.month,
        pay_date=data.pay_date,
        cutoff_date=data.cutoff_date,
        publish_date=data.publish_date,
        status="DRAFT",
    )
    session.add(period)
    try:
        await session.commit()
    except IntegrityError as e:
        # Race condition catcher: another request created same (year, month)
        # between our SELECT and INSERT. DB constraint enforced (TSK-056).
        await session.rollback()
        raise DuplicatePeriodError(
            f"Period {data.year}-{data.month:02d} sudah ada (race condition). "
            f"NC-OP-008-02 — refresh halaman dan retry."
        ) from e
    await session.refresh(period)
    return period


async def update_period_config(
    session: AsyncSession,
    period_id: UUID,
    pay_date: date | None = None,
    cutoff_date: date | None = None,
    publish_date: date | None = None,
) -> PayrollPeriod:
    """TSK-055 — update period config (pay_date / cutoff / publish). Only DRAFT.

    Once period moves to REVIEWING+, config dianggap final (no edit).
    """
    period = await get_period(session, period_id)
    if period.status != "DRAFT":
        raise PeriodLockedError(
            f"Period status {period.status} — config hanya editable di DRAFT"
        )

    if pay_date is not None:
        period.pay_date = pay_date
    if cutoff_date is not None:
        period.cutoff_date = cutoff_date
    if publish_date is not None:
        period.publish_date = publish_date

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
    """Replace or insert PPh21 component (manual input US-FN-002 AC-03).

    Validates NC-FN-002-02: net pay tidak boleh negative setelah PPh21
    diaplikasikan. Raise NetNegativeError kalau pelanggaran.
    """
    slip = await get_slip(session, slip_id)
    period = await get_period(session, slip.period_id)
    if period.status == "LOCKED":
        raise PeriodLockedError("Cannot set PPh21 on locked period")

    # NC-FN-002-02 pre-check — simulate net dengan PPh21 baru
    # Net = gross - (total_deductions_existing - existing_pph21_amount + new_pph21_amount)
    existing_stmt = select(PayrollComponent).where(
        PayrollComponent.slip_id == slip_id, PayrollComponent.code == "PPH21"
    )
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()
    existing_pph21 = Decimal(str(existing.amount)) if existing else Decimal("0")

    gross = Decimal(str(slip.gross_income))
    deductions = Decimal(str(slip.total_deductions))
    projected_deductions = deductions - existing_pph21 + pph21_amount
    projected_net = gross - projected_deductions
    if projected_net < 0:
        raise NetNegativeError(
            f"Slip {slip.slip_no}: PPh21 {pph21_amount} membuat net pay negative "
            f"(gross={gross}, projected_deductions={projected_deductions}). "
            f"Maximum PPh21: {gross - (deductions - existing_pph21):.2f} (NC-FN-002-02)."
        )

    # Hapus existing PPh21 component kalau ada
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


async def bulk_set_pph21(
    session: AsyncSession,
    period_id: UUID,
    pph21_by_slip_id: dict[UUID, Decimal],
) -> list[PayrollSlip]:
    """Bulk set PPh21 untuk multiple slips dalam 1 period.

    Pre-validate semua: kalau ada slip yang akan net negative → reject all.
    """
    period = await get_period(session, period_id)
    if period.status == "LOCKED":
        raise PeriodLockedError("Cannot bulk-set PPh21 on locked period")

    # Pre-validate all
    blockers: list[str] = []
    for slip_id, pph21_amt in pph21_by_slip_id.items():
        slip = await get_slip(session, slip_id)
        if slip.period_id != period_id:
            blockers.append(f"Slip {slip.slip_no} bukan dari period {period_id}")
            continue
        existing_stmt = select(PayrollComponent).where(
            PayrollComponent.slip_id == slip_id, PayrollComponent.code == "PPH21"
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()
        existing_pph21 = Decimal(str(existing.amount)) if existing else Decimal("0")
        gross = Decimal(str(slip.gross_income))
        deductions = Decimal(str(slip.total_deductions))
        projected_net = gross - (deductions - existing_pph21 + pph21_amt)
        if projected_net < 0:
            blockers.append(
                f"{slip.slip_no}: PPh21 {pph21_amt} → net {projected_net:.2f} (NC-FN-002-02)"
            )

    if blockers:
        raise NetNegativeError(
            "Bulk PPh21 blocked — " + "; ".join(blockers[:5])
            + (f"... ({len(blockers)} total)" if len(blockers) > 5 else "")
        )

    # Apply all
    updated: list[PayrollSlip] = []
    for slip_id, pph21_amt in pph21_by_slip_id.items():
        s = await set_pph21(session, slip_id, pph21_amt)
        updated.append(s)
    return updated


async def suggest_pph21_for_slip(
    session: AsyncSession,
    slip_id: UUID,
    ptkp: Decimal = Decimal("54000000"),  # TK/0 default
) -> Decimal:
    """Suggest PPh21 amount berdasarkan annualized gross × bracket progressive.

    Asumsi: gross bulan ini × 12 = annual gross. Tidak include THR/bonus tahunan.
    Hasil dibagi 12 untuk monthly portion. Manual input tetap Finance discretion.
    """
    slip = await get_slip(session, slip_id)
    gross_monthly = Decimal(str(slip.gross_income))
    annual_gross = gross_monthly * Decimal("12")
    annual_tax = compute_pph21_progressive(annual_gross, ptkp)
    monthly_tax = (annual_tax / Decimal("12")).quantize(Decimal("0.01"))
    return monthly_tax


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


# ─── TSK-050 Payroll Approval Workflow ────────────────────────────


class InvalidStateTransitionError(Exception):
    """Period status tidak match dengan transisi yang diminta."""


class SelfApprovalBlockedError(Exception):
    """Approver tidak boleh sama dengan submitter (NC-FN-002-01 spirit)."""


async def submit_payroll_for_approval(
    session: AsyncSession, period_id: UUID, submitter_user_id: UUID
) -> PayrollPeriod:
    """Finance submit payroll period untuk GM/C-Level review.

    Pre-condition: status == REVIEWING (calc engine sudah jalan + PPh21 set).
    Post-condition: status → PENDING_APPROVAL, notify approvers.
    """
    period = await get_period(session, period_id)
    if period.status != "REVIEWING":
        raise InvalidStateTransitionError(
            f"Period status {period.status} — submit hanya boleh dari REVIEWING "
            f"(post-calc, post-PPh21). NC-FN-002-01."
        )

    period.status = "PENDING_APPROVAL"
    period.submitted_for_review_at = datetime.now(UTC)
    period.submitted_by_user_id = submitter_user_id
    # Clear any prior rejection state
    period.rejected_at = None
    period.rejected_by_user_id = None
    period.rejection_reason = None
    await session.commit()
    await session.refresh(period)

    # Notify GM/C-Level (users with payroll.approve permission)
    try:
        from app.notification.models import NotificationType
        from app.notification.templates import notify_from_template
        from app.identity.models import Permission, Role, RolePermission, User, UserRole

        approver_stmt = (
            select(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(Permission.code == "payroll.approve")
            .distinct()
        )
        approver_ids = list((await session.execute(approver_stmt)).scalars().all())

        slip_count = await count_slips_in_period(session, period_id)
        total_take_home = await sum_take_home_in_period(session, period_id)

        for uid in approver_ids:
            if uid == submitter_user_id:
                continue  # don't self-notify
            await notify_from_template(
                session,
                user_id=uid,
                type=NotificationType.PAYROLL_PENDING_APPROVAL,
                context={
                    "period": f"{period.year}-{period.month:02d}",
                    "employee_count": slip_count,
                    "total_idr": f"{int(total_take_home):,}".replace(",", "."),
                    "run_id": str(period.id),
                },
            )
        if approver_ids:
            await session.commit()
    except Exception:  # noqa: BLE001 — non-blocking notification
        pass

    return period


async def approve_payroll(
    session: AsyncSession,
    period_id: UUID,
    approver_user_id: UUID,
    notes: str | None = None,
) -> PayrollPeriod:
    """GM/C-Level approve payroll. Pre: PENDING_APPROVAL. Post: APPROVED.

    Self-approval blocked: approver ≠ submitter.
    """
    period = await get_period(session, period_id)
    if period.status != "PENDING_APPROVAL":
        raise InvalidStateTransitionError(
            f"Period status {period.status} — approve hanya dari PENDING_APPROVAL"
        )

    if period.submitted_by_user_id == approver_user_id:
        raise SelfApprovalBlockedError(
            "Tidak boleh approve payroll yang Anda submit sendiri (Finance vs GM rule)"
        )

    period.status = "APPROVED"
    period.approved_at = datetime.now(UTC)
    period.approved_by_user_id = approver_user_id
    period.approval_notes = notes
    await session.commit()
    await session.refresh(period)

    # Notify Finance (submitter) — approved
    try:
        from app.notification.models import NotificationType
        from app.notification.templates import notify_from_template

        if period.submitted_by_user_id:
            await notify_from_template(
                session,
                user_id=period.submitted_by_user_id,
                type=NotificationType.PAYROLL_APPROVED,
                context={
                    "period": f"{period.year}-{period.month:02d}",
                    "approver_name": "GM/C-Level",
                    "run_id": str(period.id),
                },
            )
            await session.commit()
    except Exception:  # noqa: BLE001
        pass

    return period


async def reject_payroll(
    session: AsyncSession,
    period_id: UUID,
    rejector_user_id: UUID,
    rejection_reason: str,
) -> PayrollPeriod:
    """GM/C-Level reject payroll — back to REVIEWING untuk Finance fix.

    Pre: PENDING_APPROVAL. Post: REVIEWING.
    """
    period = await get_period(session, period_id)
    if period.status != "PENDING_APPROVAL":
        raise InvalidStateTransitionError(
            f"Period status {period.status} — reject hanya dari PENDING_APPROVAL"
        )

    period.status = "REVIEWING"
    period.rejected_at = datetime.now(UTC)
    period.rejected_by_user_id = rejector_user_id
    period.rejection_reason = rejection_reason
    # Reset submitted_* so Finance harus submit ulang setelah fix
    submitter = period.submitted_by_user_id  # capture for notify
    period.submitted_for_review_at = None
    period.submitted_by_user_id = None
    await session.commit()
    await session.refresh(period)

    # Notify Finance (original submitter)
    try:
        from app.notification.models import NotificationType
        from app.notification.templates import notify_from_template

        if submitter:
            await notify_from_template(
                session,
                user_id=submitter,
                type=NotificationType.APPROVAL_REJECTED,
                context={
                    "request_type": f"Payroll {period.year}-{period.month:02d}",
                    "approver_name": "GM/C-Level",
                    "reason": rejection_reason,
                    "link": f"/payroll?period={period.id}",
                },
            )
            await session.commit()
    except Exception:  # noqa: BLE001
        pass

    return period


# ─── TSK-048 Payroll Calculation Engine ───────────────────────────


class IncompleteAttendanceError(Exception):
    """NC-OP-008-01 — beberapa employee belum ada attendance untuk period."""


class NetNegativeError(Exception):
    """NC-FN-002-02 — net pay < 0 untuk sebuah employee."""


# Standard Indonesian overtime: 1.5× hourly rate (UU Ketenagakerjaan, simplified)
DEFAULT_OVERTIME_MULTIPLIER = Decimal("1.5")
STANDARD_HOURS_PER_DAY = Decimal("8")
# Anomaly threshold: total payroll deviation vs prev month (NC-FN-002-05)
ANOMALY_DEVIATION_PCT = Decimal("30")


def _compute_attendance_factors(
    att: MonthlyAttendance | None,
    working_days: int,
    basic_salary: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """Compute (prorata_basic, overtime_amount, prorata_factor) dari attendance.

    Rules:
    - Paid days = days_present + days_absent_paid (alpha tidak dibayar)
    - Prorata factor = paid_days / working_days (clamp 0..1)
    - Overtime = overtime_hours × (basic / (working_days × 8)) × 1.5

    Returns Decimal triple, all .quantize(0.01).
    """
    if working_days <= 0:
        return Decimal("0.00"), Decimal("0.00"), Decimal("0.00")

    if att is None:
        # No attendance → assume full month (safety net, but caller should validate first)
        return basic_salary.quantize(Decimal("0.01")), Decimal("0.00"), Decimal("1.00")

    paid_days = att.days_present + att.days_absent_paid
    working_days_dec = Decimal(str(working_days))
    paid_days_dec = Decimal(str(paid_days))

    prorata_factor = paid_days_dec / working_days_dec
    # Clamp 0..1 (kalau attendance days > working_days karena edge case dari TSK-047)
    if prorata_factor > Decimal("1"):
        prorata_factor = Decimal("1")
    elif prorata_factor < Decimal("0"):
        prorata_factor = Decimal("0")

    prorata_basic = (basic_salary * prorata_factor).quantize(Decimal("0.01"))

    # Overtime
    overtime_hours = Decimal(str(att.overtime_hours))
    if overtime_hours > 0 and basic_salary > 0:
        hourly_rate = basic_salary / (working_days_dec * STANDARD_HOURS_PER_DAY)
        overtime_amount = (
            overtime_hours * hourly_rate * DEFAULT_OVERTIME_MULTIPLIER
        ).quantize(Decimal("0.01"))
    else:
        overtime_amount = Decimal("0.00")

    return prorata_basic, overtime_amount, prorata_factor.quantize(Decimal("0.0001"))


async def calculate_payroll_preview(
    session: AsyncSession, period_id: UUID
) -> CalculatePayrollPreview:
    """Pre-flight check — show what calc engine WOULD do, no mutation.

    Validates:
    - Period exists & DRAFT
    - All active employees have attendance (NC-OP-008-01)
    - No existing slips (NC-OP-008-02 duplicate prevention)
    """
    from app.payroll.attendance_service import (
        calculate_period_working_days,
        completeness,
    )

    period = await get_period(session, period_id)
    blockers: list[str] = []

    if period.status != "DRAFT":
        blockers.append(
            f"Period status {period.status} — calc hanya boleh di DRAFT (NC-OP-008-02)"
        )

    # Existing slips check (NC-OP-008-02)
    existing_count = await count_slips_in_period(session, period_id)
    if existing_count > 0:
        blockers.append(
            f"Sudah ada {existing_count} slip untuk period ini — clear dulu atau lock period (NC-OP-008-02)"
        )

    # Attendance completeness (NC-OP-008-01)
    _p, working_days, total_active, submitted_count, missing_ids = await completeness(
        session, period_id
    )

    if missing_ids:
        blockers.append(
            f"Attendance belum lengkap: {len(missing_ids)}/{total_active} karyawan belum ada data (NC-OP-008-01)"
        )

    return CalculatePayrollPreview(
        period_id=period_id,
        calendar_working_days=working_days,
        attendance_missing_count=len(missing_ids),
        attendance_missing_employee_ids=missing_ids,
        estimated_employee_count=total_active,
        can_proceed=len(blockers) == 0,
        blockers=blockers,
    )


async def _check_anomaly(
    session: AsyncSession, period: PayrollPeriod, current_total_gross: Decimal
) -> str | None:
    """NC-FN-002-05 — flag if total deviates >30% from prev month."""
    # Prev month
    prev_month = period.month - 1
    prev_year = period.year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1

    prev_period_stmt = select(PayrollPeriod).where(
        PayrollPeriod.year == prev_year, PayrollPeriod.month == prev_month
    )
    prev_period = (await session.execute(prev_period_stmt)).scalar_one_or_none()
    if prev_period is None:
        return None

    prev_gross = await sum_gross_in_period(session, prev_period.id)
    if prev_gross <= 0:
        return None

    deviation_pct = abs((current_total_gross - prev_gross) / prev_gross * Decimal("100"))
    if deviation_pct > ANOMALY_DEVIATION_PCT:
        return (
            f"Total gross berbeda {deviation_pct:.1f}% dari bulan sebelumnya "
            f"(Rp {prev_gross:,.0f} → Rp {current_total_gross:,.0f}). "
            f"Cek anomaly sebelum approve (NC-FN-002-05)."
        )
    return None


async def calculate_payroll(
    session: AsyncSession, period_id: UUID
) -> CalculatePayrollResponse:
    """Full payroll calculation — attendance × config → slips with components.

    TSK-048 main entrypoint. Differs dari generate_slips_for_period (TSK-046):
    - Validates attendance completeness (NC-OP-008-01) → raises if missing
    - Validates no existing slips (NC-OP-008-02)
    - Applies prorata basic + overtime per attendance
    - Anomaly check vs prev month (NC-FN-002-05)
    - Blocks net negative (NC-FN-002-02)
    """
    from app.identity.models import User as _User
    from app.payroll.attendance_service import calculate_period_working_days

    period = await get_period(session, period_id)
    if period.status != "DRAFT":
        raise PeriodLockedError(
            f"Period {period.year}-{period.month:02d} status {period.status} — calc hanya di DRAFT"
        )

    # Pre-validation
    preview = await calculate_payroll_preview(session, period_id)
    if not preview.can_proceed:
        raise IncompleteAttendanceError(
            "Calc payroll blocked: " + "; ".join(preview.blockers)
        )

    working_days = preview.calendar_working_days

    # Fetch all active employees + nik + attendance + config
    emp_stmt = (
        select(Employee, _User.nik.label("nik"))
        .join(_User, Employee.user_id == _User.id)
        .where(
            Employee.deleted_at.is_(None),
            Employee.status.in_([EmployeeStatus.ACTIVE, EmployeeStatus.PROBATION]),
        )
    )
    employees_with_nik = list((await session.execute(emp_stmt)).all())

    # Attendance by employee_id
    att_stmt = select(MonthlyAttendance).where(
        MonthlyAttendance.period_id == period_id
    )
    att_by_emp = {
        a.employee_id: a
        for a in (await session.execute(att_stmt)).scalars().all()
    }

    generated = 0
    skipped = 0
    errors: list[str] = []
    total_gross = Decimal("0")
    total_deductions = Decimal("0")
    total_take_home = Decimal("0")

    for emp, emp_nik in employees_with_nik:
        # Skip if slip already exists (defense — should be caught by preview)
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

        attendance = att_by_emp.get(emp.id)
        # Already validated in preview, but double-check
        if attendance is None:
            errors.append(f"{emp_nik}: attendance missing (re-validate)")
            continue

        basic_salary = Decimal(str(config.basic_salary))
        allowance = Decimal(str(config.fixed_allowance))

        # Compute prorata + overtime
        prorata_basic, overtime_amount, prorata_factor = _compute_attendance_factors(
            attendance, working_days, basic_salary
        )

        # BPJS based on basic_salary (UU rules — bukan prorata)
        bpjs_kes = (
            basic_salary * Decimal(str(config.bpjs_kesehatan_pct)) / Decimal("100")
        ).quantize(Decimal("0.01"))
        bpjs_jht = (
            basic_salary * Decimal(str(config.bpjs_ketenagakerjaan_pct)) / Decimal("100")
        ).quantize(Decimal("0.01"))

        gross = prorata_basic + allowance + overtime_amount
        deductions = bpjs_kes + bpjs_jht
        take_home = gross - deductions

        # NC-FN-002-02: block if net negative
        if take_home < 0:
            raise NetNegativeError(
                f"{emp_nik}: net pay negative (gross={gross}, deductions={deductions}). "
                f"Review komponen sebelum lanjut (NC-FN-002-02)."
            )

        slip_no = f"SLIP-{period.year}{period.month:02d}-{emp_nik}"
        slip = PayrollSlip(
            employee_id=emp.id,
            period_id=period_id,
            slip_no=slip_no,
            gross_income=gross,
            total_deductions=deductions,
            take_home_pay=take_home,
        )
        session.add(slip)
        await session.flush()

        # Build components
        components = [
            PayrollComponent(
                slip_id=slip.id,
                code="BASIC_PRORATA" if prorata_factor < Decimal("1") else "BASIC",
                name=(
                    f"Gaji Pokok ({attendance.days_present}+{attendance.days_absent_paid}/{working_days} hari)"
                    if prorata_factor < Decimal("1")
                    else "Gaji Pokok"
                ),
                component_type="INCOME",
                is_variable=False,
                amount=prorata_basic,
                source_reference=f"attendance:{attendance.id}",
            ),
        ]
        if allowance > 0:
            components.append(PayrollComponent(
                slip_id=slip.id, code="ALLOWANCE", name="Tunjangan Tetap",
                component_type="INCOME", is_variable=False, amount=allowance,
            ))
        if overtime_amount > 0:
            components.append(PayrollComponent(
                slip_id=slip.id,
                code="OVERTIME",
                name=f"Lembur ({attendance.overtime_hours} jam × 1.5)",
                component_type="INCOME",
                is_variable=True,
                amount=overtime_amount,
                source_reference=f"attendance:{attendance.id}",
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

        # Inject pending commissions (TSK-194)
        commission_total, _applied = await _apply_pending_commissions_to_slip(
            session, slip.id, emp.id, period_id,
        )
        if commission_total > 0:
            slip.gross_income = Decimal(str(slip.gross_income)) + commission_total
            slip.take_home_pay = (
                Decimal(str(slip.gross_income)) - Decimal(str(slip.total_deductions))
            )

        total_gross += Decimal(str(slip.gross_income))
        total_deductions += Decimal(str(slip.total_deductions))
        total_take_home += Decimal(str(slip.take_home_pay))
        generated += 1

    await session.commit()

    # Anomaly check (NC-FN-002-05) — non-blocking warning
    anomaly_warnings: list[str] = []
    anomaly = await _check_anomaly(session, period, total_gross)
    if anomaly:
        anomaly_warnings.append(anomaly)

    # Move period status to REVIEWING (ready for Finance/GM review)
    if generated > 0 and period.status == "DRAFT":
        period.status = "REVIEWING"
        await session.commit()

    return CalculatePayrollResponse(
        period_id=period_id,
        generated=generated,
        skipped=skipped,
        total_gross_idr=total_gross,
        total_deductions_idr=total_deductions,
        total_take_home_idr=total_take_home,
        employee_count=generated + skipped,
        anomaly_warnings=anomaly_warnings,
        errors=errors,
    )
