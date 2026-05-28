"""Separation router — TSK-017.

Endpoints di /api/v1:
- /separations (list, create, get)
- /separations/{id}/submit (DRAFT → PENDING_L1)
- /separations/{id}/approve-l1
- /separations/{id}/approve-l2
- /separations/{id}/reject
- /separations/{id}/cancel
- /separations/{id}/execute
- /separations/{id}/exit-interview

RBAC:
- separation.view → semua authenticated (mungkin filter dept by GM+)
- separation.create → Manager+ (atau employee untuk self-RESIGNATION)
- separation.approve → GM/C-Level/Executive untuk L2 approval
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.core.audit import audit_log
from app.core.deps import CurrentUser, DBSession, require_permission
from app.identity.models import User
from app.organization.models import Department, Employee
from app.separation import service
from app.separation.models import EmployeeSeparation, SeparationStatus, SeparationType
from app.separation.schemas import (
    ExitInterviewRequest,
    SeparationApproveRequest,
    SeparationCancelRequest,
    SeparationCreate,
    SeparationListItem,
    SeparationListResponse,
    SeparationOut,
    SeparationRejectRequest,
)
from app.separation.service import (
    EmployeeNotFoundError,
    InvalidSeparationStateError,
    SelfApprovalBlockedError,
    SeparationNotFoundError,
)

router = APIRouter(tags=["separation"])


# Permission mapping — backwards-compatible dengan permission registry existing:
# - layoff.create   → create separation
# - layoff.approve  → approve L1/L2 + execute
# - (no separate view perm; use sp.view atau layoff.create)


async def _lookup_employee_info(session, employee_id: UUID) -> tuple[str | None, str | None, str | None]:
    """(nik, full_name, department_name) untuk derived fields."""
    row = await session.execute(
        select(Employee.full_name, User.nik, Department.name)
        .join(User, Employee.user_id == User.id)
        .outerjoin(Department, Employee.department_id == Department.id)
        .where(Employee.id == employee_id)
    )
    r = row.first()
    if r is None:
        return None, None, None
    return r[1], r[0], r[2]


async def _lookup_user_nik(session, user_id: UUID | None) -> str | None:
    if user_id is None:
        return None
    r = await session.execute(select(User.nik).where(User.id == user_id))
    return r.scalar_one_or_none()


async def _build_separation_out(session, sep: EmployeeSeparation) -> SeparationOut:
    nik, name, dept = await _lookup_employee_info(session, sep.employee_id)
    init_nik = await _lookup_user_nik(session, sep.initiated_by_user_id)
    l1_nik = await _lookup_user_nik(session, sep.approval_l1_user_id)
    l2_nik = await _lookup_user_nik(session, sep.approval_l2_user_id)

    return SeparationOut(
        id=sep.id,
        employee_id=sep.employee_id,
        separation_type=sep.separation_type,
        status=sep.status,
        reason=sep.reason,
        effective_date=sep.effective_date,
        notice_period_days=sep.notice_period_days,
        severance_amount=sep.severance_amount,
        currency=sep.currency,
        assets_to_return=sep.assets_to_return,
        related_warning_letter_id=sep.related_warning_letter_id,
        exit_interview_notes=sep.exit_interview_notes,
        exit_interview_completed_at=sep.exit_interview_completed_at,
        initiated_by_user_id=sep.initiated_by_user_id,
        approval_l1_user_id=sep.approval_l1_user_id,
        approval_l1_at=sep.approval_l1_at,
        approval_l1_notes=sep.approval_l1_notes,
        approval_l2_user_id=sep.approval_l2_user_id,
        approval_l2_at=sep.approval_l2_at,
        approval_l2_notes=sep.approval_l2_notes,
        rejected_by_user_id=sep.rejected_by_user_id,
        rejected_at=sep.rejected_at,
        rejection_reason=sep.rejection_reason,
        executed_by_user_id=sep.executed_by_user_id,
        executed_at=sep.executed_at,
        cancelled_at=sep.cancelled_at,
        cancellation_reason=sep.cancellation_reason,
        created_at=sep.created_at,
        updated_at=sep.updated_at,
        employee_nik=nik,
        employee_name=name,
        employee_department=dept,
        initiated_by_nik=init_nik,
        approval_l1_nik=l1_nik,
        approval_l2_nik=l2_nik,
    )


async def _build_separation_list_item(session, sep: EmployeeSeparation) -> SeparationListItem:
    nik, name, dept = await _lookup_employee_info(session, sep.employee_id)
    init_nik = await _lookup_user_nik(session, sep.initiated_by_user_id)
    return SeparationListItem(
        id=sep.id,
        employee_id=sep.employee_id,
        separation_type=sep.separation_type,
        status=sep.status,
        effective_date=sep.effective_date,
        created_at=sep.created_at,
        employee_nik=nik,
        employee_name=name,
        employee_department=dept,
        initiated_by_nik=init_nik,
    )


# ─── List + Create ─────────────────────────────────────────────────


@router.get("/separations", response_model=SeparationListResponse)
async def list_separations_endpoint(
    session: DBSession,
    _user=Depends(require_permission("layoff.create")),
    employee_id: UUID | None = Query(None),
    separation_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> SeparationListResponse:
    sep_type = SeparationType(separation_type) if separation_type else None
    status_enum = SeparationStatus(status_filter) if status_filter else None

    seps, total = await service.list_separations(
        session,
        employee_id=employee_id,
        separation_type=sep_type,
        status=status_enum,
        page=page,
        page_size=page_size,
    )

    items = [await _build_separation_list_item(session, s) for s in seps]
    return SeparationListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=service.calc_total_pages(total, page_size),
    )


@router.post("/separations", response_model=SeparationOut, status_code=status.HTTP_201_CREATED)
async def create_separation_endpoint(
    request: Request,
    data: SeparationCreate,
    session: DBSession,
    user=Depends(require_permission("layoff.create")),
) -> SeparationOut:
    try:
        sep = await service.create_separation(session, data, user.id)
    except EmployeeNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "EMPLOYEE_NOT_FOUND", "message": str(e)}) from e
    except InvalidSeparationStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="SEPARATION_CREATED",
        resource_type="employee_separation",
        resource_id=str(sep.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        after_state={
            "employee_id": str(data.employee_id),
            "separation_type": data.separation_type.value,
            "effective_date": str(data.effective_date),
        },
    )
    return await _build_separation_out(session, sep)


@router.get("/separations/{sep_id}", response_model=SeparationOut)
async def get_separation_endpoint(
    sep_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("layoff.create")),
) -> SeparationOut:
    try:
        sep = await service.get_separation(session, sep_id)
    except SeparationNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    return await _build_separation_out(session, sep)


# ─── Workflow actions ──────────────────────────────────────────────


@router.post("/separations/{sep_id}/submit", response_model=SeparationOut)
async def submit_endpoint(
    request: Request,
    sep_id: UUID,
    session: DBSession,
    user=Depends(require_permission("layoff.create")),
) -> SeparationOut:
    try:
        sep = await service.submit_for_approval(session, sep_id)
    except SeparationNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidSeparationStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="SEPARATION_SUBMITTED",
        resource_type="employee_separation",
        resource_id=str(sep.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _build_separation_out(session, sep)


@router.post("/separations/{sep_id}/approve-l1", response_model=SeparationOut)
async def approve_l1_endpoint(
    request: Request,
    sep_id: UUID,
    data: SeparationApproveRequest,
    session: DBSession,
    user=Depends(require_permission("layoff.approve")),
) -> SeparationOut:
    try:
        sep = await service.approve_l1(session, sep_id, user.id, data)
    except SeparationNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except (InvalidSeparationStateError, SelfApprovalBlockedError) as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_APPROVAL", "message": str(e)},
        ) from e

    await audit_log(
        session=session,
        actor=user,
        action="SEPARATION_APPROVED_L1",
        resource_type="employee_separation",
        resource_id=str(sep.id),
        ip_address=request.client.host if request.client else None,
        after_state={"notes": data.notes},
    )
    return await _build_separation_out(session, sep)


@router.post("/separations/{sep_id}/approve-l2", response_model=SeparationOut)
async def approve_l2_endpoint(
    request: Request,
    sep_id: UUID,
    data: SeparationApproveRequest,
    session: DBSession,
    user=Depends(require_permission("layoff.approve")),
) -> SeparationOut:
    try:
        sep = await service.approve_l2(session, sep_id, user.id, data)
    except SeparationNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except (InvalidSeparationStateError, SelfApprovalBlockedError) as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_APPROVAL", "message": str(e)},
        ) from e

    await audit_log(
        session=session,
        actor=user,
        action="SEPARATION_APPROVED_L2",
        resource_type="employee_separation",
        resource_id=str(sep.id),
        ip_address=request.client.host if request.client else None,
        after_state={"notes": data.notes},
    )
    return await _build_separation_out(session, sep)


@router.post("/separations/{sep_id}/reject", response_model=SeparationOut)
async def reject_endpoint(
    request: Request,
    sep_id: UUID,
    data: SeparationRejectRequest,
    session: DBSession,
    user=Depends(require_permission("layoff.approve")),
) -> SeparationOut:
    try:
        sep = await service.reject_separation(session, sep_id, user.id, data)
    except SeparationNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidSeparationStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="SEPARATION_REJECTED",
        resource_type="employee_separation",
        resource_id=str(sep.id),
        ip_address=request.client.host if request.client else None,
        after_state={"rejection_reason": data.rejection_reason},
    )
    return await _build_separation_out(session, sep)


@router.post("/separations/{sep_id}/cancel", response_model=SeparationOut)
async def cancel_endpoint(
    request: Request,
    sep_id: UUID,
    data: SeparationCancelRequest,
    session: DBSession,
    user=Depends(require_permission("layoff.create")),
) -> SeparationOut:
    try:
        sep = await service.cancel_separation(session, sep_id, user.id, data)
    except SeparationNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidSeparationStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="SEPARATION_CANCELLED",
        resource_type="employee_separation",
        resource_id=str(sep.id),
        ip_address=request.client.host if request.client else None,
        after_state={"cancellation_reason": data.cancellation_reason},
    )
    return await _build_separation_out(session, sep)


@router.post("/separations/{sep_id}/execute", response_model=SeparationOut)
async def execute_endpoint(
    request: Request,
    sep_id: UUID,
    session: DBSession,
    user=Depends(require_permission("layoff.approve")),
) -> SeparationOut:
    """Eksekusi separation yang sudah APPROVED. Update employee + soft delete."""
    try:
        sep, emp = await service.execute_separation(session, sep_id, user.id)
    except SeparationNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except (InvalidSeparationStateError, EmployeeNotFoundError) as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_EXECUTE", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="SEPARATION_EXECUTED",
        resource_type="employee_separation",
        resource_id=str(sep.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "employee_id": str(emp.id),
            "new_employee_status": str(emp.status),
            "last_working_day": str(emp.last_working_day),
        },
    )
    return await _build_separation_out(session, sep)


@router.post("/separations/{sep_id}/exit-interview", response_model=SeparationOut)
async def record_exit_interview_endpoint(
    request: Request,
    sep_id: UUID,
    data: ExitInterviewRequest,
    session: DBSession,
    user=Depends(require_permission("layoff.create")),
) -> SeparationOut:
    try:
        sep = await service.record_exit_interview(session, sep_id, data)
    except SeparationNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidSeparationStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="SEPARATION_EXIT_INTERVIEW_RECORDED",
        resource_type="employee_separation",
        resource_id=str(sep.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _build_separation_out(session, sep)
