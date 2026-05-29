"""Project business logic — TSK-022 + TSK-022B + TSK-022C.

Hierarki: Project > Phase > Epic > Task > Subtask
- Phase: replace milestone, completion → trigger Finance untuk invoice termin.
- Epic: grouping di dalam phase.
- Task: kanban unit, slug Jira-style (auto-gen per project, e.g. WEB-123).
- Subtask: breakdown task, slug = {task_slug}.{counter}.
- Comments: markdown, di Task & Subtask.

Workflow:
- Project lifecycle: DRAFT → ACTIVE → COMPLETED/TERMINATED (atau ON_HOLD).
- Direktur Utama bisa override close kapan saja (with reason).
- Phase completion auto-trigger invoice notif via app.finance.service.
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
    PhaseStatus,
    Project,
    ProjectEpic,
    ProjectMember,
    ProjectPhase,
    ProjectStatus,
    ProjectSubtask,
    ProjectSubtaskComment,
    ProjectTask,
    ProjectTaskComment,
    ProjectType,
)
from app.project.schemas import (
    CommentCreate,
    CommentUpdate,
    EpicCreate,
    EpicUpdate,
    MemberAdd,
    PhaseCreate,
    PhaseUpdate,
    ProjectClose,
    ProjectCreate,
    ProjectUpdate,
    SubtaskCreate,
    SubtaskUpdate,
    TaskCreate,
    TaskUpdate,
)


# ─── Exceptions ────────────────────────────────────────────────────


class ProjectNotFoundError(Exception):
    pass


class PhaseNotFoundError(Exception):
    pass


class EpicNotFoundError(Exception):
    pass


class TaskNotFoundError(Exception):
    pass


class SubtaskNotFoundError(Exception):
    pass


class CommentNotFoundError(Exception):
    pass


class MemberNotFoundError(Exception):
    pass


class InvalidProjectStateError(Exception):
    pass


class DuplicateCodeError(Exception):
    pass


# Backward-compat alias agar import lama tidak break
MilestoneNotFoundError = PhaseNotFoundError


# ─── Projects ──────────────────────────────────────────────────────


async def list_projects(
    session: AsyncSession,
    project_type: ProjectType | None = None,
    status: ProjectStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Project], int]:
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


async def get_project(session: AsyncSession, project_id: UUID) -> Project:
    stmt = select(Project).where(
        Project.id == project_id, Project.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    p = result.scalar_one_or_none()
    if p is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")
    return p


async def create_project(session: AsyncSession, data: ProjectCreate) -> Project:
    p = Project(
        code=data.code,
        name=data.name,
        type=data.type,
        description=data.description,
        pm_user_id=data.pm_user_id,
        client_id=data.client_id,
        start_date=data.start_date,
        end_date=data.end_date,
        contract_value=data.contract_value,
        currency=data.currency,
        status=ProjectStatus.DRAFT,
        task_slug_counter=0,
    )
    session.add(p)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        if "projects_code_key" in str(e):
            raise DuplicateCodeError(f"Project code '{data.code}' sudah ada") from e
        raise
    await session.refresh(p)
    return p


async def update_project(
    session: AsyncSession, project_id: UUID, data: ProjectUpdate
) -> Project:
    p = await get_project(session, project_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    await session.commit()
    await session.refresh(p)
    return p


async def activate_project(session: AsyncSession, project_id: UUID) -> Project:
    p = await get_project(session, project_id)
    if p.status != ProjectStatus.DRAFT:
        raise InvalidProjectStateError(
            f"Project hanya bisa di-activate dari DRAFT (current: {p.status})"
        )
    p.status = ProjectStatus.ACTIVE
    await session.commit()
    await session.refresh(p)
    return p


async def close_project(
    session: AsyncSession,
    project_id: UUID,
    data: ProjectClose,
) -> Project:
    p = await get_project(session, project_id)
    if data.new_status not in (ProjectStatus.COMPLETED, ProjectStatus.TERMINATED):
        raise InvalidProjectStateError(
            "new_status harus COMPLETED atau TERMINATED"
        )
    p.status = data.new_status
    # Reason di-log via audit_log di router
    await session.commit()
    await session.refresh(p)
    return p


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
    await get_project(session, project_id)
    m = ProjectMember(
        project_id=project_id,
        employee_id=data.employee_id,
        role=data.role,
        allocation_pct=data.allocation_pct,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return m


async def remove_member(session: AsyncSession, member_id: UUID) -> None:
    stmt = select(ProjectMember).where(ProjectMember.id == member_id)
    result = await session.execute(stmt)
    m = result.scalar_one_or_none()
    if m is None:
        raise MemberNotFoundError(f"Member {member_id} not found")
    await session.delete(m)
    await session.commit()


# ─── Phase (replaces Milestone) ────────────────────────────────────


async def list_phases(session: AsyncSession, project_id: UUID) -> list[ProjectPhase]:
    stmt = (
        select(ProjectPhase)
        .where(
            ProjectPhase.project_id == project_id,
            ProjectPhase.deleted_at.is_(None),
        )
        .order_by(ProjectPhase.order_index, ProjectPhase.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_phase(session: AsyncSession, phase_id: UUID) -> ProjectPhase:
    stmt = select(ProjectPhase).where(
        ProjectPhase.id == phase_id, ProjectPhase.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    p = result.scalar_one_or_none()
    if p is None:
        raise PhaseNotFoundError(f"Phase {phase_id} not found")
    return p


async def create_phase(
    session: AsyncSession, project_id: UUID, data: PhaseCreate
) -> ProjectPhase:
    await get_project(session, project_id)
    phase = ProjectPhase(
        project_id=project_id,
        name=data.name,
        description=data.description,
        target_date=data.target_date,
        order_index=data.order_index,
        status=PhaseStatus.PLANNED,
    )
    session.add(phase)
    await session.commit()
    await session.refresh(phase)
    return phase


async def update_phase(
    session: AsyncSession,
    phase_id: UUID,
    data: PhaseUpdate,
) -> tuple[ProjectPhase, list]:
    """Update phase. Kalau marked complete (status=COMPLETED atau progress=100),
    auto-trigger Finance untuk invoice termin.

    Returns: (phase, triggered_invoices)
    """
    phase = await get_phase(session, phase_id)

    update_dict = data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(phase, field, value)

    is_newly_completed = (
        (
            phase.progress_pct == Decimal("100")
            or phase.status == PhaseStatus.COMPLETED
            or phase.completed_at is not None
        )
        and ("progress_pct" in update_dict
             or "status" in update_dict
             or "completed_at" in update_dict)
    )

    triggered = []
    if is_newly_completed:
        if phase.completed_at is None:
            phase.completed_at = date.today()
        if phase.status != PhaseStatus.COMPLETED:
            phase.status = PhaseStatus.COMPLETED
        # Trigger finance invoice notif (lazy import untuk avoid circular)
        from app.finance.service import trigger_invoices_on_phase_complete

        await session.commit()
        await session.refresh(phase)
        triggered = await trigger_invoices_on_phase_complete(session, phase.id)
    else:
        await session.commit()
        await session.refresh(phase)

    return phase, triggered


async def delete_phase(session: AsyncSession, phase_id: UUID) -> None:
    phase = await get_phase(session, phase_id)
    phase.deleted_at = datetime.now(UTC)
    await session.commit()


# Backward-compat aliases (deprecated) — supaya router lama tidak break
list_milestones = list_phases
get_milestone = get_phase
create_milestone = create_phase
update_milestone = update_phase


# ─── Epic ──────────────────────────────────────────────────────────


async def list_epics(
    session: AsyncSession, phase_id: UUID | None = None, project_id: UUID | None = None
) -> list[ProjectEpic]:
    stmt = select(ProjectEpic).where(ProjectEpic.deleted_at.is_(None))
    if phase_id is not None:
        stmt = stmt.where(ProjectEpic.phase_id == phase_id)
    if project_id is not None:
        stmt = stmt.where(ProjectEpic.project_id == project_id)
    stmt = stmt.order_by(ProjectEpic.order_index, ProjectEpic.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_epic(session: AsyncSession, epic_id: UUID) -> ProjectEpic:
    stmt = select(ProjectEpic).where(
        ProjectEpic.id == epic_id, ProjectEpic.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    e = result.scalar_one_or_none()
    if e is None:
        raise EpicNotFoundError(f"Epic {epic_id} not found")
    return e


async def create_epic(
    session: AsyncSession, phase_id: UUID, data: EpicCreate
) -> ProjectEpic:
    phase = await get_phase(session, phase_id)
    epic = ProjectEpic(
        phase_id=phase_id,
        project_id=phase.project_id,
        name=data.name,
        description=data.description,
        color=data.color,
        order_index=data.order_index,
        status="PLANNED",
    )
    session.add(epic)
    await session.commit()
    await session.refresh(epic)
    return epic


async def update_epic(
    session: AsyncSession, epic_id: UUID, data: EpicUpdate
) -> ProjectEpic:
    epic = await get_epic(session, epic_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(epic, field, value)
    await session.commit()
    await session.refresh(epic)
    return epic


async def delete_epic(session: AsyncSession, epic_id: UUID) -> None:
    epic = await get_epic(session, epic_id)
    epic.deleted_at = datetime.now(UTC)
    await session.commit()


# ─── Slug generator ────────────────────────────────────────────────


async def _next_task_slug(session: AsyncSession, project_id: UUID) -> str:
    """Generate slug Jira-style (PROJECT_CODE-counter) atomic via row-lock."""
    # SELECT FOR UPDATE supaya concurrent create tidak conflict
    stmt = (
        select(Project.code, Project.task_slug_counter)
        .where(Project.id == project_id)
        .with_for_update()
    )
    result = await session.execute(stmt)
    row = result.one_or_none()
    if row is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")
    code, counter = row
    new_counter = counter + 1
    # Update counter
    p = await session.get(Project, project_id)
    p.task_slug_counter = new_counter
    return f"{code}-{new_counter}"


async def _next_subtask_slug(session: AsyncSession, task_id: UUID) -> str:
    """Subtask slug = {task_slug}.{counter}, counter per task."""
    task = await session.get(ProjectTask, task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} not found")
    # Count existing subtasks (including soft-deleted, untuk avoid slug reuse)
    count_stmt = select(func.count(ProjectSubtask.id)).where(
        ProjectSubtask.task_id == task_id
    )
    count = int((await session.execute(count_stmt)).scalar_one())
    return f"{task.slug}.{count + 1}"


# ─── Tasks ─────────────────────────────────────────────────────────


async def list_tasks(
    session: AsyncSession,
    project_id: UUID,
    epic_id: UUID | None = None,
    status_filter: str | None = None,
) -> list[ProjectTask]:
    stmt = select(ProjectTask).where(
        ProjectTask.project_id == project_id,
        ProjectTask.deleted_at.is_(None),
    )
    if epic_id is not None:
        stmt = stmt.where(ProjectTask.epic_id == epic_id)
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

    slug = await _next_task_slug(session, project_id)

    task = ProjectTask(
        project_id=project_id,
        epic_id=data.epic_id,
        slug=slug,
        title=data.title,
        description=data.description,
        assignee_id=data.assignee_id,
        status=data.status,
        priority=data.priority,
        story_points=data.story_points,
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


# ─── Subtasks ──────────────────────────────────────────────────────


async def list_subtasks(session: AsyncSession, task_id: UUID) -> list[ProjectSubtask]:
    stmt = (
        select(ProjectSubtask)
        .where(
            ProjectSubtask.task_id == task_id,
            ProjectSubtask.deleted_at.is_(None),
        )
        .order_by(ProjectSubtask.order_index, ProjectSubtask.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_subtask(session: AsyncSession, subtask_id: UUID) -> ProjectSubtask:
    stmt = select(ProjectSubtask).where(
        ProjectSubtask.id == subtask_id, ProjectSubtask.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    s = result.scalar_one_or_none()
    if s is None:
        raise SubtaskNotFoundError(f"Subtask {subtask_id} not found")
    return s


async def create_subtask(
    session: AsyncSession, task_id: UUID, data: SubtaskCreate
) -> ProjectSubtask:
    await get_task(session, task_id)
    slug = await _next_subtask_slug(session, task_id)

    sub = ProjectSubtask(
        task_id=task_id,
        slug=slug,
        title=data.title,
        description=data.description,
        assignee_id=data.assignee_id,
        status=data.status,
        story_points=data.story_points,
        due_date=data.due_date,
        order_index=data.order_index,
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    return sub


async def update_subtask(
    session: AsyncSession, subtask_id: UUID, data: SubtaskUpdate
) -> ProjectSubtask:
    sub = await get_subtask(session, subtask_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(sub, field, value)
    await session.commit()
    await session.refresh(sub)
    return sub


async def delete_subtask(session: AsyncSession, subtask_id: UUID) -> None:
    sub = await get_subtask(session, subtask_id)
    sub.deleted_at = datetime.now(UTC)
    await session.commit()


# ─── Comments ──────────────────────────────────────────────────────


async def list_task_comments(
    session: AsyncSession, task_id: UUID
) -> list[ProjectTaskComment]:
    stmt = (
        select(ProjectTaskComment)
        .where(
            ProjectTaskComment.task_id == task_id,
            ProjectTaskComment.deleted_at.is_(None),
        )
        .order_by(ProjectTaskComment.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_task_comment(
    session: AsyncSession,
    task_id: UUID,
    author_user_id: UUID,
    data: CommentCreate,
) -> ProjectTaskComment:
    await get_task(session, task_id)
    c = ProjectTaskComment(
        task_id=task_id,
        author_user_id=author_user_id,
        body=data.body,
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


async def update_task_comment(
    session: AsyncSession,
    comment_id: UUID,
    author_user_id: UUID,
    data: CommentUpdate,
) -> ProjectTaskComment:
    stmt = select(ProjectTaskComment).where(
        ProjectTaskComment.id == comment_id,
        ProjectTaskComment.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    c = result.scalar_one_or_none()
    if c is None:
        raise CommentNotFoundError(f"Comment {comment_id} not found")
    if c.author_user_id != author_user_id:
        raise InvalidProjectStateError("Hanya author yang bisa edit comment")
    c.body = data.body
    await session.commit()
    await session.refresh(c)
    return c


async def delete_task_comment(
    session: AsyncSession, comment_id: UUID, author_user_id: UUID
) -> None:
    stmt = select(ProjectTaskComment).where(
        ProjectTaskComment.id == comment_id,
        ProjectTaskComment.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    c = result.scalar_one_or_none()
    if c is None:
        raise CommentNotFoundError(f"Comment {comment_id} not found")
    if c.author_user_id != author_user_id:
        raise InvalidProjectStateError("Hanya author yang bisa hapus comment")
    c.deleted_at = datetime.now(UTC)
    await session.commit()


async def list_subtask_comments(
    session: AsyncSession, subtask_id: UUID
) -> list[ProjectSubtaskComment]:
    stmt = (
        select(ProjectSubtaskComment)
        .where(
            ProjectSubtaskComment.subtask_id == subtask_id,
            ProjectSubtaskComment.deleted_at.is_(None),
        )
        .order_by(ProjectSubtaskComment.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_subtask_comment(
    session: AsyncSession,
    subtask_id: UUID,
    author_user_id: UUID,
    data: CommentCreate,
) -> ProjectSubtaskComment:
    await get_subtask(session, subtask_id)
    c = ProjectSubtaskComment(
        subtask_id=subtask_id,
        author_user_id=author_user_id,
        body=data.body,
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


async def update_subtask_comment(
    session: AsyncSession,
    comment_id: UUID,
    author_user_id: UUID,
    data: CommentUpdate,
) -> ProjectSubtaskComment:
    stmt = select(ProjectSubtaskComment).where(
        ProjectSubtaskComment.id == comment_id,
        ProjectSubtaskComment.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    c = result.scalar_one_or_none()
    if c is None:
        raise CommentNotFoundError(f"Comment {comment_id} not found")
    if c.author_user_id != author_user_id:
        raise InvalidProjectStateError("Hanya author yang bisa edit comment")
    c.body = data.body
    await session.commit()
    await session.refresh(c)
    return c


async def delete_subtask_comment(
    session: AsyncSession, comment_id: UUID, author_user_id: UUID
) -> None:
    stmt = select(ProjectSubtaskComment).where(
        ProjectSubtaskComment.id == comment_id,
        ProjectSubtaskComment.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    c = result.scalar_one_or_none()
    if c is None:
        raise CommentNotFoundError(f"Comment {comment_id} not found")
    if c.author_user_id != author_user_id:
        raise InvalidProjectStateError("Hanya author yang bisa hapus comment")
    c.deleted_at = datetime.now(UTC)
    await session.commit()


# ─── Helpers ───────────────────────────────────────────────────────


def calc_total_pages(total: int, page_size: int) -> int:
    if total == 0:
        return 0
    return math.ceil(total / page_size)


async def compute_overall_progress(
    session: AsyncSession, project_id: UUID
) -> Decimal | None:
    """Average phase progress_pct."""
    stmt = select(func.avg(ProjectPhase.progress_pct)).where(
        ProjectPhase.project_id == project_id,
        ProjectPhase.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    avg = result.scalar_one_or_none()
    return Decimal(str(avg)) if avg is not None else None


async def count_completed_phases(
    session: AsyncSession, project_id: UUID
) -> int:
    stmt = select(func.count(ProjectPhase.id)).where(
        ProjectPhase.project_id == project_id,
        ProjectPhase.deleted_at.is_(None),
        ProjectPhase.completed_at.is_not(None),
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def count_total_phases(session: AsyncSession, project_id: UUID) -> int:
    stmt = select(func.count(ProjectPhase.id)).where(
        ProjectPhase.project_id == project_id,
        ProjectPhase.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())


# Backward-compat aliases
count_completed_milestones = count_completed_phases
count_total_milestones = count_total_phases


async def count_members(session: AsyncSession, project_id: UUID) -> int:
    stmt = select(func.count(ProjectMember.id)).where(
        ProjectMember.project_id == project_id
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def count_subtasks(
    session: AsyncSession, task_id: UUID, completed_only: bool = False
) -> int:
    stmt = select(func.count(ProjectSubtask.id)).where(
        ProjectSubtask.task_id == task_id,
        ProjectSubtask.deleted_at.is_(None),
    )
    if completed_only:
        stmt = stmt.where(ProjectSubtask.status == "DONE")
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def count_task_comments(session: AsyncSession, task_id: UUID) -> int:
    stmt = select(func.count(ProjectTaskComment.id)).where(
        ProjectTaskComment.task_id == task_id,
        ProjectTaskComment.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def count_subtask_comments(session: AsyncSession, subtask_id: UUID) -> int:
    stmt = select(func.count(ProjectSubtaskComment.id)).where(
        ProjectSubtaskComment.subtask_id == subtask_id,
        ProjectSubtaskComment.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def count_tasks_in_epic(
    session: AsyncSession, epic_id: UUID, completed_only: bool = False
) -> int:
    stmt = select(func.count(ProjectTask.id)).where(
        ProjectTask.epic_id == epic_id,
        ProjectTask.deleted_at.is_(None),
    )
    if completed_only:
        stmt = stmt.where(ProjectTask.status == "DONE")
    result = await session.execute(stmt)
    return int(result.scalar_one())
