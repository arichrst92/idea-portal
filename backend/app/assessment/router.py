"""Assessment router — TSK-021.

Endpoints di /api/v1:
- /assessment-periods                — list, create, close
- /assessment-configs                — list, create (per dept, Executive only)
- /okr-objectives                    — list, create + key results CRUD
- /okr-key-results/{id}              — update progress
- /assessments                       — list, get, submit
- /assessment-threshold-check/{nik}  — cek apakah perlu SP
- /warning-letters                   — list, issue (SP1/SP2/SP3)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.assessment import service
from app.assessment.schemas import (
    AssessmentListResponse,
    AssessmentOut,
    AssessmentSubmit,
    ConfigCreate,
    ConfigOut,
    ItemOut,
    KeyResultOut,
    KeyResultUpdate,
    ObjectiveCreate,
    ObjectiveOut,
    PeriodCreate,
    PeriodOut,
    ThresholdCheckResponse,
    WarningLetterCreate,
    WarningLetterOut,
)
from app.assessment.service import (
    AssessmentNotFoundError,
    ConfigNotFoundError,
    InvalidAssessmentStateError,
    ObjectiveNotFoundError,
    PeriodNotFoundError,
)
from app.core.audit import audit_log
from app.core.deps import (
    CurrentUser,
    DBSession,
    require_executive,
    require_permission,
)
from app.identity.models import User
from app.organization.models import Department, Employee

router = APIRouter(tags=["assessment"])


# ─── Helpers ───────────────────────────────────────────────────────


async def _lookup_employee_info(session, employee_id: UUID) -> tuple[str | None, str | None, str | None, UUID | None]:
    """(nik, name, dept_name, dept_id)."""
    row = await session.execute(
        select(Employee.full_name, Employee.department_id, User.nik, Department.name)
        .join(User, Employee.user_id == User.id)
        .outerjoin(Department, Employee.department_id == Department.id)
        .where(Employee.id == employee_id)
    )
    r = row.first()
    if r is None:
        return None, None, None, None
    return r[2], r[0], r[3], r[1]


# ─── Period endpoints ─────────────────────────────────────────────


@router.get("/assessment-periods", response_model=list[PeriodOut])
async def list_periods_endpoint(
    session: DBSession,
    _user=Depends(require_permission("assessment.view")),
) -> list[PeriodOut]:
    periods = await service.list_periods(session)
    return [PeriodOut.model_validate(p) for p in periods]


@router.post(
    "/assessment-periods",
    response_model=PeriodOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_period_endpoint(
    request: Request,
    data: PeriodCreate,
    session: DBSession,
    user=Depends(require_permission("assessment.configure")),
) -> PeriodOut:
    try:
        period = await service.create_period(session, data)
    except InvalidAssessmentStateError as e:
        raise HTTPException(status_code=400, detail={"code": "DUPLICATE", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="ASSESSMENT_PERIOD_CREATED",
        resource_type="assessment_period",
        resource_id=str(period.id),
        ip_address=request.client.host if request.client else None,
    )
    return PeriodOut.model_validate(period)


@router.post("/assessment-periods/{period_id}/close", response_model=PeriodOut)
async def close_period_endpoint(
    request: Request,
    period_id: UUID,
    session: DBSession,
    user=Depends(require_permission("assessment.configure")),
) -> PeriodOut:
    try:
        period = await service.close_period(session, period_id)
    except PeriodNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="ASSESSMENT_PERIOD_CLOSED",
        resource_type="assessment_period",
        resource_id=str(period.id),
        ip_address=request.client.host if request.client else None,
    )
    return PeriodOut.model_validate(period)


# ─── Config endpoints ──────────────────────────────────────────────


@router.get("/assessment-configs", response_model=list[ConfigOut])
async def list_configs_endpoint(
    session: DBSession,
    _user=Depends(require_permission("assessment.view")),
) -> list[ConfigOut]:
    configs = await service.list_configs(session)
    out: list[ConfigOut] = []
    for c in configs:
        items = await service.get_items_for_config(session, c.id)
        dept_row = await session.execute(
            select(Department.name).where(Department.id == c.department_id)
        )
        out.append(
            ConfigOut(
                id=c.id,
                department_id=c.department_id,
                okr_weight_pct=c.okr_weight_pct,
                weighted_weight_pct=c.weighted_weight_pct,
                effective_date=c.effective_date,
                configured_by_user_id=c.configured_by_user_id,
                created_at=c.created_at,
                department_name=dept_row.scalar_one_or_none(),
                items=[ItemOut.model_validate(i) for i in items],
            )
        )
    return out


@router.post(
    "/assessment-configs",
    response_model=ConfigOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_config_endpoint(
    request: Request,
    data: ConfigCreate,
    session: DBSession,
    user=Depends(require_permission("assessment.configure")),
) -> ConfigOut:
    try:
        config = await service.create_config(session, data, user.id)
    except InvalidAssessmentStateError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_CONFIG", "message": str(e)},
        ) from e

    await audit_log(
        session=session,
        actor=user,
        action="ASSESSMENT_CONFIG_CREATED",
        resource_type="assessment_config",
        resource_id=str(config.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "dept_id": str(data.department_id),
            "okr_pct": float(data.okr_weight_pct),
            "weighted_pct": float(data.weighted_weight_pct),
            "items_count": len(data.items),
        },
    )

    items = await service.get_items_for_config(session, config.id)
    dept_row = await session.execute(
        select(Department.name).where(Department.id == config.department_id)
    )
    return ConfigOut(
        id=config.id,
        department_id=config.department_id,
        okr_weight_pct=config.okr_weight_pct,
        weighted_weight_pct=config.weighted_weight_pct,
        effective_date=config.effective_date,
        configured_by_user_id=config.configured_by_user_id,
        created_at=config.created_at,
        department_name=dept_row.scalar_one_or_none(),
        items=[ItemOut.model_validate(i) for i in items],
    )


# ─── OKR endpoints ────────────────────────────────────────────────


@router.get("/okr-objectives", response_model=list[ObjectiveOut])
async def list_objectives_endpoint(
    session: DBSession,
    _user=Depends(require_permission("assessment.view")),
    employee_id: UUID | None = Query(None),
    year: int | None = Query(None),
    quarter: int | None = Query(None),
) -> list[ObjectiveOut]:
    objectives = await service.list_objectives(session, employee_id, year, quarter)
    out: list[ObjectiveOut] = []
    for o in objectives:
        nik, name, _, _ = await _lookup_employee_info(session, o.employee_id)
        krs = await service.get_key_results_for_objective(session, o.id)
        avg = (
            sum((kr.progress_pct for kr in krs), Decimal("0")) / len(krs)
            if krs
            else Decimal("0")
        )
        out.append(
            ObjectiveOut(
                id=o.id,
                employee_id=o.employee_id,
                year=o.year,
                quarter=o.quarter,
                objective=o.objective,
                set_by_user_id=o.set_by_user_id,
                created_at=o.created_at,
                employee_nik=nik,
                employee_name=name,
                key_results=[KeyResultOut.model_validate(kr) for kr in krs],
                avg_progress=avg,
            )
        )
    return out


@router.post(
    "/okr-objectives",
    response_model=ObjectiveOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_objective_endpoint(
    request: Request,
    data: ObjectiveCreate,
    session: DBSession,
    user=Depends(require_permission("okr.create")),
) -> ObjectiveOut:
    obj = await service.create_objective(session, data, user.id)

    await audit_log(
        session=session,
        actor=user,
        action="OKR_OBJECTIVE_CREATED",
        resource_type="okr_objective",
        resource_id=str(obj.id),
        ip_address=request.client.host if request.client else None,
        after_state={"year": data.year, "quarter": data.quarter},
    )

    nik, name, _, _ = await _lookup_employee_info(session, obj.employee_id)
    krs = await service.get_key_results_for_objective(session, obj.id)
    return ObjectiveOut(
        id=obj.id,
        employee_id=obj.employee_id,
        year=obj.year,
        quarter=obj.quarter,
        objective=obj.objective,
        set_by_user_id=obj.set_by_user_id,
        created_at=obj.created_at,
        employee_nik=nik,
        employee_name=name,
        key_results=[KeyResultOut.model_validate(kr) for kr in krs],
        avg_progress=Decimal("0"),
    )


@router.patch("/okr-key-results/{kr_id}", response_model=KeyResultOut)
async def update_kr_endpoint(
    kr_id: UUID,
    data: KeyResultUpdate,
    session: DBSession,
    _user=Depends(require_permission("okr.edit")),
) -> KeyResultOut:
    try:
        kr = await service.update_key_result(session, kr_id, data.achieved, data.progress_pct)
    except ObjectiveNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    return KeyResultOut.model_validate(kr)


# ─── Assessment endpoints ─────────────────────────────────────────


@router.get("/assessments", response_model=AssessmentListResponse)
async def list_assessments_endpoint(
    session: DBSession,
    _user=Depends(require_permission("assessment.view")),
    period_id: UUID | None = Query(None),
    employee_id: UUID | None = Query(None),
    department_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> AssessmentListResponse:
    assessments, total = await service.list_assessments(
        session,
        period_id=period_id,
        employee_id=employee_id,
        department_id=department_id,
        page=page,
        page_size=page_size,
    )

    items = []
    for a in assessments:
        nik, name, dept, _ = await _lookup_employee_info(session, a.employee_id)
        period_row = await session.execute(
            select(service.AssessmentPeriod).where(service.AssessmentPeriod.id == a.period_id)
        )
        period = period_row.scalar_one_or_none()
        items.append(
            AssessmentOut(
                id=a.id,
                employee_id=a.employee_id,
                period_id=a.period_id,
                okr_score=a.okr_score,
                weighted_score=a.weighted_score,
                final_score=a.final_score,
                notes=a.notes,
                submitted_by_user_id=a.submitted_by_user_id,
                created_at=a.created_at,
                employee_nik=nik,
                employee_name=name,
                department_name=dept,
                period_label=service.period_label(period) if period else None,
                threshold_flag=service.derive_threshold_flag(a.final_score),
            )
        )

    return AssessmentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=service.calc_total_pages(total, page_size),
    )


@router.post(
    "/assessments",
    response_model=AssessmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit_assessment_endpoint(
    request: Request,
    data: AssessmentSubmit,
    session: DBSession,
    user=Depends(require_permission("assessment.create")),
) -> AssessmentOut:
    try:
        a = await service.submit_assessment(session, data, user.id)
    except (PeriodNotFoundError, InvalidAssessmentStateError) as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ASSESSMENT", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="ASSESSMENT_SUBMITTED",
        resource_type="assessment",
        resource_id=str(a.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "okr_score": float(a.okr_score) if a.okr_score else None,
            "weighted_score": float(a.weighted_score) if a.weighted_score else None,
            "final_score": float(a.final_score) if a.final_score else None,
        },
    )

    nik, name, dept, _ = await _lookup_employee_info(session, a.employee_id)
    period_row = await session.execute(
        select(service.AssessmentPeriod).where(service.AssessmentPeriod.id == a.period_id)
    )
    period = period_row.scalar_one_or_none()
    return AssessmentOut(
        id=a.id,
        employee_id=a.employee_id,
        period_id=a.period_id,
        okr_score=a.okr_score,
        weighted_score=a.weighted_score,
        final_score=a.final_score,
        notes=a.notes,
        submitted_by_user_id=a.submitted_by_user_id,
        created_at=a.created_at,
        employee_nik=nik,
        employee_name=name,
        department_name=dept,
        period_label=service.period_label(period) if period else None,
        threshold_flag=service.derive_threshold_flag(a.final_score),
    )


# ─── SP Threshold + Warning Letter ────────────────────────────────


@router.get(
    "/assessment-threshold-check/{employee_id}",
    response_model=ThresholdCheckResponse,
)
async def threshold_check_endpoint(
    employee_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("sp.view")),
) -> ThresholdCheckResponse:
    """Cek apakah karyawan butuh SP berdasarkan 3 bulan terakhir."""
    nik, name, dept_name, dept_id = await _lookup_employee_info(session, employee_id)
    result = await service.check_employee_threshold(session, employee_id)
    return ThresholdCheckResponse(
        employee_id=employee_id,
        employee_nik=nik,
        employee_name=name,
        department_id=dept_id,
        department_name=dept_name,
        consecutive_low_months=result["consecutive_low_months"],
        threshold_score=result["threshold_score"],
        recent_scores=result["recent_scores"],
        suggested_sp_level=result["suggested_sp_level"],
        action_required=result["action_required"],
    )


@router.get("/warning-letters", response_model=list[WarningLetterOut])
async def list_warning_letters_endpoint(
    session: DBSession,
    _user=Depends(require_permission("sp.view")),
    employee_id: UUID | None = Query(None),
) -> list[WarningLetterOut]:
    letters = await service.list_warning_letters(session, employee_id)
    out: list[WarningLetterOut] = []
    for sp in letters:
        nik, name, _, _ = await _lookup_employee_info(session, sp.employee_id)
        out.append(
            WarningLetterOut(
                id=sp.id,
                employee_id=sp.employee_id,
                level=sp.level,
                issued_date=sp.issued_date,
                reason=sp.reason,
                document_url=sp.document_url,
                is_ai_drafted=sp.is_ai_drafted,
                acknowledged_at=sp.acknowledged_at,
                approved_by_user_id=sp.approved_by_user_id,
                created_at=sp.created_at,
                employee_nik=nik,
                employee_name=name,
            )
        )
    return out


@router.post(
    "/warning-letters",
    response_model=WarningLetterOut,
    status_code=status.HTTP_201_CREATED,
)
async def issue_warning_letter_endpoint(
    request: Request,
    data: WarningLetterCreate,
    session: DBSession,
    user=Depends(require_permission("sp.approve")),
) -> WarningLetterOut:
    try:
        sp = await service.issue_warning_letter(session, data, user.id)
    except InvalidAssessmentStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_SP", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action=f"WARNING_LETTER_{data.level}_ISSUED",
        resource_type="warning_letter",
        resource_id=str(sp.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "level": sp.level,
            "issued_date": str(sp.issued_date),
        },
    )

    nik, name, _, _ = await _lookup_employee_info(session, sp.employee_id)
    return WarningLetterOut(
        id=sp.id,
        employee_id=sp.employee_id,
        level=sp.level,
        issued_date=sp.issued_date,
        reason=sp.reason,
        document_url=sp.document_url,
        is_ai_drafted=sp.is_ai_drafted,
        acknowledged_at=sp.acknowledged_at,
        approved_by_user_id=sp.approved_by_user_id,
        created_at=sp.created_at,
        employee_nik=nik,
        employee_name=name,
    )
