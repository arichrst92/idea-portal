"""Helper untuk resolve approval chain user IDs — TSK-060.

Given a requester (employee), return:
- L1 user_id = direct supervisor's user_id
- L2 user_id = supervisor's supervisor's user_id (fallback: any L1-L3 in dept)

Used by notification wiring across Leave, Reimbursement, Separation, CR, etc.

If chain incomplete (no supervisor set), returns None for that layer —
caller should handle (skip notify) silently.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.organization.models import Employee

logger = logging.getLogger(__name__)


async def find_l1_l2_approver_user_ids(
    session: AsyncSession, employee_id: UUID
) -> tuple[UUID | None, UUID | None]:
    """Resolve (L1 user_id, L2 user_id) for the requester.

    L1 = supervisor of requester
    L2 = supervisor of supervisor

    Returns (None, None) if no supervisor chain set.
    Both fetched via single round-trip per layer.
    """
    # Layer 1: requester's supervisor
    l1_stmt = select(Employee).where(Employee.id == employee_id)
    requester = (await session.execute(l1_stmt)).scalar_one_or_none()
    if not requester or not requester.supervisor_id:
        return (None, None)

    l1_emp_stmt = select(Employee).where(Employee.id == requester.supervisor_id)
    l1_emp = (await session.execute(l1_emp_stmt)).scalar_one_or_none()
    if not l1_emp:
        return (None, None)
    l1_user_id = l1_emp.user_id

    # Layer 2: L1's supervisor
    if not l1_emp.supervisor_id:
        return (l1_user_id, None)
    l2_emp_stmt = select(Employee).where(Employee.id == l1_emp.supervisor_id)
    l2_emp = (await session.execute(l2_emp_stmt)).scalar_one_or_none()
    l2_user_id = l2_emp.user_id if l2_emp else None

    return (l1_user_id, l2_user_id)


async def get_requester_user_id(
    session: AsyncSession, employee_id: UUID
) -> UUID | None:
    """Get the user_id for an employee (= requester of a request)."""
    stmt = select(Employee.user_id).where(Employee.id == employee_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_employee_display_name(
    session: AsyncSession, employee_id: UUID
) -> str:
    """Get full_name of employee for notification body."""
    stmt = select(Employee.full_name).where(Employee.id == employee_id)
    name = (await session.execute(stmt)).scalar_one_or_none()
    return name or "Unknown"


async def find_l1_l2_approver_user_ids_by_user(
    session: AsyncSession, user_id: UUID
) -> tuple[UUID | None, UUID | None]:
    """Same as find_l1_l2_approver_user_ids but starting from a user_id.

    Used by flows where requester is identified by User (e.g. Procurement
    Request — requested_by_user_id).
    """
    emp_stmt = select(Employee).where(Employee.user_id == user_id)
    emp = (await session.execute(emp_stmt)).scalar_one_or_none()
    if emp is None:
        return (None, None)
    return await find_l1_l2_approver_user_ids(session, emp.id)


async def get_user_display_name(
    session: AsyncSession, user_id: UUID
) -> str:
    """Get full_name of the employee linked to a user_id."""
    stmt = select(Employee.full_name).where(Employee.user_id == user_id)
    name = (await session.execute(stmt)).scalar_one_or_none()
    return name or "Unknown"
