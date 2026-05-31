"""Reimbursement + Procurement business logic — TSK-023.

Reimbursement workflow:
PENDING_L1 → PENDING_L2 → APPROVED → TRANSFERRED
                       → REJECTED / CANCELLED

Procurement workflow:
PENDING_L1 → PENDING_L2 → APPROVED → ORDERED → DELIVERED
                       → REJECTED / CANCELLED

Both: 2-layer approval (supervisor → GM/Finance), self-approval blocked.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.notification.approver_chain import (
    find_l1_l2_approver_user_ids,
    find_l1_l2_approver_user_ids_by_user,
    get_employee_display_name,
    get_requester_user_id,
    get_user_display_name,
)
from app.notification.models import NotificationType
from app.notification.templates import notify_from_template
from app.organization.models import Employee
from app.payroll.models import ProcurementRequest, Reimbursement, Vendor
from app.payroll.reimbursement_schemas import (
    ProcurementCreate,
    ProcurementDeliver,
    ProcurementOrder,
    ReimbursementApprove,
    ReimbursementCreate,
    ReimbursementReject,
    ReimbursementTransfer,
    VendorCreate,
)


# ─── Exceptions ────────────────────────────────────────────────────


class ReimbursementNotFoundError(Exception):
    pass


class ProcurementNotFoundError(Exception):
    pass


class VendorNotFoundError(Exception):
    pass


class InvalidStateError(Exception):
    pass


class SelfApprovalBlockedError(Exception):
    pass


class DuplicateVendorCodeError(Exception):
    pass


# ─── Vendor CRUD ───────────────────────────────────────────────────


async def list_vendors(session: AsyncSession) -> list[Vendor]:
    stmt = select(Vendor).where(Vendor.deleted_at.is_(None)).order_by(Vendor.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_vendor(session: AsyncSession, data: VendorCreate) -> Vendor:
    vendor = Vendor(**data.model_dump())
    session.add(vendor)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        if "vendors_code_key" in str(e):
            raise DuplicateVendorCodeError(f"Vendor code '{data.code}' sudah ada") from e
        raise
    await session.refresh(vendor)
    return vendor


# ─── Reimbursement CRUD ────────────────────────────────────────────


async def get_reimbursement(session: AsyncSession, reimb_id: UUID) -> Reimbursement:
    stmt = select(Reimbursement).where(Reimbursement.id == reimb_id)
    result = await session.execute(stmt)
    r = result.scalar_one_or_none()
    if r is None:
        raise ReimbursementNotFoundError(f"Reimbursement {reimb_id} not found")
    return r


async def list_reimbursements(
    session: AsyncSession,
    employee_id: UUID | None = None,
    status_filter: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Reimbursement], int]:
    page = max(page, 1)
    page_size = max(min(page_size, 200), 1)

    base = select(Reimbursement)
    if employee_id is not None:
        base = base.where(Reimbursement.employee_id == employee_id)
    if status_filter is not None:
        base = base.where(Reimbursement.status == status_filter)
    if category is not None:
        base = base.where(Reimbursement.category == category)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    stmt = (
        base.order_by(Reimbursement.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def create_reimbursement(
    session: AsyncSession, data: ReimbursementCreate
) -> Reimbursement:
    # Validate employee
    emp_result = await session.execute(
        select(Employee).where(Employee.id == data.employee_id, Employee.deleted_at.is_(None))
    )
    if emp_result.scalar_one_or_none() is None:
        raise InvalidStateError(f"Employee {data.employee_id} not found")

    r = Reimbursement(
        employee_id=data.employee_id,
        request_date=data.request_date,
        category=data.category,
        amount=data.amount,
        currency=data.currency,
        description=data.description,
        receipt_url=data.receipt_url,
        project_id=data.project_id,
        status="PENDING_L1",
    )
    session.add(r)
    await session.commit()
    await session.refresh(r)

    # TSK-060 — notify L1 approver
    l1_user_id, _ = await find_l1_l2_approver_user_ids(session, data.employee_id)
    if l1_user_id:
        requester_name = await get_employee_display_name(session, data.employee_id)
        await notify_from_template(
            session,
            user_id=l1_user_id,
            type=NotificationType.PROCUREMENT_PENDING,
            context={
                "kind": "Reimbursement",
                "requester_name": requester_name,
                "amount_idr": f"{int(data.amount):,}".replace(",", "."),
                "purpose": data.description or data.category,
                "request_id": str(r.id),
                "tab": "reimbursement",
            },
        )
        await session.commit()
    return r


async def approve_reimbursement_l1(
    session: AsyncSession,
    reimb_id: UUID,
    approver_user_id: UUID,
    data: ReimbursementApprove,
) -> Reimbursement:
    r = await get_reimbursement(session, reimb_id)
    if r.status != "PENDING_L1":
        raise InvalidStateError(f"Status {r.status} — bukan PENDING_L1")

    emp_result = await session.execute(select(Employee).where(Employee.id == r.employee_id))
    emp = emp_result.scalar_one_or_none()
    if emp and emp.user_id == approver_user_id:
        raise SelfApprovalBlockedError("Tidak boleh approve request sendiri")

    r.layer1_approver_id = approver_user_id
    r.layer1_approved_at = datetime.now(UTC)
    r.layer1_notes = data.notes
    r.status = "PENDING_L2"
    await session.commit()
    await session.refresh(r)

    # TSK-060 — notify L2
    _, l2_user_id = await find_l1_l2_approver_user_ids(session, r.employee_id)
    if l2_user_id:
        requester_name = await get_employee_display_name(session, r.employee_id)
        await notify_from_template(
            session,
            user_id=l2_user_id,
            type=NotificationType.PROCUREMENT_PENDING,
            context={
                "kind": "Reimbursement",
                "requester_name": requester_name,
                "amount_idr": f"{int(r.amount):,}".replace(",", "."),
                "purpose": r.description or r.category,
                "request_id": str(r.id),
                "tab": "reimbursement",
            },
        )
        await session.commit()
    return r


async def approve_reimbursement_l2(
    session: AsyncSession,
    reimb_id: UUID,
    approver_user_id: UUID,
    data: ReimbursementApprove,
) -> Reimbursement:
    r = await get_reimbursement(session, reimb_id)
    if r.status != "PENDING_L2":
        raise InvalidStateError(f"Status {r.status} — bukan PENDING_L2")
    if r.layer1_approver_id == approver_user_id:
        raise SelfApprovalBlockedError("L2 harus berbeda dari L1")

    emp_result = await session.execute(select(Employee).where(Employee.id == r.employee_id))
    emp = emp_result.scalar_one_or_none()
    if emp and emp.user_id == approver_user_id:
        raise SelfApprovalBlockedError("Tidak boleh approve request sendiri")

    r.layer2_approver_id = approver_user_id
    r.layer2_approved_at = datetime.now(UTC)
    r.layer2_notes = data.notes
    r.status = "APPROVED"
    await session.commit()
    await session.refresh(r)

    # TSK-060 — notify requester (approved)
    requester_user_id = await get_requester_user_id(session, r.employee_id)
    if requester_user_id:
        await notify_from_template(
            session,
            user_id=requester_user_id,
            type=NotificationType.PROCUREMENT_APPROVED,
            context={
                "kind": "Reimbursement",
                "amount_idr": f"{int(r.amount):,}".replace(",", "."),
                "request_id": str(r.id),
                "tab": "reimbursement",
            },
        )
        await session.commit()
    return r


async def reject_reimbursement(
    session: AsyncSession,
    reimb_id: UUID,
    rejector_user_id: UUID,
    data: ReimbursementReject,
) -> Reimbursement:
    r = await get_reimbursement(session, reimb_id)
    if r.status not in {"PENDING_L1", "PENDING_L2"}:
        raise InvalidStateError(f"Status {r.status} — hanya pending yang bisa reject")
    r.status = "REJECTED"
    r.rejected_by_user_id = rejector_user_id
    r.rejected_at = datetime.now(UTC)
    r.rejection_reason = data.rejection_reason
    await session.commit()
    await session.refresh(r)

    # TSK-060 — notify requester (rejected)
    requester_user_id = await get_requester_user_id(session, r.employee_id)
    if requester_user_id:
        await notify_from_template(
            session,
            user_id=requester_user_id,
            type=NotificationType.APPROVAL_REJECTED,
            context={
                "request_type": "Reimbursement",
                "approver_name": "—",
                "reason": data.rejection_reason or "(no reason)",
                "link": f"/finance?tab=reimbursement&id={r.id}",
            },
        )
        await session.commit()
    return r


async def cancel_reimbursement(session: AsyncSession, reimb_id: UUID) -> Reimbursement:
    r = await get_reimbursement(session, reimb_id)
    if r.status in {"REJECTED", "CANCELLED", "TRANSFERRED"}:
        raise InvalidStateError(f"Status {r.status} — tidak bisa cancel")
    r.status = "CANCELLED"
    r.cancelled_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(r)
    return r


async def mark_transferred(
    session: AsyncSession,
    reimb_id: UUID,
    transferrer_user_id: UUID,
    data: ReimbursementTransfer,
) -> Reimbursement:
    r = await get_reimbursement(session, reimb_id)
    if r.status != "APPROVED":
        raise InvalidStateError(f"Status {r.status} — hanya APPROVED yang bisa di-transfer")
    r.status = "TRANSFERRED"
    r.transferred_at = date.today()
    r.transferred_by_user_id = transferrer_user_id
    r.transfer_reference = data.transfer_reference
    await session.commit()
    await session.refresh(r)
    return r


# ─── Procurement CRUD ──────────────────────────────────────────────


async def get_procurement(session: AsyncSession, proc_id: UUID) -> ProcurementRequest:
    stmt = select(ProcurementRequest).where(ProcurementRequest.id == proc_id)
    result = await session.execute(stmt)
    p = result.scalar_one_or_none()
    if p is None:
        raise ProcurementNotFoundError(f"Procurement {proc_id} not found")
    return p


async def list_procurements(
    session: AsyncSession,
    requested_by_user_id: UUID | None = None,
    status_filter: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[ProcurementRequest], int]:
    page = max(page, 1)
    page_size = max(min(page_size, 200), 1)

    base = select(ProcurementRequest)
    if requested_by_user_id is not None:
        base = base.where(ProcurementRequest.requested_by_user_id == requested_by_user_id)
    if status_filter is not None:
        base = base.where(ProcurementRequest.status == status_filter)
    if category is not None:
        base = base.where(ProcurementRequest.item_category == category)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    stmt = (
        base.order_by(ProcurementRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def create_procurement(
    session: AsyncSession,
    data: ProcurementCreate,
    requested_by_user_id: UUID,
) -> ProcurementRequest:
    p = ProcurementRequest(
        requested_by_user_id=requested_by_user_id,
        request_date=data.request_date or date.today(),
        item_description=data.item_description,
        item_category=data.item_category,
        quantity=data.quantity,
        estimated_amount=data.estimated_amount,
        currency=data.currency,
        vendor_id=data.vendor_id,
        is_asset=data.is_asset,
        expected_delivery_date=data.expected_delivery_date,
        notes=data.notes,
        status="PENDING_L1",
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)

    # TSK-060 — notify L1 approver
    l1_user_id, _ = await find_l1_l2_approver_user_ids_by_user(session, requested_by_user_id)
    if l1_user_id:
        requester_name = await get_user_display_name(session, requested_by_user_id)
        await notify_from_template(
            session,
            user_id=l1_user_id,
            type=NotificationType.PROCUREMENT_PENDING,
            context={
                "kind": "Procurement",
                "requester_name": requester_name,
                "amount_idr": f"{int(data.estimated_amount):,}".replace(",", "."),
                "purpose": data.item_description,
                "request_id": str(p.id),
                "tab": "procurement",
            },
        )
        await session.commit()
    return p


async def approve_procurement_l1(
    session: AsyncSession,
    proc_id: UUID,
    approver_user_id: UUID,
    data: ReimbursementApprove,
) -> ProcurementRequest:
    p = await get_procurement(session, proc_id)
    if p.status != "PENDING_L1":
        raise InvalidStateError(f"Status {p.status} — bukan PENDING_L1")
    if p.requested_by_user_id == approver_user_id:
        raise SelfApprovalBlockedError("Tidak boleh approve request sendiri")
    p.layer1_approver_id = approver_user_id
    p.layer1_approved_at = datetime.now(UTC)
    p.layer1_notes = data.notes
    p.status = "PENDING_L2"
    await session.commit()
    await session.refresh(p)

    # TSK-060 — notify L2
    _, l2_user_id = await find_l1_l2_approver_user_ids_by_user(session, p.requested_by_user_id)
    if l2_user_id:
        requester_name = await get_user_display_name(session, p.requested_by_user_id)
        await notify_from_template(
            session,
            user_id=l2_user_id,
            type=NotificationType.PROCUREMENT_PENDING,
            context={
                "kind": "Procurement",
                "requester_name": requester_name,
                "amount_idr": f"{int(p.estimated_amount):,}".replace(",", "."),
                "purpose": p.item_description,
                "request_id": str(p.id),
                "tab": "procurement",
            },
        )
        await session.commit()
    return p


async def approve_procurement_l2(
    session: AsyncSession,
    proc_id: UUID,
    approver_user_id: UUID,
    data: ReimbursementApprove,
) -> ProcurementRequest:
    p = await get_procurement(session, proc_id)
    if p.status != "PENDING_L2":
        raise InvalidStateError(f"Status {p.status} — bukan PENDING_L2")
    if p.layer1_approver_id == approver_user_id:
        raise SelfApprovalBlockedError("L2 harus berbeda dari L1")
    if p.requested_by_user_id == approver_user_id:
        raise SelfApprovalBlockedError("Tidak boleh approve request sendiri")
    p.layer2_approver_id = approver_user_id
    p.layer2_approved_at = datetime.now(UTC)
    p.layer2_notes = data.notes
    p.status = "APPROVED"
    await session.commit()
    await session.refresh(p)

    # TSK-060 — notify requester (approved)
    await notify_from_template(
        session,
        user_id=p.requested_by_user_id,
        type=NotificationType.PROCUREMENT_APPROVED,
        context={
            "kind": "Procurement",
            "amount_idr": f"{int(p.estimated_amount):,}".replace(",", "."),
            "request_id": str(p.id),
            "tab": "procurement",
        },
    )
    await session.commit()
    return p


async def reject_procurement(
    session: AsyncSession,
    proc_id: UUID,
    rejector_user_id: UUID,
    data: ReimbursementReject,
) -> ProcurementRequest:
    p = await get_procurement(session, proc_id)
    if p.status not in {"PENDING_L1", "PENDING_L2"}:
        raise InvalidStateError(f"Status {p.status} — hanya pending yang bisa reject")
    p.status = "REJECTED"
    p.rejected_by_user_id = rejector_user_id
    p.rejected_at = datetime.now(UTC)
    p.rejection_reason = data.rejection_reason
    await session.commit()
    await session.refresh(p)

    # TSK-060 — notify requester (rejected)
    await notify_from_template(
        session,
        user_id=p.requested_by_user_id,
        type=NotificationType.APPROVAL_REJECTED,
        context={
            "request_type": "Procurement",
            "approver_name": "—",
            "reason": data.rejection_reason or "(no reason)",
            "link": f"/finance?tab=procurement&id={p.id}",
        },
    )
    await session.commit()
    return p


async def cancel_procurement(session: AsyncSession, proc_id: UUID) -> ProcurementRequest:
    p = await get_procurement(session, proc_id)
    if p.status in {"REJECTED", "CANCELLED", "DELIVERED"}:
        raise InvalidStateError(f"Status {p.status} — tidak bisa cancel")
    p.status = "CANCELLED"
    p.cancelled_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(p)
    return p


async def order_procurement(
    session: AsyncSession, proc_id: UUID, data: ProcurementOrder
) -> ProcurementRequest:
    p = await get_procurement(session, proc_id)
    if p.status != "APPROVED":
        raise InvalidStateError(f"Status {p.status} — hanya APPROVED yang bisa di-order")
    p.po_number = data.po_number
    p.ordered_at = date.today()
    if data.vendor_id:
        p.vendor_id = data.vendor_id
    if data.actual_amount is not None:
        p.actual_amount = data.actual_amount
    p.status = "ORDERED"
    await session.commit()
    await session.refresh(p)
    return p


async def deliver_procurement(
    session: AsyncSession, proc_id: UUID, data: ProcurementDeliver
) -> ProcurementRequest:
    p = await get_procurement(session, proc_id)
    if p.status != "ORDERED":
        raise InvalidStateError(f"Status {p.status} — hanya ORDERED yang bisa di-deliver")
    p.status = "DELIVERED"
    p.actual_delivery_date = data.actual_delivery_date
    await session.commit()
    await session.refresh(p)
    return p


# ─── Helpers ───────────────────────────────────────────────────────


def calc_total_pages(total: int, page_size: int) -> int:
    if total == 0:
        return 0
    return math.ceil(total / page_size)
