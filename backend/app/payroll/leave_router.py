"""Leave router — TSK-019.

Endpoints di /api/v1:
- /leave-types                       — list, create
- /leave-balances?employee_id=...    — saldo per employee per year
- /leave-requests                    — list, create
- /leave-requests/{id}               — detail
- /leave-requests/{id}/approve-l1
- /leave-requests/{id}/approve-l2
- /leave-requests/{id}/reject
- /leave-requests/{id}/cancel
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.core.audit import audit_log
from app.core.deps import CurrentUser, DBSession, require_permission
from app.identity.models import User
from app.organization.models import Employee
from app.payroll import leave_service as service
from app.payroll.leave_schemas import (
    EmployeeBalanceSummary,
    LeaveBalanceOut,
    LeaveRequestApprove,
    LeaveRequestCreate,
    LeaveRequestListItem,
    LeaveRequestListResponse,
    LeaveRequestOut,
    LeaveRequestReject,
    LeaveTypeCreate,
    LeaveTypeOut,
)
from app.payroll.leave_service import (
    InsufficientBalanceError,
    InvalidLeaveStateError,
    LeaveRequestNotFoundError,
    LeaveTypeNotFoundError,
    SelfApprovalBlockedError,
)
from app.payroll.models import LeaveBalance, LeaveRequest, LeaveType

router = APIRouter(tags=["leave"])


# ─── Helpers ───────────────────────────────────────────────────────


async def _lookup_user_nik(session, user_id: UUID | None) -> str | None:
    if user_id is None:
        return None
    r = await session.execute(select(User.nik).where(User.id == user_id))
    return r.scalar_one_or_none()


async def _lookup_employee_info(session, employee_id: UUID) -> tuple[str | None, str | None]:
    row = await session.execute(
        select(Employee.full_name, User.nik)
        .join(User, Employee.user_id == User.id)
        .where(Employee.id == employee_id)
    )
    r = row.first()
    if r is None:
        return None, None
    return r[1], r[0]  # nik, name


async def _lookup_leave_type(session, type_id: UUID) -> tuple[str | None, str | None]:
    r = await session.execute(
        select(LeaveType.code, LeaveType.name).where(LeaveType.id == type_id)
    )
    row = r.first()
    if row is None:
        return None, None
    return row[0], row[1]


async def _build_request_out(session, req: LeaveRequest) -> LeaveRequestOut:
    nik, name = await _lookup_employee_info(session, req.employee_id)
    lt_code, lt_name = await _lookup_leave_type(session, req.leave_type_id)
    l1_nik = await _lookup_user_nik(session, req.layer1_approver_id)
    l2_nik = await _lookup_user_nik(session, req.layer2_approver_id)

    return LeaveRequestOut(
        id=req.id,
        employee_id=req.employee_id,
        leave_type_id=req.leave_type_id,
        start_date=req.start_date,
        end_date=req.end_date,
        days_count=req.days_count,
        reason=req.reason,
        status=req.status,
        layer1_approver_id=req.layer1_approver_id,
        layer1_approved_at=req.layer1_approved_at,
        layer1_notes=req.layer1_notes,
        layer2_approver_id=req.layer2_approver_id,
        layer2_approved_at=req.layer2_approved_at,
        layer2_notes=req.layer2_notes,
        rejected_by_user_id=req.rejected_by_user_id,
        rejected_at=req.rejected_at,
        rejection_reason=req.rejection_reason,
        cancelled_at=req.cancelled_at,
        created_at=req.created_at,
        updated_at=req.updated_at,
        employee_nik=nik,
        employee_name=name,
        leave_type_code=lt_code,
        leave_type_name=lt_name,
        layer1_approver_nik=l1_nik,
        layer2_approver_nik=l2_nik,
    )


async def _build_request_list_item(session, req: LeaveRequest) -> LeaveRequestListItem:
    nik, name = await _lookup_employee_info(session, req.employee_id)
    lt_code, lt_name = await _lookup_leave_type(session, req.leave_type_id)
    return LeaveRequestListItem(
        id=req.id,
        employee_id=req.employee_id,
        employee_nik=nik,
        employee_name=name,
        leave_type_code=lt_code,
        leave_type_name=lt_name,
        start_date=req.start_date,
        end_date=req.end_date,
        days_count=req.days_count,
        status=req.status,
        created_at=req.created_at,
    )


async def _build_balance_out(session, balance: LeaveBalance) -> LeaveBalanceOut:
    lt_code, lt_name = await _lookup_leave_type(session, balance.leave_type_id)
    remaining = service.compute_remaining(balance)
    return LeaveBalanceOut(
        id=balance.id,
        employee_id=balance.employee_id,
        leave_type_id=balance.leave_type_id,
        year=balance.year,
        allocated_days=balance.allocated_days,
        used_days=balance.used_days,
        carried_over_days=balance.carried_over_days,
        remaining_days=remaining,
        leave_type_code=lt_code,
        leave_type_name=lt_name,
    )


# ─── LeaveType endpoints ───────────────────────────────────────────


@router.get("/leave-types", response_model=list[LeaveTypeOut])
async def list_leave_types_endpoint(
    session: DBSession,
    _user=Depends(require_permission("leave.create")),
) -> list[LeaveTypeOut]:
    types = await service.list_leave_types(session)
    return [LeaveTypeOut.model_validate(t) for t in types]


@router.post(
    "/leave-types",
    response_model=LeaveTypeOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_leave_type_endpoint(
    request: Request,
    data: LeaveTypeCreate,
    session: DBSession,
    user=Depends(require_permission("leave.approve")),
) -> LeaveTypeOut:
    """Create leave type baru — HR/Executive only."""
    lt = LeaveType(**data.model_dump())
    session.add(lt)
    await session.commit()
    await session.refresh(lt)

    await audit_log(
        session=session,
        actor=user,
        action="LEAVE_TYPE_CREATED",
        resource_type="leave_type",
        resource_id=str(lt.id),
        ip_address=request.client.host if request.client else None,
        after_state=data.model_dump(),
    )
    return LeaveTypeOut.model_validate(lt)


# ─── LeaveBalance endpoints ────────────────────────────────────────


@router.get("/leave-balances", response_model=EmployeeBalanceSummary)
async def get_balances_endpoint(
    session: DBSession,
    employee_id: UUID = Query(..., description="Employee UUID"),
    year: int | None = Query(None, description="Default tahun ini"),
    _user=Depends(require_permission("leave.create")),
) -> EmployeeBalanceSummary:
    """Get semua leave balance untuk 1 employee. Auto-create kalau belum ada."""
    year = year or date.today().year
    # Auto-create balance untuk semua leave type
    balances = await service.ensure_all_balances(session, employee_id, year)

    nik, name = await _lookup_employee_info(session, employee_id)
    items = [await _build_balance_out(session, b) for b in balances]
    return EmployeeBalanceSummary(
        employee_id=employee_id,
        employee_nik=nik,
        employee_name=name,
        year=year,
        balances=items,
    )


# ─── LeaveRequest endpoints ────────────────────────────────────────


@router.get("/leave-requests", response_model=LeaveRequestListResponse)
async def list_requests_endpoint(
    session: DBSession,
    _user=Depends(require_permission("leave.create")),
    employee_id: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> LeaveRequestListResponse:
    reqs, total = await service.list_leave_requests(
        session, employee_id=employee_id, status_filter=status_filter, page=page, page_size=page_size
    )
    items = [await _build_request_list_item(session, r) for r in reqs]
    return LeaveRequestListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=service.calc_total_pages(total, page_size),
    )


@router.post(
    "/leave-requests",
    response_model=LeaveRequestOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_request_endpoint(
    request: Request,
    data: LeaveRequestCreate,
    session: DBSession,
    user=Depends(require_permission("leave.create")),
) -> LeaveRequestOut:
    try:
        req = await service.create_leave_request(session, data)
    except (LeaveTypeNotFoundError, InvalidLeaveStateError) as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_REQUEST", "message": str(e)},
        ) from e
    except InsufficientBalanceError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INSUFFICIENT_BALANCE", "message": str(e)},
        ) from e

    await audit_log(
        session=session,
        actor=user,
        action="LEAVE_REQUEST_CREATED",
        resource_type="leave_request",
        resource_id=str(req.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "employee_id": str(req.employee_id),
            "leave_type_id": str(req.leave_type_id),
            "period": f"{req.start_date} - {req.end_date}",
            "days": req.days_count,
        },
    )
    return await _build_request_out(session, req)


@router.get("/leave-requests/{req_id}", response_model=LeaveRequestOut)
async def get_request_endpoint(
    req_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("leave.create")),
) -> LeaveRequestOut:
    try:
        req = await service.get_leave_request(session, req_id)
    except LeaveRequestNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    return await _build_request_out(session, req)


@router.post("/leave-requests/{req_id}/approve-l1", response_model=LeaveRequestOut)
async def approve_l1_endpoint(
    request: Request,
    req_id: UUID,
    data: LeaveRequestApprove,
    session: DBSession,
    user=Depends(require_permission("leave.approve")),
) -> LeaveRequestOut:
    try:
        req = await service.approve_l1(session, req_id, user.id, data)
    except LeaveRequestNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except (InvalidLeaveStateError, SelfApprovalBlockedError) as e:
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_APPROVAL", "message": str(e)}
        ) from e

    await audit_log(
        session=session,
        actor=user,
        action="LEAVE_REQUEST_APPROVED_L1",
        resource_type="leave_request",
        resource_id=str(req.id),
        ip_address=request.client.host if request.client else None,
        after_state={"notes": data.notes},
    )
    return await _build_request_out(session, req)


@router.post("/leave-requests/{req_id}/approve-l2", response_model=LeaveRequestOut)
async def approve_l2_endpoint(
    request: Request,
    req_id: UUID,
    data: LeaveRequestApprove,
    session: DBSession,
    user=Depends(require_permission("leave.approve")),
) -> LeaveRequestOut:
    try:
        req = await service.approve_l2(session, req_id, user.id, data)
    except LeaveRequestNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except (InvalidLeaveStateError, SelfApprovalBlockedError) as e:
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_APPROVAL", "message": str(e)}
        ) from e
    except InsufficientBalanceError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INSUFFICIENT_BALANCE", "message": str(e)},
        ) from e

    await audit_log(
        session=session,
        actor=user,
        action="LEAVE_REQUEST_APPROVED_L2",
        resource_type="leave_request",
        resource_id=str(req.id),
        ip_address=request.client.host if request.client else None,
        after_state={"notes": data.notes},
    )
    return await _build_request_out(session, req)


@router.post("/leave-requests/{req_id}/reject", response_model=LeaveRequestOut)
async def reject_endpoint(
    request: Request,
    req_id: UUID,
    data: LeaveRequestReject,
    session: DBSession,
    user=Depends(require_permission("leave.approve")),
) -> LeaveRequestOut:
    try:
        req = await service.reject_request(session, req_id, user.id, data)
    except LeaveRequestNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidLeaveStateError as e:
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}
        ) from e

    await audit_log(
        session=session,
        actor=user,
        action="LEAVE_REQUEST_REJECTED",
        resource_type="leave_request",
        resource_id=str(req.id),
        ip_address=request.client.host if request.client else None,
        after_state={"rejection_reason": data.rejection_reason},
    )
    return await _build_request_out(session, req)


@router.post("/leave-requests/{req_id}/cancel", response_model=LeaveRequestOut)
async def cancel_endpoint(
    request: Request,
    req_id: UUID,
    session: DBSession,
    user=Depends(require_permission("leave.create")),
) -> LeaveRequestOut:
    """Cancel — siapa saja yang punya leave.create permission bisa cancel.

    Backend tidak validate ownership; bisa di-tightening kalau perlu.
    """
    try:
        req = await service.cancel_request(session, req_id, user.id)
    except LeaveRequestNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidLeaveStateError as e:
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}
        ) from e

    await audit_log(
        session=session,
        actor=user,
        action="LEAVE_REQUEST_CANCELLED",
        resource_type="leave_request",
        resource_id=str(req.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _build_request_out(session, req)
