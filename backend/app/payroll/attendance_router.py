"""Attendance router — TSK-047.

Endpoints:
- GET    /api/v1/payroll/periods/{period_id}/attendance               — list + completeness
- POST   /api/v1/payroll/periods/{period_id}/attendance               — bulk upsert
- GET    /api/v1/payroll/periods/{period_id}/attendance/completeness  — cheap progress check
- PATCH  /api/v1/payroll/attendance/{att_id}                          — single update

Permission: payroll.edit (Operation role).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import DBSession, get_current_user, require_permission
from app.identity.models import User
from app.organization.models import Department, Employee, EmployeeStatus
from app.payroll import attendance_service as service
from app.payroll.attendance_schemas import (
    AttendanceBulkUpsert,
    AttendanceCompletenessResponse,
    AttendanceListResponse,
    AttendanceOut,
    AttendanceUpdate,
)
from app.payroll.attendance_service import (
    AttendanceNotFoundError,
    ExceedsWorkingDaysError,
    PeriodLockedError,
    PeriodNotFoundError,
)

router = APIRouter(prefix="/payroll", tags=["payroll-attendance"])


def _make_out(
    att, emp: Employee | None, dept_name: str | None = None
) -> AttendanceOut:
    out = AttendanceOut.model_validate(att)
    if emp is not None:
        # Resolve NIK via Employee.user_id → User (Employee has no nik column per ERD)
        out.employee_name = emp.full_name
        out.department_name = dept_name
    return out


# ─── Static routes BEFORE dynamic (NC-DEV-002) ────────────────────────


@router.get(
    "/periods/{period_id}/attendance/completeness",
    response_model=AttendanceCompletenessResponse,
)
async def get_completeness(
    period_id: UUID,
    session: DBSession,
    _: Annotated[User, Depends(require_permission("payroll.view"))],
) -> AttendanceCompletenessResponse:
    """Cheap completeness check — count submitted vs total active employees."""
    try:
        period, working_days, total_active, submitted, missing = await service.completeness(
            session, period_id
        )
    except PeriodNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": str(e)},
        ) from e

    return AttendanceCompletenessResponse(
        period_id=period.id,
        calendar_working_days=working_days,
        total_active_employees=total_active,
        submitted_count=submitted,
        missing_count=total_active - submitted,
        missing_employee_ids=missing,
    )


@router.get(
    "/periods/{period_id}/attendance",
    response_model=AttendanceListResponse,
)
async def list_attendance(
    period_id: UUID,
    session: DBSession,
    _: Annotated[User, Depends(require_permission("payroll.view"))],
) -> AttendanceListResponse:
    """List all attendance rows untuk periode + completeness metadata."""
    try:
        period, paired, working_days, total_active = await service.list_for_period(
            session, period_id
        )
    except PeriodNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": str(e)},
        ) from e

    # Fetch department names in bulk
    dept_ids = {emp.department_id for _, emp in paired if emp.department_id}
    dept_map: dict[UUID, str] = {}
    if dept_ids:
        dept_stmt = select(Department).where(Department.id.in_(dept_ids))
        for d in (await session.execute(dept_stmt)).scalars().all():
            dept_map[d.id] = d.name

    # Fetch NIK from User join
    from app.identity.models import User as UserModel
    user_ids = {emp.user_id for _, emp in paired if emp.user_id}
    nik_map: dict[UUID, str] = {}
    if user_ids:
        user_stmt = select(UserModel.id, UserModel.nik).where(UserModel.id.in_(user_ids))
        for uid, nik in (await session.execute(user_stmt)).all():
            nik_map[uid] = nik

    items: list[AttendanceOut] = []
    for att, emp in paired:
        out = _make_out(att, emp, dept_map.get(emp.department_id) if emp.department_id else None)
        out.employee_nik = nik_map.get(emp.user_id) if emp.user_id else None
        items.append(out)

    return AttendanceListResponse(
        period_id=period.id,
        period_year=period.year,
        period_month=period.month,
        period_status=period.status,
        calendar_working_days=working_days,
        total_active_employees=total_active,
        submitted_count=len(items),
        missing_count=total_active - len(items),
        items=items,
    )


@router.post(
    "/periods/{period_id}/attendance",
    response_model=list[AttendanceOut],
    status_code=status.HTTP_201_CREATED,
)
async def bulk_upsert_attendance(
    period_id: UUID,
    data: AttendanceBulkUpsert,
    session: DBSession,
    current_user: Annotated[User, Depends(require_permission("payroll.edit"))],
) -> list[AttendanceOut]:
    """Bulk upsert attendance untuk 1 periode (Operation submit massal).

    - Period harus DRAFT (NC-OP-008-02)
    - Setiap row days_present + absent_paid + absent_unpaid ≤ calendar_working_days (NC-OP-007-01)
    - overtime_hours ≥ 0 (NC-OP-007-05, juga via Pydantic Field)
    """
    if data.period_id != period_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "period_id di path tidak match dengan body"},
        )

    try:
        rows = await service.bulk_upsert(session, data, current_user.id)
    except PeriodNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": str(e)},
        ) from e
    except PeriodLockedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(e)},
        ) from e
    except ExceedsWorkingDaysError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(e)},
        ) from e

    return [AttendanceOut.model_validate(r) for r in rows]


@router.patch(
    "/attendance/{att_id}",
    response_model=AttendanceOut,
)
async def update_single_attendance(
    att_id: UUID,
    data: AttendanceUpdate,
    session: DBSession,
    current_user: Annotated[User, Depends(require_permission("payroll.edit"))],
) -> AttendanceOut:
    """Update single attendance record."""
    try:
        att = await service.update_attendance(session, att_id, data, current_user.id)
    except AttendanceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": str(e)},
        ) from e
    except PeriodLockedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(e)},
        ) from e
    except ExceedsWorkingDaysError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(e)},
        ) from e

    return AttendanceOut.model_validate(att)
