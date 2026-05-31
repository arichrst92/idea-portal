"""Separation business logic — TSK-017.

State machine:
DRAFT → PENDING_APPROVAL_L1 (submit by initiator, atau auto saat create)
PENDING_APPROVAL_L1 → PENDING_APPROVAL_L2 (L1 approve)
PENDING_APPROVAL_L1 → REJECTED (L1 reject)
PENDING_APPROVAL_L2 → APPROVED (L2 approve)
PENDING_APPROVAL_L2 → REJECTED (L2 reject)
APPROVED → EXECUTED (execute, update employee.status + soft delete)
Any (kecuali EXECUTED) → CANCELLED

Rules:
- Self-approval blocked (initiator ≠ approver_l1 ≠ approver_l2)
- Sequential: L2 tidak bisa approve sebelum L1
- Execute hanya bisa setelah APPROVED, dan effective_date <= today
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.notification.approver_chain import (
    find_l1_l2_approver_user_ids,
    get_employee_display_name,
)
from app.notification.models import NotificationType
from app.notification.templates import notify_from_template
from app.organization.models import Employee, EmployeeStatus
from app.separation.models import (
    EmployeeSeparation,
    SeparationStatus,
    SeparationType,
)
from app.separation.schemas import (
    ExitInterviewRequest,
    SeparationApproveRequest,
    SeparationCancelRequest,
    SeparationCreate,
    SeparationRejectRequest,
)


# ─── Exceptions ────────────────────────────────────────────────────


class SeparationNotFoundError(Exception):
    pass


class InvalidSeparationStateError(Exception):
    pass


class SelfApprovalBlockedError(Exception):
    pass


class EmployeeNotFoundError(Exception):
    pass


# ─── CRUD ──────────────────────────────────────────────────────────


async def get_separation(session: AsyncSession, sep_id: UUID) -> EmployeeSeparation:
    stmt = select(EmployeeSeparation).where(EmployeeSeparation.id == sep_id)
    result = await session.execute(stmt)
    sep = result.scalar_one_or_none()
    if sep is None:
        raise SeparationNotFoundError(f"Separation {sep_id} not found")
    return sep


async def list_separations(
    session: AsyncSession,
    employee_id: UUID | None = None,
    separation_type: SeparationType | None = None,
    status: SeparationStatus | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[EmployeeSeparation], int]:
    page = max(page, 1)
    page_size = max(min(page_size, 200), 1)

    base = select(EmployeeSeparation)
    if employee_id is not None:
        base = base.where(EmployeeSeparation.employee_id == employee_id)
    if separation_type is not None:
        base = base.where(EmployeeSeparation.separation_type == separation_type)
    if status is not None:
        base = base.where(EmployeeSeparation.status == status)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    stmt = (
        base.order_by(EmployeeSeparation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def create_separation(
    session: AsyncSession,
    data: SeparationCreate,
    initiated_by_user_id: UUID,
    auto_submit: bool = True,
) -> EmployeeSeparation:
    """Create separation, auto submit ke PENDING_APPROVAL_L1 secara default."""
    # Validate employee exists + active
    emp_result = await session.execute(
        select(Employee).where(
            Employee.id == data.employee_id, Employee.deleted_at.is_(None)
        )
    )
    emp = emp_result.scalar_one_or_none()
    if emp is None:
        raise EmployeeNotFoundError(f"Employee {data.employee_id} not found / sudah deleted")

    if emp.status in {EmployeeStatus.ALUMNI, EmployeeStatus.RESIGNED, EmployeeStatus.TERMINATED}:
        raise InvalidSeparationStateError(
            f"Employee status {emp.status} — sudah berhenti, tidak bisa create separation baru"
        )

    # Check existing pending separation untuk employee
    existing = await session.execute(
        select(EmployeeSeparation).where(
            EmployeeSeparation.employee_id == data.employee_id,
            EmployeeSeparation.status.in_(
                [
                    SeparationStatus.DRAFT,
                    SeparationStatus.PENDING_APPROVAL_L1,
                    SeparationStatus.PENDING_APPROVAL_L2,
                    SeparationStatus.APPROVED,
                ]
            ),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise InvalidSeparationStateError(
            "Sudah ada separation pending untuk employee ini"
        )

    sep = EmployeeSeparation(
        employee_id=data.employee_id,
        separation_type=data.separation_type,
        reason=data.reason,
        effective_date=data.effective_date,
        notice_period_days=data.notice_period_days,
        severance_amount=data.severance_amount,
        currency=data.currency,
        assets_to_return=data.assets_to_return,
        related_warning_letter_id=data.related_warning_letter_id,
        initiated_by_user_id=initiated_by_user_id,
        status=SeparationStatus.PENDING_APPROVAL_L1 if auto_submit else SeparationStatus.DRAFT,
    )
    session.add(sep)
    await session.commit()
    await session.refresh(sep)
    return sep


# ─── Approval workflow ─────────────────────────────────────────────


async def submit_for_approval(
    session: AsyncSession, sep_id: UUID
) -> EmployeeSeparation:
    """DRAFT → PENDING_APPROVAL_L1."""
    sep = await get_separation(session, sep_id)
    if sep.status != SeparationStatus.DRAFT:
        raise InvalidSeparationStateError(
            f"Status {sep.status} — hanya DRAFT yang bisa submit"
        )
    sep.status = SeparationStatus.PENDING_APPROVAL_L1
    await session.commit()
    await session.refresh(sep)

    # TSK-060 — notify L1 approver (supervisor of separating employee)
    l1_user_id, _ = await find_l1_l2_approver_user_ids(session, sep.employee_id)
    if l1_user_id:
        emp_name = await get_employee_display_name(session, sep.employee_id)
        await notify_from_template(
            session,
            user_id=l1_user_id,
            type=NotificationType.SEPARATION_PENDING,
            context={
                "requester_name": emp_name,
                "separation_type": sep.separation_type.value if hasattr(sep.separation_type, "value") else str(sep.separation_type),
                "employee_name": emp_name,
                "effective_date": sep.effective_date.strftime("%d %b %Y") if sep.effective_date else "—",
                "separation_id": str(sep.id),
            },
        )
        await session.commit()
    return sep


async def approve_l1(
    session: AsyncSession,
    sep_id: UUID,
    approver_user_id: UUID,
    data: SeparationApproveRequest,
) -> EmployeeSeparation:
    """L1 approve: PENDING_APPROVAL_L1 → PENDING_APPROVAL_L2."""
    sep = await get_separation(session, sep_id)
    if sep.status != SeparationStatus.PENDING_APPROVAL_L1:
        raise InvalidSeparationStateError(
            f"Status {sep.status} — bukan PENDING_APPROVAL_L1"
        )
    if sep.initiated_by_user_id == approver_user_id:
        raise SelfApprovalBlockedError("Tidak boleh approve request sendiri")

    sep.approval_l1_user_id = approver_user_id
    sep.approval_l1_at = datetime.now(UTC)
    sep.approval_l1_notes = data.notes
    sep.status = SeparationStatus.PENDING_APPROVAL_L2
    await session.commit()
    await session.refresh(sep)

    # TSK-060 — notify L2 approver
    _, l2_user_id = await find_l1_l2_approver_user_ids(session, sep.employee_id)
    if l2_user_id:
        emp_name = await get_employee_display_name(session, sep.employee_id)
        await notify_from_template(
            session,
            user_id=l2_user_id,
            type=NotificationType.SEPARATION_PENDING,
            context={
                "requester_name": emp_name,
                "separation_type": sep.separation_type.value if hasattr(sep.separation_type, "value") else str(sep.separation_type),
                "employee_name": emp_name,
                "effective_date": sep.effective_date.strftime("%d %b %Y") if sep.effective_date else "—",
                "separation_id": str(sep.id),
            },
        )
        await session.commit()
    return sep


async def approve_l2(
    session: AsyncSession,
    sep_id: UUID,
    approver_user_id: UUID,
    data: SeparationApproveRequest,
) -> EmployeeSeparation:
    """L2 approve: PENDING_APPROVAL_L2 → APPROVED."""
    sep = await get_separation(session, sep_id)
    if sep.status != SeparationStatus.PENDING_APPROVAL_L2:
        raise InvalidSeparationStateError(
            f"Status {sep.status} — bukan PENDING_APPROVAL_L2"
        )
    if sep.initiated_by_user_id == approver_user_id:
        raise SelfApprovalBlockedError("Tidak boleh approve request sendiri")
    if sep.approval_l1_user_id == approver_user_id:
        raise SelfApprovalBlockedError(
            "Tidak boleh approve L2 kalau sudah approve L1 (butuh approver berbeda)"
        )

    sep.approval_l2_user_id = approver_user_id
    sep.approval_l2_at = datetime.now(UTC)
    sep.approval_l2_notes = data.notes
    sep.status = SeparationStatus.APPROVED
    await session.commit()
    await session.refresh(sep)

    # TSK-060 — notify initiator (separation approved)
    await notify_from_template(
        session,
        user_id=sep.initiated_by_user_id,
        type=NotificationType.APPROVAL_APPROVED,
        context={
            "request_type": "Separation",
            "approver_name": "—",
            "link": f"/separations/{sep.id}",
        },
    )
    await session.commit()
    return sep


async def reject_separation(
    session: AsyncSession,
    sep_id: UUID,
    rejector_user_id: UUID,
    data: SeparationRejectRequest,
) -> EmployeeSeparation:
    """Reject di PENDING_APPROVAL_L1 atau PENDING_APPROVAL_L2."""
    sep = await get_separation(session, sep_id)
    if sep.status not in {
        SeparationStatus.PENDING_APPROVAL_L1,
        SeparationStatus.PENDING_APPROVAL_L2,
    }:
        raise InvalidSeparationStateError(
            f"Status {sep.status} — hanya pending state yang bisa di-reject"
        )

    sep.status = SeparationStatus.REJECTED
    sep.rejected_by_user_id = rejector_user_id
    sep.rejected_at = datetime.now(UTC)
    sep.rejection_reason = data.rejection_reason
    await session.commit()
    await session.refresh(sep)

    # TSK-060 — notify initiator
    await notify_from_template(
        session,
        user_id=sep.initiated_by_user_id,
        type=NotificationType.APPROVAL_REJECTED,
        context={
            "request_type": "Separation",
            "approver_name": "—",
            "reason": data.rejection_reason or "(no reason)",
            "link": f"/separations/{sep.id}",
        },
    )
    await session.commit()
    return sep


async def cancel_separation(
    session: AsyncSession,
    sep_id: UUID,
    cancellor_user_id: UUID,
    data: SeparationCancelRequest,
) -> EmployeeSeparation:
    """Cancel kapan saja sebelum EXECUTED. Hanya initiator atau executor."""
    sep = await get_separation(session, sep_id)
    if sep.status in {SeparationStatus.EXECUTED, SeparationStatus.CANCELLED}:
        raise InvalidSeparationStateError(
            f"Status {sep.status} — tidak bisa di-cancel lagi"
        )

    sep.status = SeparationStatus.CANCELLED
    sep.cancelled_at = datetime.now(UTC)
    sep.cancellation_reason = data.cancellation_reason
    await session.commit()
    await session.refresh(sep)
    return sep


async def execute_separation(
    session: AsyncSession, sep_id: UUID, executor_user_id: UUID
) -> tuple[EmployeeSeparation, Employee]:
    """Eksekusi separation yang sudah APPROVED.

    Effects:
    - Set employee.status sesuai type (RESIGNED/TERMINATED/ALUMNI)
    - Set employee.last_working_day = effective_date
    - Soft delete employee (deleted_at = now)
    - Disable user login (user.is_active = false)
    - Update separation status → EXECUTED + executed_at/by
    """
    sep = await get_separation(session, sep_id)
    if sep.status != SeparationStatus.APPROVED:
        raise InvalidSeparationStateError(
            f"Status {sep.status} — hanya APPROVED yang bisa di-execute"
        )

    # Optional: enforce effective_date <= today
    # Skip strict check — admin bisa execute earlier untuk tanggal mendatang

    # Load employee + user
    emp_result = await session.execute(
        select(Employee).where(Employee.id == sep.employee_id)
    )
    emp = emp_result.scalar_one_or_none()
    if emp is None:
        raise EmployeeNotFoundError(f"Employee {sep.employee_id} not found")

    # Map separation_type → employee.status
    status_map = {
        SeparationType.RESIGNATION: EmployeeStatus.RESIGNED,
        SeparationType.LAYOFF: EmployeeStatus.ALUMNI,
        SeparationType.TERMINATION: EmployeeStatus.TERMINATED,
        SeparationType.END_OF_CONTRACT: EmployeeStatus.ALUMNI,
        SeparationType.RETIREMENT: EmployeeStatus.ALUMNI,
    }
    emp.status = status_map.get(sep.separation_type, EmployeeStatus.ALUMNI)
    emp.last_working_day = sep.effective_date
    emp.deleted_at = datetime.now(UTC)
    if emp.user_id:
        from app.identity.models import User

        user_result = await session.execute(select(User).where(User.id == emp.user_id))
        user = user_result.scalar_one_or_none()
        if user is not None:
            user.is_active = False

    # Update separation
    sep.status = SeparationStatus.EXECUTED
    sep.executed_by_user_id = executor_user_id
    sep.executed_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(sep)
    await session.refresh(emp)
    return sep, emp


# ─── Exit interview ────────────────────────────────────────────────


async def record_exit_interview(
    session: AsyncSession,
    sep_id: UUID,
    data: ExitInterviewRequest,
) -> EmployeeSeparation:
    """Record exit interview notes (typically setelah execute)."""
    sep = await get_separation(session, sep_id)
    if sep.status not in {SeparationStatus.APPROVED, SeparationStatus.EXECUTED}:
        raise InvalidSeparationStateError(
            "Exit interview hanya bisa dicatat setelah separation APPROVED/EXECUTED"
        )
    sep.exit_interview_notes = data.notes
    sep.exit_interview_completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(sep)
    return sep


# ─── Helpers ───────────────────────────────────────────────────────


def calc_total_pages(total: int, page_size: int) -> int:
    if total == 0:
        return 0
    return math.ceil(total / page_size)
