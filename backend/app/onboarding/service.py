"""Onboarding business logic — TSK-016.

Workflow:
1. HR/Manager bikin OnboardingTemplate (sekali per dept/level)
2. Saat employee baru hire → assign template (auto-create TaskCompletion per task)
3. Tasks di-mark DONE/SKIPPED/BLOCKED secara individual
4. Progress percent dihitung otomatis (done_required / total_required)
5. Saat semua required task DONE → assignment auto-complete
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.onboarding.models import (
    AssignmentStatus,
    OnboardingAssignment,
    OnboardingTask,
    OnboardingTemplate,
    TaskCategory,
    TaskCompletion,
    TaskCompletionStatus,
)
from app.onboarding.schemas import (
    AssignmentCreate,
    AssignmentUpdate,
    TaskCompletionUpdate,
    TaskCreate,
    TaskUpdate,
    TemplateCreate,
    TemplateUpdate,
)
from app.organization.models import Department, Employee


# ─── Exceptions ────────────────────────────────────────────────────


class TemplateNotFoundError(Exception):
    pass


class TaskNotFoundError(Exception):
    pass


class AssignmentNotFoundError(Exception):
    pass


class CompletionNotFoundError(Exception):
    pass


class AlreadyAssignedError(Exception):
    pass


class InvalidOnboardingStateError(Exception):
    pass


# ─── Template CRUD ─────────────────────────────────────────────────


async def get_template(session: AsyncSession, template_id: UUID) -> OnboardingTemplate:
    stmt = (
        select(OnboardingTemplate)
        .where(OnboardingTemplate.id == template_id, OnboardingTemplate.deleted_at.is_(None))
        .options(selectinload(OnboardingTemplate.tasks))
    )
    result = await session.execute(stmt)
    t = result.scalar_one_or_none()
    if t is None:
        raise TemplateNotFoundError(f"Template {template_id} not found")
    return t


async def list_templates(
    session: AsyncSession,
    department_id: UUID | None = None,
    is_active: bool | None = None,
) -> list[OnboardingTemplate]:
    stmt = (
        select(OnboardingTemplate)
        .where(OnboardingTemplate.deleted_at.is_(None))
        .options(selectinload(OnboardingTemplate.tasks))
        .order_by(OnboardingTemplate.name)
    )
    if department_id is not None:
        stmt = stmt.where(OnboardingTemplate.target_department_id == department_id)
    if is_active is not None:
        stmt = stmt.where(OnboardingTemplate.is_active == is_active)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_template(
    session: AsyncSession, data: TemplateCreate
) -> OnboardingTemplate:
    """Create template + initial tasks dalam 1 transaction."""
    if data.target_department_id is not None:
        dept = await session.execute(
            select(Department).where(Department.id == data.target_department_id)
        )
        if dept.scalar_one_or_none() is None:
            raise InvalidOnboardingStateError(
                f"Department {data.target_department_id} not found"
            )

    template = OnboardingTemplate(
        name=data.name,
        description=data.description,
        target_department_id=data.target_department_id,
        target_position_level=data.target_position_level,
        estimated_duration_days=data.estimated_duration_days,
    )
    session.add(template)
    await session.flush()

    # Auto-set order_index untuk task yang belum di-set
    for idx, task_data in enumerate(data.tasks):
        task = OnboardingTask(
            template_id=template.id,
            **task_data.model_dump(exclude={"order_index"}),
            order_index=task_data.order_index if task_data.order_index else idx,
        )
        session.add(task)

    await session.commit()
    await session.refresh(template, attribute_names=["tasks"])
    return template


async def update_template(
    session: AsyncSession, template_id: UUID, data: TemplateUpdate
) -> OnboardingTemplate:
    template = await get_template(session, template_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    await session.commit()
    await session.refresh(template)
    return template


async def add_task_to_template(
    session: AsyncSession, template_id: UUID, data: TaskCreate
) -> OnboardingTask:
    template = await get_template(session, template_id)
    # Auto order_index = max + 1 kalau belum di-set
    if data.order_index == 0:
        max_order = max((t.order_index for t in template.tasks), default=-1)
        order_idx = max_order + 1
    else:
        order_idx = data.order_index

    task = OnboardingTask(
        template_id=template.id,
        **data.model_dump(exclude={"order_index"}),
        order_index=order_idx,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def update_task(
    session: AsyncSession, task_id: UUID, data: TaskUpdate
) -> OnboardingTask:
    stmt = select(OnboardingTask).where(OnboardingTask.id == task_id)
    result = await session.execute(stmt)
    task = result.scalar_one_or_none()
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await session.commit()
    await session.refresh(task)
    return task


async def delete_task(session: AsyncSession, task_id: UUID) -> None:
    stmt = select(OnboardingTask).where(OnboardingTask.id == task_id)
    result = await session.execute(stmt)
    task = result.scalar_one_or_none()
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} not found")
    await session.delete(task)
    await session.commit()


# ─── Assignment ────────────────────────────────────────────────────


async def get_assignment(
    session: AsyncSession, assignment_id: UUID
) -> OnboardingAssignment:
    stmt = (
        select(OnboardingAssignment)
        .where(OnboardingAssignment.id == assignment_id)
        .options(
            selectinload(OnboardingAssignment.template).selectinload(OnboardingTemplate.tasks),
            selectinload(OnboardingAssignment.completions).selectinload(TaskCompletion.task),
        )
    )
    result = await session.execute(stmt)
    a = result.scalar_one_or_none()
    if a is None:
        raise AssignmentNotFoundError(f"Assignment {assignment_id} not found")
    return a


async def list_assignments(
    session: AsyncSession,
    employee_id: UUID | None = None,
    status: AssignmentStatus | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[OnboardingAssignment], int]:
    page = max(page, 1)
    page_size = max(min(page_size, 200), 1)

    base = select(OnboardingAssignment)
    if employee_id is not None:
        base = base.where(OnboardingAssignment.employee_id == employee_id)
    if status is not None:
        base = base.where(OnboardingAssignment.status == status)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    stmt = (
        base.options(
            # Eager load template.tasks juga supaya calculate_progress
            # tidak trigger lazy load di async context (crash di FastAPI)
            selectinload(OnboardingAssignment.template).selectinload(
                OnboardingTemplate.tasks
            ),
            selectinload(OnboardingAssignment.completions),
        )
        .order_by(OnboardingAssignment.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def create_assignment(
    session: AsyncSession,
    data: AssignmentCreate,
    assigned_by_user_id: UUID,
) -> OnboardingAssignment:
    """Assign template ke employee + auto-create TaskCompletion per task."""
    # Validate employee exists
    emp_stmt = select(Employee).where(Employee.id == data.employee_id, Employee.deleted_at.is_(None))
    emp_result = await session.execute(emp_stmt)
    emp = emp_result.scalar_one_or_none()
    if emp is None:
        raise InvalidOnboardingStateError(f"Employee {data.employee_id} not found")

    template = await get_template(session, data.template_id)

    # Check uniqueness (1 employee bisa di-assign template SAMA cuma sekali)
    existing = await session.execute(
        select(OnboardingAssignment).where(
            OnboardingAssignment.employee_id == data.employee_id,
            OnboardingAssignment.template_id == data.template_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise AlreadyAssignedError(
            f"Employee sudah punya assignment untuk template '{template.name}'"
        )

    started_at = data.started_at or date.today()
    target_completion = data.target_completion_date or (
        started_at + timedelta(days=template.estimated_duration_days)
    )

    assignment = OnboardingAssignment(
        employee_id=data.employee_id,
        template_id=template.id,
        status=AssignmentStatus.IN_PROGRESS,
        started_at=started_at,
        target_completion_date=target_completion,
        assigned_by_user_id=assigned_by_user_id,
        notes=data.notes,
    )
    session.add(assignment)
    await session.flush()

    # Auto-create TaskCompletion per template task
    for task in template.tasks:
        completion = TaskCompletion(
            assignment_id=assignment.id,
            task_id=task.id,
            status=TaskCompletionStatus.PENDING,
            due_date=started_at + timedelta(days=task.default_due_offset_days),
        )
        session.add(completion)

    await session.commit()
    await session.refresh(
        assignment, attribute_names=["template", "completions"]
    )
    return assignment


async def update_assignment(
    session: AsyncSession, assignment_id: UUID, data: AssignmentUpdate
) -> OnboardingAssignment:
    assignment = await get_assignment(session, assignment_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(assignment, field, value)
    if data.status == AssignmentStatus.COMPLETED and assignment.completed_at is None:
        assignment.completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(assignment)
    return assignment


# ─── TaskCompletion ────────────────────────────────────────────────


async def update_completion(
    session: AsyncSession,
    completion_id: UUID,
    data: TaskCompletionUpdate,
    completed_by_user_id: UUID,
) -> TaskCompletion:
    stmt = select(TaskCompletion).where(TaskCompletion.id == completion_id)
    result = await session.execute(stmt)
    completion = result.scalar_one_or_none()
    if completion is None:
        raise CompletionNotFoundError(f"Completion {completion_id} not found")

    if data.status == TaskCompletionStatus.BLOCKED and not data.blocker_reason:
        raise InvalidOnboardingStateError("Blocker reason wajib diisi saat status=BLOCKED")

    completion.status = data.status
    if data.notes is not None:
        completion.notes = data.notes
    if data.blocker_reason is not None:
        completion.blocker_reason = data.blocker_reason

    if data.status == TaskCompletionStatus.DONE:
        completion.completed_at = datetime.now(UTC)
        completion.completed_by_user_id = completed_by_user_id
    elif data.status != TaskCompletionStatus.DONE and completion.completed_at is not None:
        # Reverse: kalau di-DONE lalu di-revert
        completion.completed_at = None
        completion.completed_by_user_id = None

    await session.commit()

    # Auto-complete assignment kalau semua required tasks DONE
    await _maybe_complete_assignment(session, completion.assignment_id)

    await session.refresh(completion)
    return completion


async def _maybe_complete_assignment(session: AsyncSession, assignment_id: UUID) -> None:
    """Cek apakah semua required task sudah DONE, jika ya → mark assignment COMPLETED."""
    assignment = await get_assignment(session, assignment_id)

    required_task_ids = {t.id for t in assignment.template.tasks if t.is_required}
    done_required = sum(
        1
        for c in assignment.completions
        if c.task_id in required_task_ids and c.status == TaskCompletionStatus.DONE
    )

    if (
        len(required_task_ids) > 0
        and done_required == len(required_task_ids)
        and assignment.status != AssignmentStatus.COMPLETED
    ):
        assignment.status = AssignmentStatus.COMPLETED
        assignment.completed_at = datetime.now(UTC)
        await session.commit()


# ─── Helpers untuk router ──────────────────────────────────────────


def calculate_progress(assignment: OnboardingAssignment) -> tuple[int, int, int]:
    """Returns (total_tasks, completed_tasks, progress_percent).

    Required-only counting: optional tasks tidak masuk denominator.
    """
    required_completions = [
        c
        for c in assignment.completions
        if any(t.id == c.task_id and t.is_required for t in assignment.template.tasks)
    ]
    total = len(required_completions)
    done = sum(1 for c in required_completions if c.status == TaskCompletionStatus.DONE)
    pct = int((done / total) * 100) if total > 0 else 0
    return total, done, pct


def group_completions_by_category(
    assignment: OnboardingAssignment,
) -> dict[str, list[TaskCompletion]]:
    """Grouping TaskCompletion by task.category untuk UI checklist.

    Note: task.category dari DB bisa berupa str (kalau column String) atau
    TaskCategory enum (kalau ada explicit converter). Handle keduanya.
    """
    grouped: dict[str, list[TaskCompletion]] = defaultdict(list)
    task_by_id = {t.id: t for t in assignment.template.tasks}
    sorted_completions = sorted(
        assignment.completions,
        key=lambda c: (
            task_by_id.get(c.task_id).order_index if task_by_id.get(c.task_id) else 999,
        ),
    )
    for completion in sorted_completions:
        task = task_by_id.get(completion.task_id)
        if task is None:
            cat = TaskCategory.OTHER.value
        else:
            # Handle both string (raw from DB) dan enum instance
            cat = task.category.value if hasattr(task.category, "value") else str(task.category)
        grouped[cat].append(completion)
    return dict(grouped)


def calc_total_pages(total: int, page_size: int) -> int:
    if total == 0:
        return 0
    return math.ceil(total / page_size)
