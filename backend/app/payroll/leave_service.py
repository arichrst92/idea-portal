"""Leave business logic — TSK-019.

Workflow:
1. Employee submit LeaveRequest → status PENDING_L1
2. L1 (supervisor) approve → status PENDING_L2
3. L2 (GM/HR) approve → status APPROVED, auto-deduct dari LeaveBalance
4. Reject di L1 atau L2 → status REJECTED
5. Cancel oleh employee sebelum APPROVED → status CANCELLED

Days calculation:
- Inclusive both ends (start_date dan end_date di-count)
- Exclude weekend (Sat+Sun)
- Exclude national holiday dari tabel holidays
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.organization.models import Employee, EmployeeStatus
from app.payroll.leave_schemas import (
    LeaveRequestApprove,
    LeaveRequestCreate,
    LeaveRequestReject,
    LeaveRequestStatus,
)
from app.payroll.models import Holiday, LeaveBalance, LeaveRequest, LeaveType


# ─── Exceptions ────────────────────────────────────────────────────


class LeaveRequestNotFoundError(Exception):
    pass


class LeaveTypeNotFoundError(Exception):
    pass


class InsufficientBalanceError(Exception):
    pass


class InvalidLeaveStateError(Exception):
    pass


class SelfApprovalBlockedError(Exception):
    pass


# ─── LeaveType helpers ─────────────────────────────────────────────


async def list_leave_types(session: AsyncSession) -> list[LeaveType]:
    stmt = select(LeaveType).order_by(LeaveType.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_leave_type(session: AsyncSession, type_id: UUID) -> LeaveType:
    stmt = select(LeaveType).where(LeaveType.id == type_id)
    result = await session.execute(stmt)
    lt = result.scalar_one_or_none()
    if lt is None:
        raise LeaveTypeNotFoundError(f"LeaveType {type_id} not found")
    return lt


# ─── Days calculation ──────────────────────────────────────────────


async def calculate_business_days(
    session: AsyncSession, start_date: date, end_date: date
) -> int:
    """Hitung hari kerja: exclude weekend + national holiday.

    Both ends inclusive.
    """
    if end_date < start_date:
        raise InvalidLeaveStateError("end_date harus >= start_date")

    # Fetch holidays dalam range (lebih efisien single query)
    holiday_stmt = select(Holiday.holiday_date).where(
        Holiday.holiday_date >= start_date,
        Holiday.holiday_date <= end_date,
    )
    holiday_result = await session.execute(holiday_stmt)
    holiday_dates = {row[0] for row in holiday_result.all()}

    days = 0
    cursor = start_date
    while cursor <= end_date:
        # Weekday: 0=Monday, 6=Sunday — exclude 5(Sat) and 6(Sun)
        if cursor.weekday() < 5 and cursor not in holiday_dates:
            days += 1
        cursor += timedelta(days=1)
    return days


# ─── LeaveBalance ──────────────────────────────────────────────────


async def get_or_create_balance(
    session: AsyncSession,
    employee_id: UUID,
    leave_type_id: UUID,
    year: int,
) -> LeaveBalance:
    """Get balance, auto-create kalau belum ada untuk tahun ini.

    Allocated = leave_type.default_days_per_year saat first create.
    """
    stmt = select(LeaveBalance).where(
        LeaveBalance.employee_id == employee_id,
        LeaveBalance.leave_type_id == leave_type_id,
        LeaveBalance.year == year,
    )
    result = await session.execute(stmt)
    balance = result.scalar_one_or_none()
    if balance is not None:
        return balance

    # Auto-create
    leave_type = await get_leave_type(session, leave_type_id)
    balance = LeaveBalance(
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        year=year,
        allocated_days=leave_type.default_days_per_year,
        used_days=0,
        carried_over_days=0,
    )
    session.add(balance)
    await session.commit()
    await session.refresh(balance)
    return balance


async def get_employee_balances(
    session: AsyncSession, employee_id: UUID, year: int | None = None
) -> list[LeaveBalance]:
    """All balances untuk 1 employee. Default tahun ini."""
    year = year or date.today().year
    stmt = (
        select(LeaveBalance)
        .where(LeaveBalance.employee_id == employee_id, LeaveBalance.year == year)
        .order_by(LeaveBalance.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def ensure_all_balances(
    session: AsyncSession, employee_id: UUID, year: int | None = None
) -> list[LeaveBalance]:
    """Auto-create balance untuk SEMUA leave type kalau employee belum punya."""
    year = year or date.today().year
    leave_types = await list_leave_types(session)
    balances = []
    for lt in leave_types:
        b = await get_or_create_balance(session, employee_id, lt.id, year)
        balances.append(b)
    return balances


# ─── LeaveRequest ──────────────────────────────────────────────────


async def get_leave_request(session: AsyncSession, req_id: UUID) -> LeaveRequest:
    stmt = select(LeaveRequest).where(LeaveRequest.id == req_id)
    result = await session.execute(stmt)
    req = result.scalar_one_or_none()
    if req is None:
        raise LeaveRequestNotFoundError(f"LeaveRequest {req_id} not found")
    return req


async def list_leave_requests(
    session: AsyncSession,
    employee_id: UUID | None = None,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[LeaveRequest], int]:
    page = max(page, 1)
    page_size = max(min(page_size, 200), 1)

    base = select(LeaveRequest)
    if employee_id is not None:
        base = base.where(LeaveRequest.employee_id == employee_id)
    if status_filter is not None:
        base = base.where(LeaveRequest.status == status_filter)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    stmt = (
        base.order_by(LeaveRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def create_leave_request(
    session: AsyncSession, data: LeaveRequestCreate
) -> LeaveRequest:
    """Submit cuti — calculate days, validate saldo, save PENDING_L1."""
    # Validate employee
    emp_result = await session.execute(
        select(Employee).where(Employee.id == data.employee_id, Employee.deleted_at.is_(None))
    )
    emp = emp_result.scalar_one_or_none()
    if emp is None:
        raise InvalidLeaveStateError(f"Employee {data.employee_id} not found")
    if emp.status not in {EmployeeStatus.ACTIVE, EmployeeStatus.PROBATION}:
        raise InvalidLeaveStateError(
            f"Employee status {emp.status} — tidak bisa request cuti"
        )

    # Validate leave type
    leave_type = await get_leave_type(session, data.leave_type_id)

    # Calculate business days
    days = await calculate_business_days(session, data.start_date, data.end_date)
    if days == 0:
        raise InvalidLeaveStateError(
            "0 hari kerja dalam range yang dipilih (semua weekend/holiday)"
        )

    # Validate saldo (kalau paid leave)
    if leave_type.is_paid:
        year = data.start_date.year
        balance = await get_or_create_balance(
            session, data.employee_id, data.leave_type_id, year
        )
        remaining = balance.allocated_days + balance.carried_over_days - balance.used_days
        if days > remaining:
            raise InsufficientBalanceError(
                f"Saldo {leave_type.name} tidak cukup. "
                f"Tersisa {remaining} hari, request {days} hari."
            )

    # Cek overlap dengan request pending/approved untuk employee
    overlap_stmt = select(LeaveRequest).where(
        LeaveRequest.employee_id == data.employee_id,
        LeaveRequest.status.in_(["PENDING_L1", "PENDING_L2", "APPROVED"]),
        LeaveRequest.end_date >= data.start_date,
        LeaveRequest.start_date <= data.end_date,
    )
    overlap_result = await session.execute(overlap_stmt)
    if overlap_result.scalar_one_or_none() is not None:
        raise InvalidLeaveStateError(
            "Sudah ada request cuti pending/approved yang overlap dengan tanggal ini"
        )

    req = LeaveRequest(
        employee_id=data.employee_id,
        leave_type_id=data.leave_type_id,
        start_date=data.start_date,
        end_date=data.end_date,
        days_count=days,
        reason=data.reason,
        status=LeaveRequestStatus.PENDING_L1.value,
    )
    session.add(req)
    await session.commit()
    await session.refresh(req)
    return req


async def approve_l1(
    session: AsyncSession,
    req_id: UUID,
    approver_user_id: UUID,
    data: LeaveRequestApprove,
) -> LeaveRequest:
    req = await get_leave_request(session, req_id)
    if req.status != LeaveRequestStatus.PENDING_L1.value:
        raise InvalidLeaveStateError(f"Status {req.status} — bukan PENDING_L1")

    # Get employee untuk cek self-approval
    emp_result = await session.execute(select(Employee).where(Employee.id == req.employee_id))
    emp = emp_result.scalar_one_or_none()
    if emp and emp.user_id == approver_user_id:
        raise SelfApprovalBlockedError("Tidak boleh approve request sendiri")

    req.layer1_approver_id = approver_user_id
    req.layer1_approved_at = datetime.now(UTC)
    req.layer1_notes = data.notes
    req.status = LeaveRequestStatus.PENDING_L2.value
    await session.commit()
    await session.refresh(req)
    return req


async def approve_l2(
    session: AsyncSession,
    req_id: UUID,
    approver_user_id: UUID,
    data: LeaveRequestApprove,
) -> LeaveRequest:
    """L2 approve = final. Auto-deduct saldo kalau paid leave."""
    req = await get_leave_request(session, req_id)
    if req.status != LeaveRequestStatus.PENDING_L2.value:
        raise InvalidLeaveStateError(f"Status {req.status} — bukan PENDING_L2")
    if req.layer1_approver_id == approver_user_id:
        raise SelfApprovalBlockedError(
            "Approver L2 harus berbeda dari approver L1"
        )

    # Get employee + leave_type
    emp_result = await session.execute(select(Employee).where(Employee.id == req.employee_id))
    emp = emp_result.scalar_one_or_none()
    if emp and emp.user_id == approver_user_id:
        raise SelfApprovalBlockedError("Tidak boleh approve request sendiri")

    leave_type = await get_leave_type(session, req.leave_type_id)

    # Deduct saldo (paid leave only)
    if leave_type.is_paid:
        year = req.start_date.year
        balance = await get_or_create_balance(
            session, req.employee_id, req.leave_type_id, year
        )
        # Double-check saldo (mungkin berubah sejak request dibuat)
        remaining = balance.allocated_days + balance.carried_over_days - balance.used_days
        if req.days_count > remaining:
            raise InsufficientBalanceError(
                f"Saldo {leave_type.name} sudah berkurang sejak request dibuat. "
                f"Tersisa {remaining} hari, request {req.days_count} hari."
            )
        balance.used_days += req.days_count

    req.layer2_approver_id = approver_user_id
    req.layer2_approved_at = datetime.now(UTC)
    req.layer2_notes = data.notes
    req.status = LeaveRequestStatus.APPROVED.value
    await session.commit()
    await session.refresh(req)
    return req


async def reject_request(
    session: AsyncSession,
    req_id: UUID,
    rejector_user_id: UUID,
    data: LeaveRequestReject,
) -> LeaveRequest:
    req = await get_leave_request(session, req_id)
    if req.status not in {LeaveRequestStatus.PENDING_L1.value, LeaveRequestStatus.PENDING_L2.value}:
        raise InvalidLeaveStateError(
            f"Status {req.status} — hanya pending yang bisa di-reject"
        )

    req.status = LeaveRequestStatus.REJECTED.value
    req.rejected_by_user_id = rejector_user_id
    req.rejected_at = datetime.now(UTC)
    req.rejection_reason = data.rejection_reason
    await session.commit()
    await session.refresh(req)
    return req


async def cancel_request(
    session: AsyncSession, req_id: UUID, requester_user_id: UUID
) -> LeaveRequest:
    """Cancel — employee batalkan request sendiri (sebelum APPROVED).

    Kalau sudah APPROVED, employee tetap bisa cancel tapi saldo dikembalikan.
    """
    req = await get_leave_request(session, req_id)
    if req.status in {LeaveRequestStatus.CANCELLED.value, LeaveRequestStatus.REJECTED.value}:
        raise InvalidLeaveStateError(f"Status {req.status} — sudah final")

    was_approved = req.status == LeaveRequestStatus.APPROVED.value

    req.status = LeaveRequestStatus.CANCELLED.value
    req.cancelled_at = datetime.now(UTC)

    # Refund saldo kalau approved
    if was_approved:
        leave_type = await get_leave_type(session, req.leave_type_id)
        if leave_type.is_paid:
            year = req.start_date.year
            balance_stmt = select(LeaveBalance).where(
                LeaveBalance.employee_id == req.employee_id,
                LeaveBalance.leave_type_id == req.leave_type_id,
                LeaveBalance.year == year,
            )
            balance_result = await session.execute(balance_stmt)
            balance = balance_result.scalar_one_or_none()
            if balance:
                balance.used_days = max(0, balance.used_days - req.days_count)

    await session.commit()
    await session.refresh(req)
    return req


# ─── Helpers ───────────────────────────────────────────────────────


def calc_total_pages(total: int, page_size: int) -> int:
    if total == 0:
        return 0
    return math.ceil(total / page_size)


def compute_remaining(balance: LeaveBalance) -> int:
    return balance.allocated_days + balance.carried_over_days - balance.used_days
