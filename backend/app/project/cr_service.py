"""Change Request business logic — TSK-070.

Workflow:
  DRAFT → submit → PENDING_L1 → approve_l1 → PENDING_L2 → approve_l2 → APPROVED
                                          → reject → REJECTED
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.notification.approver_chain import (
    find_l1_l2_approver_user_ids_by_user,
    get_user_display_name,
)
from app.notification.models import NotificationType
from app.notification.templates import notify_from_template
from app.project.cr_schemas import CRApprove, CRCreate, CRReject, CRUpdate
from app.project.models import (
    CRImpact,
    CRStatus,
    Project,
    ProjectChangeRequest,
)


class CRNotFoundError(Exception):
    pass


class CRStateError(Exception):
    pass


class SelfApprovalError(Exception):
    pass


# ─── CRUD ──────────────────────────────────────────────────────────


async def list_crs(
    session: AsyncSession,
    project_id: UUID | None = None,
    status_filter: CRStatus | None = None,
) -> list[ProjectChangeRequest]:
    stmt = select(ProjectChangeRequest).where(
        ProjectChangeRequest.deleted_at.is_(None)
    )
    if project_id is not None:
        stmt = stmt.where(ProjectChangeRequest.project_id == project_id)
    if status_filter is not None:
        stmt = stmt.where(ProjectChangeRequest.status == status_filter)
    stmt = stmt.order_by(ProjectChangeRequest.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_cr(session: AsyncSession, cr_id: UUID) -> ProjectChangeRequest:
    stmt = select(ProjectChangeRequest).where(
        ProjectChangeRequest.id == cr_id,
        ProjectChangeRequest.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    c = result.scalar_one_or_none()
    if c is None:
        raise CRNotFoundError(f"Change Request {cr_id} not found")
    return c


async def _next_cr_number(session: AsyncSession, project_id: UUID) -> str:
    """Generate CR number: {PROJECT_CODE}-CR-{N}."""
    project = await session.get(Project, project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")
    # Count existing CRs untuk project ini
    cnt_stmt = select(func.count(ProjectChangeRequest.id)).where(
        ProjectChangeRequest.project_id == project_id,
    )
    cnt = int((await session.execute(cnt_stmt)).scalar_one())
    return f"{project.code}-CR-{cnt + 1}"


async def create_cr(
    session: AsyncSession,
    project_id: UUID,
    data: CRCreate,
    requester_user_id: UUID,
) -> ProjectChangeRequest:
    cr_no = await _next_cr_number(session, project_id)
    cr = ProjectChangeRequest(
        project_id=project_id,
        cr_number=cr_no,
        title=data.title,
        description=data.description,
        impact_category=data.impact_category,
        scope_delta=data.scope_delta,
        timeline_delta_days=data.timeline_delta_days,
        cost_delta=data.cost_delta,
        currency=data.currency,
        requester_user_id=requester_user_id,
        status=CRStatus.DRAFT,
    )
    session.add(cr)
    await session.commit()
    await session.refresh(cr)
    return cr


async def update_cr(
    session: AsyncSession, cr_id: UUID, data: CRUpdate
) -> ProjectChangeRequest:
    cr = await get_cr(session, cr_id)
    if cr.status not in (CRStatus.DRAFT, CRStatus.PENDING_L1):
        raise CRStateError(f"Tidak bisa update CR di status {cr.status}")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cr, field, value)
    await session.commit()
    await session.refresh(cr)
    return cr


async def submit_cr(session: AsyncSession, cr_id: UUID) -> ProjectChangeRequest:
    """DRAFT → PENDING_L1."""
    cr = await get_cr(session, cr_id)
    if cr.status != CRStatus.DRAFT:
        raise CRStateError(f"Hanya DRAFT bisa submit, current: {cr.status}")
    cr.status = CRStatus.PENDING_L1
    await session.commit()
    await session.refresh(cr)

    # TSK-060 — notify L1 approver
    l1_user_id, _ = await find_l1_l2_approver_user_ids_by_user(session, cr.requester_user_id)
    if l1_user_id:
        project = await session.get(Project, cr.project_id)
        requester_name = await get_user_display_name(session, cr.requester_user_id)
        await notify_from_template(
            session,
            user_id=l1_user_id,
            type=NotificationType.CHANGE_REQUEST_PENDING,
            context={
                "requester_name": requester_name,
                "project_code": project.code if project else "—",
                "project_id": str(cr.project_id),
                "summary": cr.title,
                "cr_id": str(cr.id),
            },
        )
        await session.commit()
    return cr


async def approve_l1(
    session: AsyncSession, cr_id: UUID, approver_id: UUID, data: CRApprove
) -> ProjectChangeRequest:
    cr = await get_cr(session, cr_id)
    if cr.status != CRStatus.PENDING_L1:
        raise CRStateError(f"Hanya PENDING_L1 bisa approve_l1, current: {cr.status}")
    if cr.requester_user_id == approver_id:
        raise SelfApprovalError("Requester tidak boleh approve sendiri")
    cr.layer1_approver_id = approver_id
    cr.layer1_approved_at = date.today()
    cr.layer1_notes = data.notes
    cr.status = CRStatus.PENDING_L2
    await session.commit()
    await session.refresh(cr)

    # TSK-060 — notify L2 approver
    _, l2_user_id = await find_l1_l2_approver_user_ids_by_user(session, cr.requester_user_id)
    if l2_user_id:
        project = await session.get(Project, cr.project_id)
        requester_name = await get_user_display_name(session, cr.requester_user_id)
        await notify_from_template(
            session,
            user_id=l2_user_id,
            type=NotificationType.CHANGE_REQUEST_PENDING,
            context={
                "requester_name": requester_name,
                "project_code": project.code if project else "—",
                "project_id": str(cr.project_id),
                "summary": cr.title,
                "cr_id": str(cr.id),
            },
        )
        await session.commit()
    return cr


async def approve_l2(
    session: AsyncSession, cr_id: UUID, approver_id: UUID, data: CRApprove
) -> ProjectChangeRequest:
    """L2 approve → APPROVED + auto-notify Finance & Sales."""
    cr = await get_cr(session, cr_id)
    if cr.status != CRStatus.PENDING_L2:
        raise CRStateError(f"Hanya PENDING_L2 bisa approve_l2, current: {cr.status}")
    if cr.requester_user_id == approver_id or cr.layer1_approver_id == approver_id:
        raise SelfApprovalError("L2 approver tidak boleh sama dengan requester atau L1")
    cr.layer2_approver_id = approver_id
    cr.layer2_approved_at = date.today()
    cr.layer2_notes = data.notes
    cr.status = CRStatus.APPROVED

    # Auto-notify Finance kalau ada cost impact
    if Decimal(str(cr.cost_delta)) != Decimal("0"):
        cr.finance_notified_at = date.today()

    # Auto-notify Sales kalau project type CLIENT
    project = await session.get(Project, cr.project_id)
    from app.project.models import ProjectType
    if project and project.type == ProjectType.CLIENT:
        cr.sales_notified_at = date.today()

    await session.commit()
    await session.refresh(cr)

    # TSK-060 — notify requester (CR resolved/approved)
    await notify_from_template(
        session,
        user_id=cr.requester_user_id,
        type=NotificationType.CHANGE_REQUEST_RESOLVED,
        context={
            "project_code": project.code if project else "—",
            "project_id": str(cr.project_id),
            "summary": cr.title,
            "cr_id": str(cr.id),
        },
    )
    await session.commit()
    return cr


async def reject_cr(
    session: AsyncSession, cr_id: UUID, approver_id: UUID, data: CRReject
) -> ProjectChangeRequest:
    cr = await get_cr(session, cr_id)
    if cr.status not in (CRStatus.PENDING_L1, CRStatus.PENDING_L2):
        raise CRStateError(f"Hanya PENDING_L1/L2 bisa reject, current: {cr.status}")
    if cr.requester_user_id == approver_id:
        raise SelfApprovalError("Requester tidak boleh reject sendiri")
    cr.status = CRStatus.REJECTED
    cr.rejected_at = date.today()
    cr.rejection_reason = data.rejection_reason
    await session.commit()
    await session.refresh(cr)

    # TSK-060 — notify requester (rejected)
    project = await session.get(Project, cr.project_id)
    await notify_from_template(
        session,
        user_id=cr.requester_user_id,
        type=NotificationType.APPROVAL_REJECTED,
        context={
            "request_type": f"Change Request '{cr.title}'",
            "approver_name": "—",
            "reason": data.rejection_reason or "(no reason)",
            "link": f"/projects/{cr.project_id}?tab=cr&id={cr.id}",
        },
    )
    await session.commit()
    return cr


async def cancel_cr(
    session: AsyncSession, cr_id: UUID, requester_user_id: UUID
) -> ProjectChangeRequest:
    cr = await get_cr(session, cr_id)
    if cr.requester_user_id != requester_user_id:
        raise CRStateError("Hanya requester yang bisa cancel CR")
    if cr.status not in (CRStatus.DRAFT, CRStatus.PENDING_L1):
        raise CRStateError(f"Tidak bisa cancel CR di status {cr.status}")
    cr.status = CRStatus.CANCELLED
    await session.commit()
    await session.refresh(cr)
    return cr


async def soft_delete_cr(session: AsyncSession, cr_id: UUID) -> None:
    cr = await get_cr(session, cr_id)
    cr.deleted_at = datetime.now(UTC)
    await session.commit()
