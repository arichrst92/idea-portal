"""Project business logic — TSK-022, refactored TSK-022C.

Workflow:
- Project lifecycle: DRAFT → ACTIVE → COMPLETED/TERMINATED (atau ON_HOLD)
- Direktur Utama bisa override close kapan saja (with reason)
- Milestone: track progress; (auto-notify Finance via invoice trigger akan
  di-re-aktifkan di TSK-022B via Phase → app.finance.service)
- Task: simple kanban (BACKLOG → TODO → IN_PROGRESS → IN_REVIEW → DONE/BLOCKED)

TSK-022C (2026-05-29): semua logic invoice di-pindah ke app/finance/service.py.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.project.models import (
    Project,
    ProjectMember,
    ProjectMilestone,
    ProjectStatus,
    ProjectTask,
    ProjectType,
)
from app.project.schemas import (
    MemberAdd,
    MilestoneCreate,
    MilestoneUpdate,
    ProjectClose,
    ProjectCreate,
    ProjectUpdate,
    TaskCreate,
    TaskUpdate,
)


# ─── Exceptions ────────────────────────────────────────────────────


class ProjectNotFoundError(Exception):
    pass


class MilestoneNotFoundError(Exception):
    pass


class TaskNotFoundError(Exception):
    pass


class MemberNotFoundError(Exception):
    pass


class InvalidProjectStateError(Exception):
    pass


class DuplicateCodeError(Exception):
    pass


# ─── Project CRUD ──────────────────────────────────────────────────


async def get_project(session: AsyncSession, project_id: UUID) -> Project:
    stmt = select(Project).where(
        Project.id == project_id, Project.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    p = result.scalar_one_or_none()
    if p is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")
    return p


async def list_projects(
    session: AsyncSession,
    project_type: ProjectType | None = None,
    status: ProjectStatus | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Project], int]:
    page = max(page, 1)
    page_size = max(min(page_size, 200), 1)

    base = select(Project).where(Project.deleted_at.is_(None))
    if project_type is not None:
        base = base.where(Project.type == project_type)
    if status is not None:
        base = base.where(Project.status == status)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    stmt = (
        base.order_by(Project.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def create_project(session: AsyncSession, data: ProjectCreate) -> Project:
    """Create project sebagai DRAFT."""
    project = Project(
        code=data.code,
        name=data.name,
        type=data.type,
        status=ProjectStatus.DRAFT,
        description=data.description,
        pm_user_id=data.pm_user_id,
        client_id=data.client_id,
        start_date=data.start_date,
        end_date=data.end_date,
        contract_value=data.contract_value,
        currency=data.currency,
    )
    session.add(project)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        if "projects_code_key" in str(e):
            raise DuplicateCodeError(f"Project code '{data.code}' sudah ada") from e
        raise
    await session.refresh(project)
    return project


async def update_project(
    session: AsyncSession, project_id: UUID, data: ProjectUpdate
) -> Project:
    project = await get_project(session, project_id)
    if project.status in {ProjectStatus.COMPLETED, ProjectStatus.TERMINATED}:
        raise InvalidProjectStateError(
            f"Project status {project.status} — tidak bisa edit"
        )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await session.commit()
    await session.refresh(project)
    return project


async def activate_project(session: AsyncSession, project_id: UUID) -> Project:
    """DRAFT → ACTIVE."""
    project = await get_project(session, project_id)
    if project.status != ProjectStatus.DRAFT:
        raise InvalidProjectStateError(
            f"Project status {project.status} — hanya DRAFT yang bisa di-activate"
        )
    project.status = ProjectStatus.ACTIVE
    await session.commit()
    await session.refresh(project)
    return project


async def close_project(
    session: AsyncSession,
    project_id: UUID,
    data: ProjectClose,
    is_executive_override: bool = False,
) -> Project:
    """Close project ke COMPLETED/TERMINATED.

    Per knowledge.md sec.13: Direktur Utama bisa override kapan saja
    dengan input alasan.
    """
    project = await get_project(session, project_id)

    if data.new_status not in {ProjectStatus.COMPLETED, ProjectStatus.TERMINATED}:
        raise InvalidProjectStateError(
            "new_status harus COMPLETED atau TERMINATED"
        )

    if project.status in {ProjectStatus.COMPLETED, ProjectStatus.TERMINATED}:
        raise InvalidProjectStateError(
            f"Project sudah {project.status}"
        )

    # Non-executive hanya bisa close project yang sudah ACTIVE
    if not is_executive_override and project.status != ProjectStatus.ACTIVE:
        raise InvalidProjectStateError(
            f"Project status {project.status} — hanya ACTIVE yang bisa di-close "
            "(atau pakai Direktur override)"
        )

    project.status = data.new_status
    # Append reason ke description (audit trail di audit_log juga)
    closing_note = f"\n\n[CLOSED {datetime.now(UTC).date()}]: {data.reason}"
    project.description = (project.description or "") + closing_note
    await session.commit()
    await session.refresh(project)
    return project


# ─── Members ───────────────────────────────────────────────────────


async def list_members(session: AsyncSession, project_id: UUID) -> list[ProjectMember]:
    stmt = (
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.start_date.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def add_member(
    session: AsyncSession, project_id: UUID, data: MemberAdd
) -> ProjectMember:
    # Validate project exists + active
    project = await get_project(session, project_id)
    if project.status in {ProjectStatus.COMPLETED, ProjectStatus.TERMINATED}:
        raise InvalidProjectStateError(
            f"Project status {project.status} — tidak bisa tambah member"
        )

    member = ProjectMember(
        project_id=project_id,
        employee_id=data.employee_id,
        role=data.role,
        allocation_pct=data.allocation_pct,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    session.add(member)
    await session.commit()
    await session.refresh(member)
    return member


async def remove_member(session: AsyncSession, member_id: UUID) -> None:
    stmt = select(ProjectMember).where(ProjectMember.id == member_id)
    result = await session.execute(stmt)
    member = result.scalar_one_or_none()
    if member is None:
        raise MemberNotFoundError(f"Member {member_id} not found")
    await session.delete(member)
    await session.commit()


# ─── Milestones ────────────────────────────────────────────────────


async def list_milestones(
    session: AsyncSession, project_id: UUID
) -> list[ProjectMilestone]:
    stmt = (
        select(ProjectMilestone)
        .where(ProjectMilestone.project_id == project_id)
        .order_by(ProjectMilestone.target_date)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_milestone(session: AsyncSession, milestone_id: UUID) -> ProjectMilestone:
    stmt = select(ProjectMilestone).where(ProjectMilestone.id == milestone_id)
    result = await session.execute(stmt)
    m = result.scalar_one_or_none()
    if m is None:
        raise MilestoneNotFoundError(f"Milestone {milestone_id} not found")
    return m


async def create_milestone(
    session: AsyncSession, project_id: UUID, data: MilestoneCreate
) -> ProjectMilestone:
    await get_project(session, project_id)  # validate exists
    milestone = ProjectMilestone(
        project_id=project_id,
        name=data.name,
        target_date=data.target_date,
        progress_pct=Decimal("0"),
    )
    session.add(milestone)
    await session.commit()
    await session.refresh(milestone)
    return milestone


async def update_milestone(
    session: AsyncSession,
    milestone_id: UUID,
    data: MilestoneUpdate,
) -> tuple[ProjectMilestone, list]:
    """Update milestone. Kalau marked complete (progress=100 atau completed_at),
    set completed_at.

    TSK-022C: invoice trigger di-pindah ke finance domain. Untuk sementara
    return triggered = [] (empty). Akan di-re-aktivasi di TSK-022B saat
    Phase menggantikan Milestone.

    Returns: (milestone, triggered_invoices [always empty for now])
    """
    milestone = await get_milestone(session, milestone_id)

    update_dict = data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(milestone, field, value)

    is_newly_completed = (
        (milestone.progress_pct == Decimal("100") or milestone.completed_at is not None)
        and "progress_pct" in update_dict
        or "completed_at" in update_dict
    )
    if is_newly_completed and milestone.completed_at is None:
        milestone.completed_at = date.today()

    await session.commit()
    await session.refresh(milestone)
    return milestone, []


# ─── Tasks ─────────────────────────────────────────────────────────


async def list_tasks(
    session: AsyncSession,
    project_id: UUID,
    status_filter: str | None = None,
) -> list[ProjectTask]:
    stmt = select(ProjectTask).where(
        ProjectTask.project_id == project_id,
        ProjectTask.deleted_at.is_(None),
    )
    if status_filter:
        stmt = stmt.where(ProjectTask.status == status_filter)
    stmt = stmt.order_by(ProjectTask.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_task(session: AsyncSession, task_id: UUID) -> ProjectTask:
    stmt = select(ProjectTask).where(
        ProjectTask.id == task_id, ProjectTask.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    t = result.scalar_one_or_none()
    if t is None:
        raise TaskNotFoundError(f"Task {task_id} not found")
    return t


async def create_task(
    session: AsyncSession, project_id: UUID, data: TaskCreate
) -> ProjectTask:
    await get_project(session, project_id)  # validate
    task = ProjectTask(
        project_id=project_id,
        milestone_id=data.milestone_id,
        title=data.title,
        description=data.description,
        assignee_id=data.assignee_id,
        status=data.status,
        priority=data.priority,
        due_date=data.due_date,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def update_task(
    session: AsyncSession, task_id: UUID, data: TaskUpdate
) -> ProjectTask:
    task = await get_task(session, task_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await session.commit()
    await session.refresh(task)
    return task


async def delete_task(session: AsyncSession, task_id: UUID) -> None:
    task = await get_task(session, task_id)
    task.deleted_at = datetime.now(UTC)
    await session.commit()


# ─── Invoices ──────────────────────────────────────────────────────
# REMOVED (TSK-022C). Pindah ke app.finance.service.
# Lihat: app.finance.service.list_invoices / create_invoice / update_invoice


# ─── Helpers ───────────────────────────────────────────────────────


def calc_total_pages(total: int, page_size: int) -> int:
    if total == 0:
        return 0
    return math.ceil(total / page_size)


async def compute_overall_progress(
    session: AsyncSession, project_id: UUID
) -> Decimal | None:
    """Average milestone progress_pct."""
    stmt = select(func.avg(ProjectMilestone.progress_pct)).where(
        ProjectMilestone.project_id == project_id
    )
    result = await session.execute(stmt)
    avg = result.scalar_one_or_none()
    return Decimal(str(avg)) if avg is not None else None


async def count_completed_milestones(
    session: AsyncSession, project_id: UUID
) -> int:
    stmt = select(func.count(ProjectMilestone.id)).where(
        ProjectMilestone.project_id == project_id,
        ProjectMilestone.completed_at.is_not(None),
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def count_total_milestones(session: AsyncSession, project_id: UUID) -> int:
    stmt = select(func.count(ProjectMilestone.id)).where(
        ProjectMilestone.project_id == project_id
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def count_members(session: AsyncSession, project_id: UUID) -> int:
    stmt = select(func.count(ProjectMember.id)).where(
        ProjectMember.project_id == project_id
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())
