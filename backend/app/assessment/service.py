"""Assessment business logic — TSK-021.

Scoring formula (knowledge.md sec.6):
- final_score = (okr_score × okr_weight_pct%) + (weighted_score × weighted_weight_pct%)
- weighted_score = sum (AssessmentItem.weight_pct × submitted_score) / 100

Threshold flag (per spec):
- 70+ : GREEN (baik)
- 60-69: YELLOW (perlu attention)
- 50-59: ORANGE (warning)
- <50: RED (critical)

SP auto-trigger:
- 1 bulan ORANGE/RED  → flag YELLOW di system
- 2 bulan berturut    → flag ORANGE
- 3 bulan berturut    → SP auto-suggest (manager harus approve sebelum issue)
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.assessment.models import (
    Assessment,
    AssessmentConfig,
    AssessmentItem,
    AssessmentPeriod,
    OkrKeyResult,
    OkrObjective,
    WarningLetter,
)
from app.assessment.schemas import (
    AssessmentSubmit,
    ConfigCreate,
    ObjectiveCreate,
    PeriodCreate,
    WarningLetterCreate,
)
from app.organization.models import Department, Employee


# ─── Exceptions ────────────────────────────────────────────────────


class PeriodNotFoundError(Exception):
    pass


class ConfigNotFoundError(Exception):
    pass


class ObjectiveNotFoundError(Exception):
    pass


class AssessmentNotFoundError(Exception):
    pass


class WarningLetterNotFoundError(Exception):
    pass


class InvalidAssessmentStateError(Exception):
    pass


# ─── Constants ─────────────────────────────────────────────────────


THRESHOLD_GREEN = Decimal("70")
THRESHOLD_YELLOW = Decimal("60")
THRESHOLD_ORANGE = Decimal("50")
# < ORANGE = RED


def derive_threshold_flag(score: Decimal | None) -> str:
    if score is None:
        return "NONE"
    if score >= THRESHOLD_GREEN:
        return "GREEN"
    if score >= THRESHOLD_YELLOW:
        return "YELLOW"
    if score >= THRESHOLD_ORANGE:
        return "ORANGE"
    return "RED"


def period_label(period: AssessmentPeriod) -> str:
    months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Des"]
    return f"{months[period.month - 1]} {period.year}"


# ─── Period CRUD ───────────────────────────────────────────────────


async def list_periods(session: AsyncSession) -> list[AssessmentPeriod]:
    stmt = select(AssessmentPeriod).order_by(
        AssessmentPeriod.year.desc(), AssessmentPeriod.month.desc()
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_period(session: AsyncSession, period_id: UUID) -> AssessmentPeriod:
    stmt = select(AssessmentPeriod).where(AssessmentPeriod.id == period_id)
    result = await session.execute(stmt)
    p = result.scalar_one_or_none()
    if p is None:
        raise PeriodNotFoundError(f"Period {period_id} not found")
    return p


async def create_period(session: AsyncSession, data: PeriodCreate) -> AssessmentPeriod:
    # Check duplicate
    existing = await session.execute(
        select(AssessmentPeriod).where(
            AssessmentPeriod.year == data.year,
            AssessmentPeriod.month == data.month,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise InvalidAssessmentStateError(
            f"Period {data.year}-{data.month:02d} sudah ada"
        )
    period = AssessmentPeriod(year=data.year, month=data.month, is_closed=False)
    session.add(period)
    await session.commit()
    await session.refresh(period)
    return period


async def close_period(session: AsyncSession, period_id: UUID) -> AssessmentPeriod:
    period = await get_period(session, period_id)
    period.is_closed = True
    await session.commit()
    await session.refresh(period)
    return period


# ─── Config CRUD ───────────────────────────────────────────────────


async def get_config(session: AsyncSession, config_id: UUID) -> AssessmentConfig:
    stmt = select(AssessmentConfig).where(AssessmentConfig.id == config_id)
    result = await session.execute(stmt)
    c = result.scalar_one_or_none()
    if c is None:
        raise ConfigNotFoundError(f"Config {config_id} not found")
    return c


async def get_active_config_for_dept(
    session: AsyncSession, department_id: UUID, as_of: date | None = None
) -> AssessmentConfig | None:
    """Get config aktif untuk dept (latest effective_date <= as_of)."""
    as_of = as_of or date.today()
    stmt = (
        select(AssessmentConfig)
        .where(
            AssessmentConfig.department_id == department_id,
            AssessmentConfig.effective_date <= as_of,
        )
        .order_by(AssessmentConfig.effective_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_configs(session: AsyncSession) -> list[AssessmentConfig]:
    stmt = select(AssessmentConfig).order_by(AssessmentConfig.effective_date.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_items_for_config(
    session: AsyncSession, config_id: UUID
) -> list[AssessmentItem]:
    stmt = select(AssessmentItem).where(AssessmentItem.config_id == config_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_config(
    session: AsyncSession, data: ConfigCreate, configured_by_user_id: UUID | None
) -> AssessmentConfig:
    """Create config + items dalam 1 transaction."""
    # Validate weights sum to 100
    if abs(data.okr_weight_pct + data.weighted_weight_pct - Decimal("100")) > Decimal("0.01"):
        raise InvalidAssessmentStateError(
            "okr_weight_pct + weighted_weight_pct harus = 100"
        )

    if data.items:
        item_sum = sum((i.weight_pct for i in data.items), Decimal("0"))
        if abs(item_sum - Decimal("100")) > Decimal("0.01"):
            raise InvalidAssessmentStateError(
                f"Sum item weight_pct = {item_sum}, harus = 100"
            )

    config = AssessmentConfig(
        department_id=data.department_id,
        okr_weight_pct=data.okr_weight_pct,
        weighted_weight_pct=data.weighted_weight_pct,
        effective_date=data.effective_date,
        configured_by_user_id=configured_by_user_id,
    )
    session.add(config)
    await session.flush()

    for item_data in data.items:
        item = AssessmentItem(
            config_id=config.id,
            code=item_data.code,
            name=item_data.name,
            weight_pct=item_data.weight_pct,
        )
        session.add(item)

    await session.commit()
    await session.refresh(config)
    return config


# ─── OKR CRUD ──────────────────────────────────────────────────────


async def get_objective(session: AsyncSession, objective_id: UUID) -> OkrObjective:
    stmt = select(OkrObjective).where(OkrObjective.id == objective_id)
    result = await session.execute(stmt)
    obj = result.scalar_one_or_none()
    if obj is None:
        raise ObjectiveNotFoundError(f"Objective {objective_id} not found")
    return obj


async def list_objectives(
    session: AsyncSession,
    employee_id: UUID | None = None,
    year: int | None = None,
    quarter: int | None = None,
) -> list[OkrObjective]:
    stmt = select(OkrObjective)
    if employee_id is not None:
        stmt = stmt.where(OkrObjective.employee_id == employee_id)
    if year is not None:
        stmt = stmt.where(OkrObjective.year == year)
    if quarter is not None:
        stmt = stmt.where(OkrObjective.quarter == quarter)
    stmt = stmt.order_by(OkrObjective.year.desc(), OkrObjective.quarter.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_objective(
    session: AsyncSession, data: ObjectiveCreate, set_by_user_id: UUID | None
) -> OkrObjective:
    obj = OkrObjective(
        employee_id=data.employee_id,
        year=data.year,
        quarter=data.quarter,
        objective=data.objective,
        set_by_user_id=set_by_user_id,
    )
    session.add(obj)
    await session.flush()
    for kr_data in data.key_results:
        kr = OkrKeyResult(
            objective_id=obj.id,
            description=kr_data.description,
            target=kr_data.target,
            progress_pct=Decimal("0"),
        )
        session.add(kr)
    await session.commit()
    await session.refresh(obj)
    return obj


async def get_key_results_for_objective(
    session: AsyncSession, objective_id: UUID
) -> list[OkrKeyResult]:
    stmt = select(OkrKeyResult).where(OkrKeyResult.objective_id == objective_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_key_result(
    session: AsyncSession,
    kr_id: UUID,
    achieved: Decimal | None,
    progress_pct: Decimal | None,
) -> OkrKeyResult:
    stmt = select(OkrKeyResult).where(OkrKeyResult.id == kr_id)
    result = await session.execute(stmt)
    kr = result.scalar_one_or_none()
    if kr is None:
        raise ObjectiveNotFoundError(f"KeyResult {kr_id} not found")
    if achieved is not None:
        kr.achieved = achieved
    if progress_pct is not None:
        kr.progress_pct = progress_pct
    await session.commit()
    await session.refresh(kr)
    return kr


# ─── Assessment scoring ────────────────────────────────────────────


async def submit_assessment(
    session: AsyncSession,
    data: AssessmentSubmit,
    submitted_by_user_id: UUID,
) -> Assessment:
    """Submit/upsert assessment scores untuk 1 karyawan 1 periode.

    Steps:
    1. Get period + employee + dept config
    2. Compute weighted_score = sum(item.weight × score) / 100
    3. Compute final_score = okr × okr_weight% + weighted × weighted_weight%
    4. Upsert Assessment record
    """
    # Validate period
    period = await get_period(session, data.period_id)
    if period.is_closed:
        raise InvalidAssessmentStateError(
            f"Period {period.year}-{period.month:02d} sudah closed"
        )

    # Get employee + dept
    emp_result = await session.execute(
        select(Employee).where(Employee.id == data.employee_id, Employee.deleted_at.is_(None))
    )
    emp = emp_result.scalar_one_or_none()
    if emp is None:
        raise InvalidAssessmentStateError(f"Employee {data.employee_id} not found")
    if emp.department_id is None:
        raise InvalidAssessmentStateError(
            "Employee belum punya department — tidak ada config bobot"
        )

    # Get active config for dept (effective_date <= period start)
    config_date = date(period.year, period.month, 1)
    config = await get_active_config_for_dept(session, emp.department_id, config_date)
    if config is None:
        raise InvalidAssessmentStateError(
            f"Dept belum punya assessment config aktif per {config_date}"
        )

    # Get items untuk validation
    items = await get_items_for_config(session, config.id)
    item_by_code = {i.code: i for i in items}

    # Compute weighted_score
    weighted_score = Decimal("0")
    for ws in data.weighted_items:
        item = item_by_code.get(ws.item_code)
        if item is None:
            raise InvalidAssessmentStateError(
                f"Item code '{ws.item_code}' tidak ada di config dept ini"
            )
        weighted_score += (item.weight_pct * ws.score) / Decimal("100")

    # Compute final_score
    okr_part = (data.okr_score * config.okr_weight_pct) / Decimal("100")
    weighted_part = (weighted_score * config.weighted_weight_pct) / Decimal("100")
    final_score = okr_part + weighted_part

    # Upsert: cari existing
    existing = await session.execute(
        select(Assessment).where(
            Assessment.employee_id == data.employee_id,
            Assessment.period_id == data.period_id,
        )
    )
    assessment = existing.scalar_one_or_none()
    if assessment is None:
        assessment = Assessment(
            employee_id=data.employee_id,
            period_id=data.period_id,
            okr_score=data.okr_score,
            weighted_score=weighted_score,
            final_score=final_score,
            notes=data.notes,
            submitted_by_user_id=submitted_by_user_id,
        )
        session.add(assessment)
    else:
        assessment.okr_score = data.okr_score
        assessment.weighted_score = weighted_score
        assessment.final_score = final_score
        assessment.notes = data.notes
        assessment.submitted_by_user_id = submitted_by_user_id

    await session.commit()
    await session.refresh(assessment)
    return assessment


async def get_assessment(session: AsyncSession, assessment_id: UUID) -> Assessment:
    stmt = select(Assessment).where(Assessment.id == assessment_id)
    result = await session.execute(stmt)
    a = result.scalar_one_or_none()
    if a is None:
        raise AssessmentNotFoundError(f"Assessment {assessment_id} not found")
    return a


async def list_assessments(
    session: AsyncSession,
    period_id: UUID | None = None,
    employee_id: UUID | None = None,
    department_id: UUID | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Assessment], int]:
    page = max(page, 1)
    page_size = max(min(page_size, 200), 1)

    base = select(Assessment)
    if period_id is not None:
        base = base.where(Assessment.period_id == period_id)
    if employee_id is not None:
        base = base.where(Assessment.employee_id == employee_id)
    if department_id is not None:
        # Join Employee untuk filter dept
        base = base.join(Employee, Assessment.employee_id == Employee.id).where(
            Employee.department_id == department_id
        )

    count_stmt = select(func.count()).select_from(base.subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    stmt = (
        base.order_by(Assessment.final_score.desc().nulls_last())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


# ─── SP Threshold Check ────────────────────────────────────────────


async def check_employee_threshold(
    session: AsyncSession,
    employee_id: UUID,
    months_window: int = 3,
) -> dict:
    """Cek N bulan terakhir — kalau N bulan berturut < ORANGE → suggest SP."""
    stmt = (
        select(Assessment, AssessmentPeriod)
        .join(AssessmentPeriod, Assessment.period_id == AssessmentPeriod.id)
        .where(Assessment.employee_id == employee_id)
        .order_by(AssessmentPeriod.year.desc(), AssessmentPeriod.month.desc())
        .limit(months_window)
    )
    result = await session.execute(stmt)
    rows = list(result.all())

    recent_scores = []
    consecutive_low = 0
    for assessment, period in rows:
        flag = derive_threshold_flag(assessment.final_score)
        recent_scores.append(
            {
                "period": period_label(period),
                "final_score": float(assessment.final_score) if assessment.final_score else None,
                "flag": flag,
            }
        )
        if flag in {"ORANGE", "RED"}:
            consecutive_low += 1
        else:
            break  # not consecutive

    # Determine suggested SP level
    suggested_sp = None
    action_required = False
    if consecutive_low >= 3:
        suggested_sp = "SP1"  # First time → SP1; subsequent → SP2/SP3
        action_required = True
        # Check existing SP history
        sp_stmt = (
            select(WarningLetter)
            .where(
                WarningLetter.employee_id == employee_id,
                WarningLetter.deleted_at.is_(None),
            )
            .order_by(WarningLetter.issued_date.desc())
            .limit(1)
        )
        sp_result = await session.execute(sp_stmt)
        last_sp = sp_result.scalar_one_or_none()
        if last_sp is not None:
            if last_sp.level == "SP1":
                suggested_sp = "SP2"
            elif last_sp.level == "SP2":
                suggested_sp = "SP3"
            elif last_sp.level == "SP3":
                # Already at max → trigger layoff workflow (handled di separation domain)
                suggested_sp = "LAYOFF_TRIGGER"

    return {
        "consecutive_low_months": consecutive_low,
        "threshold_score": THRESHOLD_ORANGE,
        "recent_scores": recent_scores,
        "suggested_sp_level": suggested_sp,
        "action_required": action_required,
    }


# ─── Warning Letter ────────────────────────────────────────────────


async def issue_warning_letter(
    session: AsyncSession,
    data: WarningLetterCreate,
    approver_user_id: UUID,
) -> WarningLetter:
    """Issue SP1/SP2/SP3 untuk karyawan. Manager+/GM approve."""
    # Validate employee exists
    emp_result = await session.execute(
        select(Employee).where(Employee.id == data.employee_id, Employee.deleted_at.is_(None))
    )
    if emp_result.scalar_one_or_none() is None:
        raise InvalidAssessmentStateError(f"Employee {data.employee_id} not found")

    # Check SP level sequence (SP2 butuh ada SP1 sebelumnya, dst)
    existing_stmt = (
        select(WarningLetter)
        .where(
            WarningLetter.employee_id == data.employee_id,
            WarningLetter.deleted_at.is_(None),
        )
        .order_by(WarningLetter.issued_date.desc())
        .limit(1)
    )
    existing_result = await session.execute(existing_stmt)
    last_sp = existing_result.scalar_one_or_none()

    level_order = {"SP1": 1, "SP2": 2, "SP3": 3}
    new_level = level_order.get(data.level, 0)
    if last_sp is not None:
        last_level = level_order.get(last_sp.level, 0)
        if new_level <= last_level:
            raise InvalidAssessmentStateError(
                f"Sudah ada {last_sp.level} sebelumnya — tidak bisa issue {data.level} (must escalate)"
            )
        if new_level > last_level + 1:
            raise InvalidAssessmentStateError(
                f"Tidak bisa skip level. Last: {last_sp.level}, requested: {data.level}"
            )
    elif new_level > 1:
        raise InvalidAssessmentStateError(
            f"Belum ada SP sebelumnya, tidak bisa langsung issue {data.level}"
        )

    sp = WarningLetter(
        employee_id=data.employee_id,
        level=data.level,
        issued_date=data.issued_date,
        reason=data.reason,
        document_url=data.document_url,
        is_ai_drafted=False,
        approved_by_user_id=approver_user_id,
    )
    session.add(sp)
    await session.commit()
    await session.refresh(sp)
    return sp


async def list_warning_letters(
    session: AsyncSession,
    employee_id: UUID | None = None,
) -> list[WarningLetter]:
    stmt = select(WarningLetter).where(WarningLetter.deleted_at.is_(None))
    if employee_id is not None:
        stmt = stmt.where(WarningLetter.employee_id == employee_id)
    stmt = stmt.order_by(WarningLetter.issued_date.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ─── Helpers ───────────────────────────────────────────────────────


def calc_total_pages(total: int, page_size: int) -> int:
    if total == 0:
        return 0
    return math.ceil(total / page_size)
