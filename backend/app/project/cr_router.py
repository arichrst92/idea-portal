"""Change Request router — TSK-070.

Endpoints di /api/v1:
- GET    /projects/{id}/change-requests        — list CR per project
- POST   /projects/{id}/change-requests        — create (DRAFT)
- GET    /projects/change-requests/{id}        — detail
- PATCH  /projects/change-requests/{id}        — update (DRAFT only)
- POST   /projects/change-requests/{id}/submit — DRAFT → PENDING_L1
- POST   /projects/change-requests/{id}/approve-l1
- POST   /projects/change-requests/{id}/approve-l2
- POST   /projects/change-requests/{id}/reject
- POST   /projects/change-requests/{id}/cancel
- DELETE /projects/change-requests/{id}
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.core.audit import audit_log
from app.core.deps import DBSession, require_permission
from app.identity.models import User
from app.organization.models import Employee  # noqa: F401
from app.project import cr_service as service
from app.project.cr_schemas import (
    CRApprove,
    CRCreate,
    CROut,
    CRReject,
    CRUpdate,
)
from app.project.cr_service import (
    CRNotFoundError,
    CRStateError,
    SelfApprovalError,
)
from app.project.models import CRStatus, Project

router = APIRouter(tags=["project-change-request"])


async def _to_out(session, cr) -> CROut:
    # Lookups
    req_nik = None
    if cr.requester_user_id:
        r = await session.execute(select(User.nik).where(User.id == cr.requester_user_id))
        req_nik = r.scalar_one_or_none()
    l1_nik = None
    if cr.layer1_approver_id:
        r = await session.execute(select(User.nik).where(User.id == cr.layer1_approver_id))
        l1_nik = r.scalar_one_or_none()
    l2_nik = None
    if cr.layer2_approver_id:
        r = await session.execute(select(User.nik).where(User.id == cr.layer2_approver_id))
        l2_nik = r.scalar_one_or_none()

    proj_code = None
    if cr.project_id:
        r = await session.execute(select(Project.code).where(Project.id == cr.project_id))
        proj_code = r.scalar_one_or_none()

    return CROut(
        id=cr.id, project_id=cr.project_id, cr_number=cr.cr_number,
        title=cr.title, description=cr.description,
        impact_category=cr.impact_category,
        scope_delta=cr.scope_delta, timeline_delta_days=cr.timeline_delta_days,
        cost_delta=cr.cost_delta, currency=cr.currency,
        requester_user_id=cr.requester_user_id, status=cr.status,
        layer1_approver_id=cr.layer1_approver_id,
        layer1_approved_at=cr.layer1_approved_at, layer1_notes=cr.layer1_notes,
        layer2_approver_id=cr.layer2_approver_id,
        layer2_approved_at=cr.layer2_approved_at, layer2_notes=cr.layer2_notes,
        rejected_at=cr.rejected_at, rejection_reason=cr.rejection_reason,
        sales_notified_at=cr.sales_notified_at,
        finance_notified_at=cr.finance_notified_at,
        created_at=cr.created_at, updated_at=cr.updated_at,
        requester_nik=req_nik, layer1_approver_nik=l1_nik,
        layer2_approver_nik=l2_nik, project_code=proj_code,
    )


@router.get("/projects/{project_id}/change-requests", response_model=list[CROut])
async def list_crs_endpoint(
    project_id: UUID, session: DBSession,
    status_filter: CRStatus | None = Query(None, alias="status"),
    _user=Depends(require_permission("project.view")),
) -> list[CROut]:
    crs = await service.list_crs(session, project_id=project_id, status_filter=status_filter)
    return [await _to_out(session, c) for c in crs]


@router.post(
    "/projects/{project_id}/change-requests",
    response_model=CROut, status_code=status.HTTP_201_CREATED,
)
async def create_cr_endpoint(
    request: Request, project_id: UUID, data: CRCreate, session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> CROut:
    cr = await service.create_cr(session, project_id, data, user.id)
    await audit_log(
        session=session, actor=user, action="CR_CREATED",
        resource_type="project_change_request", resource_id=str(cr.id),
        ip_address=request.client.host if request.client else None,
        after_state={"cr_number": cr.cr_number, "title": cr.title},
    )
    return await _to_out(session, cr)


@router.get("/projects/change-requests/{cr_id}", response_model=CROut)
async def get_cr_endpoint(
    cr_id: UUID, session: DBSession,
    _user=Depends(require_permission("project.view")),
) -> CROut:
    try:
        cr = await service.get_cr(session, cr_id)
    except CRNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    return await _to_out(session, cr)


@router.patch("/projects/change-requests/{cr_id}", response_model=CROut)
async def update_cr_endpoint(
    request: Request, cr_id: UUID, data: CRUpdate, session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> CROut:
    try:
        cr = await service.update_cr(session, cr_id, data)
    except CRNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except CRStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="CR_UPDATED",
        resource_type="project_change_request", resource_id=str(cr.id),
        ip_address=request.client.host if request.client else None,
        after_state=data.model_dump(exclude_unset=True, mode="json"),
    )
    return await _to_out(session, cr)


def _make_transition_endpoint(action: str, status_code: int = 200):
    """Helper factory — bukan dipakai, manual eksplisit per endpoint untuk audit."""
    pass


@router.post("/projects/change-requests/{cr_id}/submit", response_model=CROut)
async def submit_cr_endpoint(
    request: Request, cr_id: UUID, session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> CROut:
    try:
        cr = await service.submit_cr(session, cr_id)
    except CRNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except CRStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="CR_SUBMITTED",
        resource_type="project_change_request", resource_id=str(cr.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _to_out(session, cr)


@router.post("/projects/change-requests/{cr_id}/approve-l1", response_model=CROut)
async def approve_l1_endpoint(
    request: Request, cr_id: UUID, data: CRApprove, session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> CROut:
    try:
        cr = await service.approve_l1(session, cr_id, user.id, data)
    except CRNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except (CRStateError, SelfApprovalError) as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="CR_APPROVED_L1",
        resource_type="project_change_request", resource_id=str(cr.id),
        ip_address=request.client.host if request.client else None,
        after_state={"notes": data.notes},
    )
    return await _to_out(session, cr)


@router.post("/projects/change-requests/{cr_id}/approve-l2", response_model=CROut)
async def approve_l2_endpoint(
    request: Request, cr_id: UUID, data: CRApprove, session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> CROut:
    try:
        cr = await service.approve_l2(session, cr_id, user.id, data)
    except CRNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except (CRStateError, SelfApprovalError) as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="CR_APPROVED_L2",
        resource_type="project_change_request", resource_id=str(cr.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "notes": data.notes,
            "finance_notified": cr.finance_notified_at is not None,
            "sales_notified": cr.sales_notified_at is not None,
        },
    )
    return await _to_out(session, cr)


@router.post("/projects/change-requests/{cr_id}/reject", response_model=CROut)
async def reject_cr_endpoint(
    request: Request, cr_id: UUID, data: CRReject, session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> CROut:
    try:
        cr = await service.reject_cr(session, cr_id, user.id, data)
    except CRNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except (CRStateError, SelfApprovalError) as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="CR_REJECTED",
        resource_type="project_change_request", resource_id=str(cr.id),
        ip_address=request.client.host if request.client else None,
        after_state={"reason": data.rejection_reason},
    )
    return await _to_out(session, cr)


@router.post("/projects/change-requests/{cr_id}/cancel", response_model=CROut)
async def cancel_cr_endpoint(
    request: Request, cr_id: UUID, session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> CROut:
    try:
        cr = await service.cancel_cr(session, cr_id, user.id)
    except CRNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except CRStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="CR_CANCELLED",
        resource_type="project_change_request", resource_id=str(cr.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _to_out(session, cr)


@router.delete("/projects/change-requests/{cr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cr_endpoint(
    request: Request, cr_id: UUID, session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> None:
    try:
        await service.soft_delete_cr(session, cr_id)
    except CRNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="CR_DELETED",
        resource_type="project_change_request", resource_id=str(cr_id),
        ip_address=request.client.host if request.client else None,
    )
