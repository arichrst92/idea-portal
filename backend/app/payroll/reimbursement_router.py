"""Reimbursement + Procurement router — TSK-023.

Endpoints di /api/v1:
- /vendors                       — list, create
- /reimbursements                — list, create, get
- /reimbursements/{id}/approve-l1, /approve-l2, /reject, /cancel, /transfer
- /procurements                  — list, create, get
- /procurements/{id}/approve-l1, /approve-l2, /reject, /cancel, /order, /deliver
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.core.audit import audit_log
from app.core.deps import CurrentUser, DBSession, require_permission
from app.identity.models import User
from app.organization.models import Employee
from app.payroll import reimbursement_service as service
from app.payroll.models import Vendor
from app.payroll.reimbursement_schemas import (
    ProcurementCreate,
    ProcurementDeliver,
    ProcurementListItem,
    ProcurementListResponse,
    ProcurementOrder,
    ProcurementOut,
    ReimbursementApprove,
    ReimbursementCreate,
    ReimbursementListItem,
    ReimbursementListResponse,
    ReimbursementOut,
    ReimbursementReject,
    ReimbursementTransfer,
    VendorCreate,
    VendorOut,
)
from app.payroll.reimbursement_service import (
    DuplicateVendorCodeError,
    InvalidStateError,
    ProcurementNotFoundError,
    ReimbursementNotFoundError,
    SelfApprovalBlockedError,
    VendorNotFoundError,
)

router = APIRouter(tags=["reimbursement_procurement"])


# ─── Helpers ───────────────────────────────────────────────────────


async def _lookup_user_nik(session, user_id: UUID | None) -> str | None:
    if user_id is None:
        return None
    r = await session.execute(select(User.nik).where(User.id == user_id))
    return r.scalar_one_or_none()


async def _lookup_employee_info(session, employee_id: UUID) -> tuple[str | None, str | None]:
    r = await session.execute(
        select(Employee.full_name, User.nik)
        .join(User, Employee.user_id == User.id)
        .where(Employee.id == employee_id)
    )
    row = r.first()
    if row is None:
        return None, None
    return row[1], row[0]


async def _lookup_project_name(session, project_id: UUID | None) -> str | None:
    if project_id is None:
        return None
    from app.project.models import Project

    r = await session.execute(select(Project.name).where(Project.id == project_id))
    return r.scalar_one_or_none()


async def _lookup_vendor(session, vendor_id: UUID | None) -> tuple[str | None, str | None]:
    if vendor_id is None:
        return None, None
    r = await session.execute(
        select(Vendor.code, Vendor.name).where(Vendor.id == vendor_id)
    )
    row = r.first()
    if row is None:
        return None, None
    return row[0], row[1]


async def _build_reimb_out(session, r) -> ReimbursementOut:
    nik, name = await _lookup_employee_info(session, r.employee_id)
    project_name = await _lookup_project_name(session, r.project_id)
    l1_nik = await _lookup_user_nik(session, r.layer1_approver_id)
    l2_nik = await _lookup_user_nik(session, r.layer2_approver_id)
    return ReimbursementOut(
        id=r.id,
        employee_id=r.employee_id,
        request_date=r.request_date,
        category=r.category,
        amount=r.amount,
        currency=r.currency,
        description=r.description,
        receipt_url=r.receipt_url,
        project_id=r.project_id,
        status=r.status,
        layer1_approver_id=r.layer1_approver_id,
        layer1_approved_at=r.layer1_approved_at,
        layer1_notes=r.layer1_notes,
        layer2_approver_id=r.layer2_approver_id,
        layer2_approved_at=r.layer2_approved_at,
        layer2_notes=r.layer2_notes,
        rejected_by_user_id=r.rejected_by_user_id,
        rejected_at=r.rejected_at,
        rejection_reason=r.rejection_reason,
        cancelled_at=r.cancelled_at,
        transferred_at=r.transferred_at,
        transferred_by_user_id=r.transferred_by_user_id,
        transfer_reference=r.transfer_reference,
        created_at=r.created_at,
        updated_at=r.updated_at,
        employee_nik=nik,
        employee_name=name,
        project_name=project_name,
        layer1_approver_nik=l1_nik,
        layer2_approver_nik=l2_nik,
    )


async def _build_reimb_list(session, r) -> ReimbursementListItem:
    nik, name = await _lookup_employee_info(session, r.employee_id)
    project_name = await _lookup_project_name(session, r.project_id)
    return ReimbursementListItem(
        id=r.id,
        employee_id=r.employee_id,
        employee_nik=nik,
        employee_name=name,
        request_date=r.request_date,
        category=r.category,
        amount=r.amount,
        currency=r.currency,
        status=r.status,
        transferred_at=r.transferred_at,
        project_name=project_name,
        created_at=r.created_at,
    )


async def _build_proc_out(session, p) -> ProcurementOut:
    req_nik = await _lookup_user_nik(session, p.requested_by_user_id)
    v_code, v_name = await _lookup_vendor(session, p.vendor_id)
    return ProcurementOut(
        id=p.id,
        requested_by_user_id=p.requested_by_user_id,
        request_date=p.request_date,
        item_description=p.item_description,
        item_category=p.item_category,
        quantity=p.quantity,
        estimated_amount=p.estimated_amount,
        actual_amount=p.actual_amount,
        currency=p.currency,
        vendor_id=p.vendor_id,
        is_asset=p.is_asset,
        expected_delivery_date=p.expected_delivery_date,
        actual_delivery_date=p.actual_delivery_date,
        notes=p.notes,
        status=p.status,
        layer1_approver_id=p.layer1_approver_id,
        layer1_approved_at=p.layer1_approved_at,
        layer1_notes=p.layer1_notes,
        layer2_approver_id=p.layer2_approver_id,
        layer2_approved_at=p.layer2_approved_at,
        layer2_notes=p.layer2_notes,
        rejected_by_user_id=p.rejected_by_user_id,
        rejected_at=p.rejected_at,
        rejection_reason=p.rejection_reason,
        cancelled_at=p.cancelled_at,
        po_number=p.po_number,
        ordered_at=p.ordered_at,
        created_at=p.created_at,
        updated_at=p.updated_at,
        requested_by_nik=req_nik,
        vendor_code=v_code,
        vendor_name=v_name,
    )


async def _build_proc_list(session, p) -> ProcurementListItem:
    req_nik = await _lookup_user_nik(session, p.requested_by_user_id)
    _, v_name = await _lookup_vendor(session, p.vendor_id)
    return ProcurementListItem(
        id=p.id,
        requested_by_nik=req_nik,
        item_description=p.item_description,
        item_category=p.item_category,
        quantity=p.quantity,
        estimated_amount=p.estimated_amount,
        actual_amount=p.actual_amount,
        currency=p.currency,
        vendor_name=v_name,
        status=p.status,
        is_asset=p.is_asset,
        expected_delivery_date=p.expected_delivery_date,
        actual_delivery_date=p.actual_delivery_date,
        created_at=p.created_at,
    )


# ─── Vendor endpoints ──────────────────────────────────────────────


@router.get("/vendors", response_model=list[VendorOut])
async def list_vendors_endpoint(
    session: DBSession,
    _user=Depends(require_permission("reimbursement.create")),
) -> list[VendorOut]:
    vendors = await service.list_vendors(session)
    return [VendorOut.model_validate(v) for v in vendors]


@router.post(
    "/vendors", response_model=VendorOut, status_code=status.HTTP_201_CREATED
)
async def create_vendor_endpoint(
    request: Request,
    data: VendorCreate,
    session: DBSession,
    user=Depends(require_permission("procurement.create")),
) -> VendorOut:
    try:
        vendor = await service.create_vendor(session, data)
    except DuplicateVendorCodeError as e:
        raise HTTPException(status_code=409, detail={"code": "DUPLICATE", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="VENDOR_CREATED",
        resource_type="vendor",
        resource_id=str(vendor.id),
        ip_address=request.client.host if request.client else None,
    )
    return VendorOut.model_validate(vendor)


# ─── Reimbursement endpoints ──────────────────────────────────────


@router.get("/reimbursements", response_model=ReimbursementListResponse)
async def list_reimbursements_endpoint(
    session: DBSession,
    _user=Depends(require_permission("reimbursement.create")),
    employee_id: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    category: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> ReimbursementListResponse:
    items, total = await service.list_reimbursements(
        session, employee_id=employee_id, status_filter=status_filter,
        category=category, page=page, page_size=page_size,
    )
    out = [await _build_reimb_list(session, r) for r in items]
    return ReimbursementListResponse(
        items=out, total=total, page=page, page_size=page_size,
        total_pages=service.calc_total_pages(total, page_size),
    )


@router.post(
    "/reimbursements",
    response_model=ReimbursementOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_reimbursement_endpoint(
    request: Request,
    data: ReimbursementCreate,
    session: DBSession,
    user=Depends(require_permission("reimbursement.create")),
) -> ReimbursementOut:
    try:
        r = await service.create_reimbursement(session, data)
    except InvalidStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="REIMBURSEMENT_CREATED",
        resource_type="reimbursement", resource_id=str(r.id),
        ip_address=request.client.host if request.client else None,
        after_state={"amount": float(r.amount), "category": r.category},
    )
    return await _build_reimb_out(session, r)


@router.get("/reimbursements/{reimb_id}", response_model=ReimbursementOut)
async def get_reimbursement_endpoint(
    reimb_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("reimbursement.create")),
) -> ReimbursementOut:
    try:
        r = await service.get_reimbursement(session, reimb_id)
    except ReimbursementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    return await _build_reimb_out(session, r)


@router.post("/reimbursements/{reimb_id}/approve-l1", response_model=ReimbursementOut)
async def approve_reimb_l1_endpoint(
    request: Request, reimb_id: UUID, data: ReimbursementApprove,
    session: DBSession,
    user=Depends(require_permission("reimbursement.approve")),
) -> ReimbursementOut:
    try:
        r = await service.approve_reimbursement_l1(session, reimb_id, user.id, data)
    except ReimbursementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except (InvalidStateError, SelfApprovalBlockedError) as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="REIMBURSEMENT_APPROVED_L1",
        resource_type="reimbursement", resource_id=str(r.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _build_reimb_out(session, r)


@router.post("/reimbursements/{reimb_id}/approve-l2", response_model=ReimbursementOut)
async def approve_reimb_l2_endpoint(
    request: Request, reimb_id: UUID, data: ReimbursementApprove,
    session: DBSession,
    user=Depends(require_permission("reimbursement.approve")),
) -> ReimbursementOut:
    try:
        r = await service.approve_reimbursement_l2(session, reimb_id, user.id, data)
    except ReimbursementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except (InvalidStateError, SelfApprovalBlockedError) as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="REIMBURSEMENT_APPROVED_L2",
        resource_type="reimbursement", resource_id=str(r.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _build_reimb_out(session, r)


@router.post("/reimbursements/{reimb_id}/reject", response_model=ReimbursementOut)
async def reject_reimb_endpoint(
    request: Request, reimb_id: UUID, data: ReimbursementReject,
    session: DBSession,
    user=Depends(require_permission("reimbursement.approve")),
) -> ReimbursementOut:
    try:
        r = await service.reject_reimbursement(session, reimb_id, user.id, data)
    except ReimbursementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="REIMBURSEMENT_REJECTED",
        resource_type="reimbursement", resource_id=str(r.id),
        ip_address=request.client.host if request.client else None,
        after_state={"reason": data.rejection_reason},
    )
    return await _build_reimb_out(session, r)


@router.post("/reimbursements/{reimb_id}/cancel", response_model=ReimbursementOut)
async def cancel_reimb_endpoint(
    request: Request, reimb_id: UUID,
    session: DBSession,
    user=Depends(require_permission("reimbursement.create")),
) -> ReimbursementOut:
    try:
        r = await service.cancel_reimbursement(session, reimb_id)
    except ReimbursementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="REIMBURSEMENT_CANCELLED",
        resource_type="reimbursement", resource_id=str(r.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _build_reimb_out(session, r)


@router.post("/reimbursements/{reimb_id}/transfer", response_model=ReimbursementOut)
async def transfer_reimb_endpoint(
    request: Request, reimb_id: UUID, data: ReimbursementTransfer,
    session: DBSession,
    user=Depends(require_permission("reimbursement.approve")),  # Finance
) -> ReimbursementOut:
    try:
        r = await service.mark_transferred(session, reimb_id, user.id, data)
    except ReimbursementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="REIMBURSEMENT_TRANSFERRED",
        resource_type="reimbursement", resource_id=str(r.id),
        ip_address=request.client.host if request.client else None,
        after_state={"transfer_reference": data.transfer_reference},
    )
    return await _build_reimb_out(session, r)


# ─── Procurement endpoints ─────────────────────────────────────────


@router.get("/procurements", response_model=ProcurementListResponse)
async def list_procurements_endpoint(
    session: DBSession,
    _user=Depends(require_permission("procurement.create")),
    requested_by_user_id: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    category: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> ProcurementListResponse:
    items, total = await service.list_procurements(
        session, requested_by_user_id=requested_by_user_id, status_filter=status_filter,
        category=category, page=page, page_size=page_size,
    )
    out = [await _build_proc_list(session, p) for p in items]
    return ProcurementListResponse(
        items=out, total=total, page=page, page_size=page_size,
        total_pages=service.calc_total_pages(total, page_size),
    )


@router.post(
    "/procurements", response_model=ProcurementOut, status_code=status.HTTP_201_CREATED,
)
async def create_procurement_endpoint(
    request: Request, data: ProcurementCreate, session: DBSession,
    user=Depends(require_permission("procurement.create")),
) -> ProcurementOut:
    p = await service.create_procurement(session, data, user.id)
    await audit_log(
        session=session, actor=user, action="PROCUREMENT_CREATED",
        resource_type="procurement", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "category": p.item_category,
            "estimated": float(p.estimated_amount) if p.estimated_amount else None,
        },
    )
    return await _build_proc_out(session, p)


@router.get("/procurements/{proc_id}", response_model=ProcurementOut)
async def get_procurement_endpoint(
    proc_id: UUID, session: DBSession,
    _user=Depends(require_permission("procurement.create")),
) -> ProcurementOut:
    try:
        p = await service.get_procurement(session, proc_id)
    except ProcurementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    return await _build_proc_out(session, p)


@router.post("/procurements/{proc_id}/approve-l1", response_model=ProcurementOut)
async def approve_proc_l1_endpoint(
    request: Request, proc_id: UUID, data: ReimbursementApprove, session: DBSession,
    user=Depends(require_permission("procurement.approve")),
) -> ProcurementOut:
    try:
        p = await service.approve_procurement_l1(session, proc_id, user.id, data)
    except ProcurementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except (InvalidStateError, SelfApprovalBlockedError) as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="PROCUREMENT_APPROVED_L1",
        resource_type="procurement", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _build_proc_out(session, p)


@router.post("/procurements/{proc_id}/approve-l2", response_model=ProcurementOut)
async def approve_proc_l2_endpoint(
    request: Request, proc_id: UUID, data: ReimbursementApprove, session: DBSession,
    user=Depends(require_permission("procurement.approve")),
) -> ProcurementOut:
    try:
        p = await service.approve_procurement_l2(session, proc_id, user.id, data)
    except ProcurementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except (InvalidStateError, SelfApprovalBlockedError) as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="PROCUREMENT_APPROVED_L2",
        resource_type="procurement", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _build_proc_out(session, p)


@router.post("/procurements/{proc_id}/reject", response_model=ProcurementOut)
async def reject_proc_endpoint(
    request: Request, proc_id: UUID, data: ReimbursementReject, session: DBSession,
    user=Depends(require_permission("procurement.approve")),
) -> ProcurementOut:
    try:
        p = await service.reject_procurement(session, proc_id, user.id, data)
    except ProcurementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="PROCUREMENT_REJECTED",
        resource_type="procurement", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
        after_state={"reason": data.rejection_reason},
    )
    return await _build_proc_out(session, p)


@router.post("/procurements/{proc_id}/cancel", response_model=ProcurementOut)
async def cancel_proc_endpoint(
    request: Request, proc_id: UUID, session: DBSession,
    user=Depends(require_permission("procurement.create")),
) -> ProcurementOut:
    try:
        p = await service.cancel_procurement(session, proc_id)
    except ProcurementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="PROCUREMENT_CANCELLED",
        resource_type="procurement", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _build_proc_out(session, p)


@router.post("/procurements/{proc_id}/order", response_model=ProcurementOut)
async def order_proc_endpoint(
    request: Request, proc_id: UUID, data: ProcurementOrder, session: DBSession,
    user=Depends(require_permission("procurement.approve")),
) -> ProcurementOut:
    try:
        p = await service.order_procurement(session, proc_id, data)
    except ProcurementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="PROCUREMENT_ORDERED",
        resource_type="procurement", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
        after_state={"po_number": data.po_number},
    )
    return await _build_proc_out(session, p)


@router.post("/procurements/{proc_id}/deliver", response_model=ProcurementOut)
async def deliver_proc_endpoint(
    request: Request, proc_id: UUID, data: ProcurementDeliver, session: DBSession,
    user=Depends(require_permission("procurement.approve")),
) -> ProcurementOut:
    try:
        p = await service.deliver_procurement(session, proc_id, data)
    except ProcurementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="PROCUREMENT_DELIVERED",
        resource_type="procurement", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
        after_state={"delivery_date": str(data.actual_delivery_date)},
    )
    return await _build_proc_out(session, p)
