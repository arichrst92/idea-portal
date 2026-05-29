"""Project router — TSK-022, refactored TSK-022C.

Endpoints di /api/v1:
- /projects                          — list, create
- /projects/{id}                     — get, patch
- /projects/{id}/activate            — DRAFT → ACTIVE
- /projects/{id}/close               — close dengan reason (Direktur override)
- /projects/{id}/members             — list, add
- /projects/members/{member_id}      — delete
- /projects/{id}/milestones          — list, create
- /projects/milestones/{m_id}        — update
- /projects/{id}/tasks               — list (kanban), create
- /projects/tasks/{t_id}             — update, delete

CATATAN (TSK-022C): Invoice endpoints di-pindah ke /api/v1/finance/invoices.
Lihat app.finance.router.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.core.audit import audit_log
from app.core.deps import CurrentUser, DBSession, require_permission
from app.identity.models import User
from app.organization.models import Employee
from app.project import service
from app.project.models import ProjectStatus, ProjectType
from app.project.schemas import (
    MemberAdd,
    MemberOut,
    MilestoneCreate,
    MilestoneOut,
    MilestoneUpdate,
    ProjectClose,
    ProjectCreate,
    ProjectListItem,
    ProjectListResponse,
    ProjectOut,
    ProjectUpdate,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)
from app.project.service import (
    DuplicateCodeError,
    InvalidProjectStateError,
    MemberNotFoundError,
    MilestoneNotFoundError,
    ProjectNotFoundError,
    TaskNotFoundError,
)

router = APIRouter(tags=["project"])


# ─── Helpers ───────────────────────────────────────────────────────


async def _lookup_user(session, user_id: UUID | None) -> tuple[str | None, str | None]:
    """(nik, _placeholder_name). User.nik kalau ada."""
    if user_id is None:
        return None, None
    r = await session.execute(select(User.nik).where(User.id == user_id))
    return r.scalar_one_or_none(), None


async def _lookup_employee(session, employee_id: UUID | None) -> tuple[str | None, str | None]:
    if employee_id is None:
        return None, None
    r = await session.execute(
        select(Employee.full_name, User.nik)
        .join(User, Employee.user_id == User.id)
        .where(Employee.id == employee_id)
    )
    row = r.first()
    if row is None:
        return None, None
    return row[1], row[0]


async def _build_project_out(session, p) -> ProjectOut:
    pm_nik, _ = await _lookup_user(session, p.pm_user_id)
    # Client name lookup (Client table di outsource domain)
    client_name = None
    if p.client_id:
        from app.outsource.models import Client

        cr = await session.execute(select(Client.name).where(Client.id == p.client_id))
        client_name = cr.scalar_one_or_none()

    mem_count = await service.count_members(session, p.id)
    ms_total = await service.count_total_milestones(session, p.id)
    ms_done = await service.count_completed_milestones(session, p.id)
    progress = await service.compute_overall_progress(session, p.id)

    return ProjectOut(
        id=p.id,
        code=p.code,
        name=p.name,
        type=p.type,
        status=p.status,
        description=p.description,
        pm_user_id=p.pm_user_id,
        client_id=p.client_id,
        start_date=p.start_date,
        end_date=p.end_date,
        contract_value=p.contract_value,
        currency=p.currency,
        created_at=p.created_at,
        updated_at=p.updated_at,
        pm_nik=pm_nik,
        client_name=client_name,
        member_count=mem_count,
        milestone_count=ms_total,
        completed_milestones=ms_done,
        overall_progress_pct=progress,
    )


async def _build_project_list_item(session, p) -> ProjectListItem:
    pm_nik, _ = await _lookup_user(session, p.pm_user_id)
    client_name = None
    if p.client_id:
        from app.outsource.models import Client

        cr = await session.execute(select(Client.name).where(Client.id == p.client_id))
        client_name = cr.scalar_one_or_none()

    return ProjectListItem(
        id=p.id,
        code=p.code,
        name=p.name,
        type=p.type,
        status=p.status,
        pm_nik=pm_nik,
        client_name=client_name,
        start_date=p.start_date,
        end_date=p.end_date,
        contract_value=p.contract_value,
        currency=p.currency,
        member_count=await service.count_members(session, p.id),
        overall_progress_pct=await service.compute_overall_progress(session, p.id),
    )


# ─── Project endpoints ─────────────────────────────────────────────


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects_endpoint(
    session: DBSession,
    _user=Depends(require_permission("project.view")),
    type: str | None = Query(None, alias="type"),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> ProjectListResponse:
    type_enum = ProjectType(type) if type else None
    status_enum = ProjectStatus(status_filter) if status_filter else None
    projects, total = await service.list_projects(
        session,
        project_type=type_enum,
        status=status_enum,
        page=page,
        page_size=page_size,
    )
    items = [await _build_project_list_item(session, p) for p in projects]
    return ProjectListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=service.calc_total_pages(total, page_size),
    )


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project_endpoint(
    request: Request,
    data: ProjectCreate,
    session: DBSession,
    user=Depends(require_permission("project.create")),
) -> ProjectOut:
    try:
        p = await service.create_project(session, data)
    except DuplicateCodeError as e:
        raise HTTPException(status_code=409, detail={"code": "DUPLICATE_CODE", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="PROJECT_CREATED",
        resource_type="project",
        resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
        after_state={"code": p.code, "type": p.type.value},
    )
    return await _build_project_out(session, p)


@router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project_endpoint(
    project_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("project.view")),
) -> ProjectOut:
    try:
        p = await service.get_project(session, project_id)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    return await _build_project_out(session, p)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
async def update_project_endpoint(
    request: Request,
    project_id: UUID,
    data: ProjectUpdate,
    session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> ProjectOut:
    try:
        p = await service.update_project(session, project_id, data)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidProjectStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="PROJECT_UPDATED",
        resource_type="project",
        resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
        after_state=data.model_dump(exclude_unset=True),
    )
    return await _build_project_out(session, p)


@router.post("/projects/{project_id}/activate", response_model=ProjectOut)
async def activate_project_endpoint(
    request: Request,
    project_id: UUID,
    session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> ProjectOut:
    try:
        p = await service.activate_project(session, project_id)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidProjectStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="PROJECT_ACTIVATED",
        resource_type="project",
        resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _build_project_out(session, p)


@router.post("/projects/{project_id}/close", response_model=ProjectOut)
async def close_project_endpoint(
    request: Request,
    project_id: UUID,
    data: ProjectClose,
    session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> ProjectOut:
    """Close project. Direktur Utama/Wakil bisa override status apa pun."""
    from app.identity.service import is_executive

    is_override = is_executive(user)

    try:
        p = await service.close_project(session, project_id, data, is_executive_override=is_override)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidProjectStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="PROJECT_CLOSED" if not is_override else "PROJECT_CLOSED_OVERRIDE",
        resource_type="project",
        resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "new_status": data.new_status.value,
            "reason": data.reason,
            "executive_override": is_override,
        },
    )
    return await _build_project_out(session, p)


# ─── Members ───────────────────────────────────────────────────────


@router.get("/projects/{project_id}/members", response_model=list[MemberOut])
async def list_members_endpoint(
    project_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("project.view")),
) -> list[MemberOut]:
    members = await service.list_members(session, project_id)
    out = []
    for m in members:
        nik, name = await _lookup_employee(session, m.employee_id)
        out.append(
            MemberOut(
                id=m.id,
                project_id=m.project_id,
                employee_id=m.employee_id,
                role=m.role,
                allocation_pct=m.allocation_pct,
                start_date=m.start_date,
                end_date=m.end_date,
                employee_nik=nik,
                employee_name=name,
            )
        )
    return out


@router.post(
    "/projects/{project_id}/members",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_member_endpoint(
    request: Request,
    project_id: UUID,
    data: MemberAdd,
    session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> MemberOut:
    try:
        m = await service.add_member(session, project_id, data)
    except (ProjectNotFoundError, InvalidProjectStateError) as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="PROJECT_MEMBER_ADDED",
        resource_type="project_member",
        resource_id=str(m.id),
        ip_address=request.client.host if request.client else None,
        after_state={"employee_id": str(data.employee_id), "allocation_pct": float(data.allocation_pct)},
    )

    nik, name = await _lookup_employee(session, m.employee_id)
    return MemberOut(
        id=m.id,
        project_id=m.project_id,
        employee_id=m.employee_id,
        role=m.role,
        allocation_pct=m.allocation_pct,
        start_date=m.start_date,
        end_date=m.end_date,
        employee_nik=nik,
        employee_name=name,
    )


@router.delete("/projects/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member_endpoint(
    member_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("project.edit")),
) -> None:
    try:
        await service.remove_member(session, member_id)
    except MemberNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e


# ─── Milestones ────────────────────────────────────────────────────


def _ms_to_out(m, today=None) -> MilestoneOut:
    from datetime import date as _date

    today = today or _date.today()
    overdue = m.target_date < today and m.completed_at is None
    return MilestoneOut(
        id=m.id,
        project_id=m.project_id,
        name=m.name,
        target_date=m.target_date,
        completed_at=m.completed_at,
        progress_pct=m.progress_pct,
        is_overdue=overdue,
    )


@router.get("/projects/{project_id}/milestones", response_model=list[MilestoneOut])
async def list_milestones_endpoint(
    project_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("project.view")),
) -> list[MilestoneOut]:
    milestones = await service.list_milestones(session, project_id)
    return [_ms_to_out(m) for m in milestones]


@router.post(
    "/projects/{project_id}/milestones",
    response_model=MilestoneOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_milestone_endpoint(
    request: Request,
    project_id: UUID,
    data: MilestoneCreate,
    session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> MilestoneOut:
    try:
        m = await service.create_milestone(session, project_id, data)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="MILESTONE_CREATED",
        resource_type="project_milestone",
        resource_id=str(m.id),
        ip_address=request.client.host if request.client else None,
    )
    return _ms_to_out(m)


@router.patch("/projects/milestones/{milestone_id}", response_model=MilestoneOut)
async def update_milestone_endpoint(
    request: Request,
    milestone_id: UUID,
    data: MilestoneUpdate,
    session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> MilestoneOut:
    try:
        m, triggered = await service.update_milestone(session, milestone_id, data)
    except MilestoneNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="MILESTONE_UPDATED",
        resource_type="project_milestone",
        resource_id=str(m.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "progress_pct": float(m.progress_pct),
            "completed_at": str(m.completed_at) if m.completed_at else None,
        },
    )
    return _ms_to_out(m)


# ─── Tasks ─────────────────────────────────────────────────────────


async def _task_to_out(session, t) -> TaskOut:
    assignee_nik, assignee_name = await _lookup_employee(session, t.assignee_id)
    ms_name = None
    if t.milestone_id:
        from app.project.models import ProjectMilestone

        mr = await session.execute(
            select(ProjectMilestone.name).where(ProjectMilestone.id == t.milestone_id)
        )
        ms_name = mr.scalar_one_or_none()
    return TaskOut(
        id=t.id,
        project_id=t.project_id,
        milestone_id=t.milestone_id,
        title=t.title,
        description=t.description,
        assignee_id=t.assignee_id,
        status=t.status,
        priority=t.priority,
        due_date=t.due_date,
        created_at=t.created_at,
        assignee_nik=assignee_nik,
        assignee_name=assignee_name,
        milestone_name=ms_name,
    )


@router.get("/projects/{project_id}/tasks", response_model=list[TaskOut])
async def list_tasks_endpoint(
    project_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("project.view")),
    status_filter: str | None = Query(None, alias="status"),
) -> list[TaskOut]:
    tasks = await service.list_tasks(session, project_id, status_filter)
    return [await _task_to_out(session, t) for t in tasks]


@router.post(
    "/projects/{project_id}/tasks",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_task_endpoint(
    request: Request,
    project_id: UUID,
    data: TaskCreate,
    session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> TaskOut:
    try:
        t = await service.create_task(session, project_id, data)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="TASK_CREATED",
        resource_type="project_task",
        resource_id=str(t.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _task_to_out(session, t)


@router.patch("/projects/tasks/{task_id}", response_model=TaskOut)
async def update_task_endpoint(
    task_id: UUID,
    data: TaskUpdate,
    session: DBSession,
    _user=Depends(require_permission("project.edit")),
) -> TaskOut:
    try:
        t = await service.update_task(session, task_id, data)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    return await _task_to_out(session, t)


@router.delete("/projects/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_endpoint(
    task_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("project.edit")),
) -> None:
    try:
        await service.delete_task(session, task_id)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e


# ─── Invoices ──────────────────────────────────────────────────────
# REMOVED (TSK-022C). Pindah ke /api/v1/finance/invoices.
# Lihat app.finance.router.
