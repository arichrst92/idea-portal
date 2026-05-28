"""Onboarding router — TSK-016.

Endpoints di /api/v1:
- /onboarding/templates                          — list, create, detail, update
- /onboarding/templates/{id}/tasks               — add task to template
- /onboarding/tasks/{id}                         — update/delete task
- /onboarding/assignments                        — list, create, get, update
- /onboarding/assignments/{id}                   — detail dengan progress + tasks grouped
- /onboarding/completions/{id}                   — update status (DONE/SKIPPED/BLOCKED)

RBAC:
- onboarding.view → semua authenticated (filtered)
- onboarding.edit → HR (Manager+ untuk dept-nya, GM+ all)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.core.audit import audit_log
from app.core.deps import CurrentUser, DBSession, require_permission
from app.identity.models import User
from app.onboarding import service
from app.onboarding.models import AssignmentStatus, OnboardingTemplate, TaskCompletion
from app.onboarding.schemas import (
    AssignmentCreate,
    AssignmentDetailOut,
    AssignmentListItem,
    AssignmentListResponse,
    AssignmentUpdate,
    TaskCompletionOut,
    TaskCompletionUpdate,
    TaskCreate,
    TaskOut,
    TaskUpdate,
    TemplateCreate,
    TemplateDetailOut,
    TemplateOut,
    TemplateUpdate,
)
from app.onboarding.service import (
    AlreadyAssignedError,
    AssignmentNotFoundError,
    CompletionNotFoundError,
    InvalidOnboardingStateError,
    TaskNotFoundError,
    TemplateNotFoundError,
)
from app.organization.models import Department, Employee

router = APIRouter(tags=["onboarding"])


# ─── Helpers ───────────────────────────────────────────────────────


async def _build_template_out(
    session, template: OnboardingTemplate, include_tasks: bool = False
) -> TemplateOut | TemplateDetailOut:
    dept_name = None
    if template.target_department_id:
        d = await session.execute(
            select(Department.name).where(Department.id == template.target_department_id)
        )
        dept_name = d.scalar_one_or_none()

    from app.onboarding.models import OnboardingAssignment

    assignment_count_stmt = select(
        select(OnboardingAssignment)
        .where(OnboardingAssignment.template_id == template.id)
        .subquery()
        .c.id.label("id")
    )
    count_result = await session.execute(
        select(OnboardingAssignment).where(OnboardingAssignment.template_id == template.id)
    )
    assignment_count = len(list(count_result.scalars().all()))

    base_data = {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "target_department_id": template.target_department_id,
        "target_position_level": template.target_position_level,
        "estimated_duration_days": template.estimated_duration_days,
        "is_active": template.is_active,
        "created_at": template.created_at,
        "department_name": dept_name,
        "task_count": len(template.tasks),
        "assignment_count": assignment_count,
    }

    if include_tasks:
        tasks_out = [TaskOut.model_validate(t) for t in template.tasks]
        return TemplateDetailOut(**base_data, tasks=tasks_out)

    return TemplateOut(**base_data)


async def _build_completion_out(
    completion: TaskCompletion, task_by_id: dict
) -> TaskCompletionOut:
    task = task_by_id.get(completion.task_id)
    return TaskCompletionOut(
        id=completion.id,
        assignment_id=completion.assignment_id,
        task_id=completion.task_id,
        status=completion.status,
        due_date=completion.due_date,
        completed_at=completion.completed_at,
        completed_by_user_id=completion.completed_by_user_id,
        notes=completion.notes,
        blocker_reason=completion.blocker_reason,
        created_at=completion.created_at,
        updated_at=completion.updated_at,
        task_title=task.title if task else None,
        task_category=task.category if task else None,
        task_assigned_role=task.assigned_role if task else None,
        task_is_required=task.is_required if task else None,
        task_instructions=task.instructions if task else None,
        task_reference_url=task.reference_url if task else None,
    )


async def _build_assignment_out(
    session, assignment, *, detailed: bool = False
) -> AssignmentListItem | AssignmentDetailOut:
    # Lookup employee data
    emp_data = await session.execute(
        select(Employee.full_name, Employee.department_id, User.nik, Department.name)
        .join(User, Employee.user_id == User.id)
        .outerjoin(Department, Employee.department_id == Department.id)
        .where(Employee.id == assignment.employee_id)
    )
    row = emp_data.first()
    emp_name = row[0] if row else None
    emp_nik = row[2] if row else None
    emp_dept = row[3] if row else None

    template_name = assignment.template.name if assignment.template else None
    total, done, pct = service.calculate_progress(assignment)

    base = {
        "id": assignment.id,
        "employee_id": assignment.employee_id,
        "template_id": assignment.template_id,
        "status": assignment.status,
        "started_at": assignment.started_at,
        "target_completion_date": assignment.target_completion_date,
        "completed_at": assignment.completed_at,
        "employee_nik": emp_nik,
        "employee_name": emp_name,
        "employee_department": emp_dept,
        "template_name": template_name,
        "total_tasks": total,
        "completed_tasks": done,
        "progress_percent": pct,
    }

    if not detailed:
        return AssignmentListItem(**base)

    task_by_id = {t.id: t for t in assignment.template.tasks}
    grouped = service.group_completions_by_category(assignment)
    completions_by_cat = {
        cat: [await _build_completion_out(c, task_by_id) for c in items]
        for cat, items in grouped.items()
    }

    return AssignmentDetailOut(
        **base,
        assigned_by_user_id=assignment.assigned_by_user_id,
        notes=assignment.notes,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
        completions_by_category=completions_by_cat,
    )


# ─── Template endpoints ────────────────────────────────────────────


@router.get("/onboarding/templates", response_model=list[TemplateOut])
async def list_templates_endpoint(
    session: DBSession,
    _user=Depends(require_permission("onboarding.view")),
    department_id: UUID | None = Query(None),
    is_active: bool | None = Query(None),
) -> list[TemplateOut]:
    templates = await service.list_templates(
        session, department_id=department_id, is_active=is_active
    )
    return [await _build_template_out(session, t, include_tasks=False) for t in templates]


@router.post(
    "/onboarding/templates",
    response_model=TemplateDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_template_endpoint(
    request: Request,
    data: TemplateCreate,
    session: DBSession,
    user=Depends(require_permission("onboarding.edit")),
) -> TemplateDetailOut:
    try:
        template = await service.create_template(session, data)
    except InvalidOnboardingStateError as e:
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_INPUT", "message": str(e)}
        ) from e

    await audit_log(
        session=session,
        actor=user,
        action="ONBOARDING_TEMPLATE_CREATED",
        resource_type="onboarding_template",
        resource_id=str(template.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        after_state={"name": template.name, "task_count": len(template.tasks)},
    )
    return await _build_template_out(session, template, include_tasks=True)


@router.get("/onboarding/templates/{template_id}", response_model=TemplateDetailOut)
async def get_template_endpoint(
    template_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("onboarding.view")),
) -> TemplateDetailOut:
    try:
        template = await service.get_template(session, template_id)
    except TemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "TEMPLATE_NOT_FOUND", "message": str(e)}) from e
    return await _build_template_out(session, template, include_tasks=True)


@router.patch("/onboarding/templates/{template_id}", response_model=TemplateOut)
async def update_template_endpoint(
    request: Request,
    template_id: UUID,
    data: TemplateUpdate,
    session: DBSession,
    user=Depends(require_permission("onboarding.edit")),
) -> TemplateOut:
    try:
        template = await service.update_template(session, template_id, data)
    except TemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "TEMPLATE_NOT_FOUND", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="ONBOARDING_TEMPLATE_UPDATED",
        resource_type="onboarding_template",
        resource_id=str(template.id),
        ip_address=request.client.host if request.client else None,
        after_state=data.model_dump(exclude_unset=True),
    )
    return await _build_template_out(session, template, include_tasks=False)


@router.post(
    "/onboarding/templates/{template_id}/tasks",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_task_endpoint(
    template_id: UUID,
    data: TaskCreate,
    session: DBSession,
    _user=Depends(require_permission("onboarding.edit")),
) -> TaskOut:
    try:
        task = await service.add_task_to_template(session, template_id, data)
    except TemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "TEMPLATE_NOT_FOUND", "message": str(e)}) from e
    return TaskOut.model_validate(task)


@router.patch("/onboarding/tasks/{task_id}", response_model=TaskOut)
async def update_task_endpoint(
    task_id: UUID,
    data: TaskUpdate,
    session: DBSession,
    _user=Depends(require_permission("onboarding.edit")),
) -> TaskOut:
    try:
        task = await service.update_task(session, task_id, data)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": str(e)}) from e
    return TaskOut.model_validate(task)


@router.delete("/onboarding/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_endpoint(
    task_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("onboarding.edit")),
) -> None:
    try:
        await service.delete_task(session, task_id)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": str(e)}) from e


# ─── Assignment endpoints ──────────────────────────────────────────


@router.get("/onboarding/assignments", response_model=AssignmentListResponse)
async def list_assignments_endpoint(
    session: DBSession,
    _user=Depends(require_permission("onboarding.view")),
    employee_id: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> AssignmentListResponse:
    status_enum = AssignmentStatus(status_filter) if status_filter else None
    assignments, total = await service.list_assignments(
        session, employee_id=employee_id, status=status_enum, page=page, page_size=page_size
    )

    items = []
    for a in assignments:
        item = await _build_assignment_out(session, a, detailed=False)
        items.append(item)

    return AssignmentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=service.calc_total_pages(total, page_size),
    )


@router.post(
    "/onboarding/assignments",
    response_model=AssignmentDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_assignment_endpoint(
    request: Request,
    data: AssignmentCreate,
    session: DBSession,
    user=Depends(require_permission("onboarding.edit")),
) -> AssignmentDetailOut:
    try:
        assignment = await service.create_assignment(session, data, user.id)
    except (TemplateNotFoundError, AlreadyAssignedError, InvalidOnboardingStateError) as e:
        code = "INVALID_ASSIGNMENT"
        if isinstance(e, AlreadyAssignedError):
            code = "ALREADY_ASSIGNED"
        elif isinstance(e, TemplateNotFoundError):
            code = "TEMPLATE_NOT_FOUND"
        raise HTTPException(status_code=400, detail={"code": code, "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="ONBOARDING_ASSIGNED",
        resource_type="onboarding_assignment",
        resource_id=str(assignment.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        after_state={
            "employee_id": str(data.employee_id),
            "template_id": str(data.template_id),
        },
    )

    # Re-fetch dengan eager loading lengkap untuk detail response
    assignment = await service.get_assignment(session, assignment.id)
    return await _build_assignment_out(session, assignment, detailed=True)


@router.get(
    "/onboarding/assignments/{assignment_id}", response_model=AssignmentDetailOut
)
async def get_assignment_endpoint(
    assignment_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("onboarding.view")),
) -> AssignmentDetailOut:
    try:
        assignment = await service.get_assignment(session, assignment_id)
    except AssignmentNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "ASSIGNMENT_NOT_FOUND", "message": str(e)}) from e
    return await _build_assignment_out(session, assignment, detailed=True)


@router.patch("/onboarding/assignments/{assignment_id}", response_model=AssignmentDetailOut)
async def update_assignment_endpoint(
    request: Request,
    assignment_id: UUID,
    data: AssignmentUpdate,
    session: DBSession,
    user=Depends(require_permission("onboarding.edit")),
) -> AssignmentDetailOut:
    try:
        assignment = await service.update_assignment(session, assignment_id, data)
    except AssignmentNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "ASSIGNMENT_NOT_FOUND", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="ONBOARDING_ASSIGNMENT_UPDATED",
        resource_type="onboarding_assignment",
        resource_id=str(assignment.id),
        ip_address=request.client.host if request.client else None,
        after_state=data.model_dump(exclude_unset=True),
    )

    # Re-fetch eager utk detail
    assignment = await service.get_assignment(session, assignment.id)
    return await _build_assignment_out(session, assignment, detailed=True)


# ─── TaskCompletion endpoint ───────────────────────────────────────


@router.patch("/onboarding/completions/{completion_id}", response_model=TaskCompletionOut)
async def update_completion_endpoint(
    request: Request,
    completion_id: UUID,
    data: TaskCompletionUpdate,
    session: DBSession,
    user=Depends(require_permission("onboarding.edit")),
) -> TaskCompletionOut:
    try:
        completion = await service.update_completion(session, completion_id, data, user.id)
    except CompletionNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "COMPLETION_NOT_FOUND", "message": str(e)}) from e
    except InvalidOnboardingStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_INPUT", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="ONBOARDING_TASK_STATUS_CHANGED",
        resource_type="task_completion",
        resource_id=str(completion.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "new_status": data.status.value,
            "notes": data.notes,
            "blocker_reason": data.blocker_reason,
        },
    )

    # Re-fetch dengan task info
    refetch_stmt = (
        select(TaskCompletion)
        .where(TaskCompletion.id == completion_id)
        .options()
    )
    result = await session.execute(refetch_stmt)
    completion = result.scalar_one()
    from app.onboarding.models import OnboardingTask

    task_result = await session.execute(
        select(OnboardingTask).where(OnboardingTask.id == completion.task_id)
    )
    task = task_result.scalar_one_or_none()

    return TaskCompletionOut(
        id=completion.id,
        assignment_id=completion.assignment_id,
        task_id=completion.task_id,
        status=completion.status,
        due_date=completion.due_date,
        completed_at=completion.completed_at,
        completed_by_user_id=completion.completed_by_user_id,
        notes=completion.notes,
        blocker_reason=completion.blocker_reason,
        created_at=completion.created_at,
        updated_at=completion.updated_at,
        task_title=task.title if task else None,
        task_category=task.category if task else None,
        task_assigned_role=task.assigned_role if task else None,
        task_is_required=task.is_required if task else None,
        task_instructions=task.instructions if task else None,
        task_reference_url=task.reference_url if task else None,
    )
