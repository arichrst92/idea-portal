"""Project router — TSK-022, refactored TSK-022C & TSK-022B.

Hierarki endpoints di /api/v1:

  /projects                              — list, create
  /projects/{id}                         — get, patch
  /projects/{id}/activate                — DRAFT → ACTIVE
  /projects/{id}/close                   — close (Direktur override)

  /projects/{id}/members                 — list, add
  /projects/members/{member_id}          — remove

  /projects/{id}/phases                  — list, create
  /projects/phases/{phase_id}            — get, update (auto-trigger invoice notif), delete

  /projects/phases/{phase_id}/epics      — list, create
  /projects/{id}/epics                   — list all epics in project
  /projects/epics/{epic_id}              — get, update, delete

  /projects/{id}/tasks                   — list (kanban), create (slug auto)
  /projects/tasks/{task_id}              — get, update, delete

  /projects/tasks/{task_id}/subtasks     — list, create
  /projects/subtasks/{sub_id}            — get, update, delete

  /projects/tasks/{task_id}/comments     — list, create
  /projects/task-comments/{comment_id}   — update, delete (author only)
  /projects/subtasks/{sub_id}/comments   — list, create
  /projects/subtask-comments/{comment_id}— update, delete (author only)

CATATAN (TSK-022C): Invoice endpoint pindah ke /api/v1/finance/invoices.
Milestone endpoint dipertahankan sebagai alias backward-compat (deprecated).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from datetime import date as _date, timedelta as _timedelta

from app.core.audit import audit_log
from app.core.deps import CurrentUser, DBSession, require_permission
from app.identity.models import User
from app.organization.models import Employee
from app.project.models import ProjectTask as _ProjectTask
from app.project import service
from app.project.models import ProjectStatus, ProjectType
from app.project.schemas import (
    CommentCreate,
    CommentOut,
    CommentUpdate,
    EpicCreate,
    EpicOut,
    EpicUpdate,
    MemberAdd,
    MemberOut,
    PhaseCreate,
    PhaseOut,
    PhaseUpdate,
    ProjectClose,
    ProjectCreate,
    ProjectListItem,
    ProjectListResponse,
    ProjectOut,
    ProjectUpdate,
    SubtaskCreate,
    SubtaskOut,
    SubtaskUpdate,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)
from app.project.service import (
    CommentNotFoundError,
    DuplicateCodeError,
    EpicNotFoundError,
    InvalidProjectStateError,
    MemberNotFoundError,
    PhaseNotFoundError,
    ProjectNotFoundError,
    SubtaskNotFoundError,
    TaskNotFoundError,
)

router = APIRouter(tags=["project"])


# ─── Helpers ───────────────────────────────────────────────────────


async def _lookup_user(session, user_id: UUID | None) -> tuple[str | None, str | None]:
    if user_id is None:
        return None, None
    r = await session.execute(select(User.nik).where(User.id == user_id))
    return r.scalar_one_or_none(), None


async def _lookup_employee(session, employee_id: UUID | None) -> tuple[str | None, str | None]:
    if employee_id is None:
        return None, None
    r = await session.execute(
        select(User.nik, Employee.full_name)
        .join(User, Employee.user_id == User.id)
        .where(Employee.id == employee_id)
    )
    row = r.one_or_none()
    if row is None:
        return None, None
    return row[0], row[1]


async def _project_to_out(session, p) -> ProjectOut:
    pm_nik, _ = await _lookup_user(session, p.pm_user_id)
    client_name = None
    if p.client_id:
        from app.organization.models import Client

        r = await session.execute(select(Client.name).where(Client.id == p.client_id))
        client_name = r.scalar_one_or_none()
    phase_count = await service.count_total_phases(session, p.id)
    completed_phases = await service.count_completed_phases(session, p.id)
    member_count = await service.count_members(session, p.id)
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
        pm_name=None,
        client_name=client_name,
        member_count=member_count,
        phase_count=phase_count,
        completed_phases=completed_phases,
        overall_progress_pct=progress,
    )


def _project_to_list(p, pm_nik=None, client_name=None, member_count=0, progress=None) -> ProjectListItem:
    return ProjectListItem(
        id=p.id, code=p.code, name=p.name, type=p.type, status=p.status,
        pm_nik=pm_nik, client_name=client_name,
        start_date=p.start_date, end_date=p.end_date,
        contract_value=p.contract_value, currency=p.currency,
        member_count=member_count, overall_progress_pct=progress,
    )


# ─── Project endpoints ────────────────────────────────────────────


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects_endpoint(
    session: DBSession,
    project_type: ProjectType | None = Query(None, alias="type"),
    status_filter: ProjectStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _user=Depends(require_permission("project.view")),
) -> ProjectListResponse:
    items, total = await service.list_projects(
        session, project_type=project_type, status=status_filter,
        page=page, page_size=page_size,
    )
    out_items = []
    for p in items:
        pm_nik, _ = await _lookup_user(session, p.pm_user_id)
        client_name = None
        if p.client_id:
            from app.organization.models import Client
            r = await session.execute(select(Client.name).where(Client.id == p.client_id))
            client_name = r.scalar_one_or_none()
        mc = await service.count_members(session, p.id)
        prog = await service.compute_overall_progress(session, p.id)
        out_items.append(_project_to_list(p, pm_nik, client_name, mc, prog))
    return ProjectListResponse(
        items=out_items, total=total, page=page, page_size=page_size,
        total_pages=service.calc_total_pages(total, page_size),
    )


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
    return await _project_to_out(session, p)


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
        session=session, actor=user, action="PROJECT_CREATED",
        resource_type="project", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
        after_state={"code": p.code, "name": p.name, "type": p.type.value if hasattr(p.type, "value") else str(p.type)},
    )
    return await _project_to_out(session, p)


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
    await audit_log(
        session=session, actor=user, action="PROJECT_UPDATED",
        resource_type="project", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
        after_state=data.model_dump(exclude_unset=True, mode="json"),
    )
    return await _project_to_out(session, p)


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
        session=session, actor=user, action="PROJECT_ACTIVATED",
        resource_type="project", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _project_to_out(session, p)


@router.post("/projects/{project_id}/close", response_model=ProjectOut)
async def close_project_endpoint(
    request: Request,
    project_id: UUID,
    data: ProjectClose,
    session: DBSession,
    user=Depends(require_permission("project.override")),
) -> ProjectOut:
    try:
        p = await service.close_project(session, project_id, data)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidProjectStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="PROJECT_CLOSED",
        resource_type="project", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
        after_state={"new_status": data.new_status.value, "reason": data.reason},
    )
    return await _project_to_out(session, p)


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
        out.append(MemberOut(
            id=m.id, project_id=m.project_id, employee_id=m.employee_id,
            role=m.role, allocation_pct=m.allocation_pct,
            start_date=m.start_date, end_date=m.end_date,
            employee_nik=nik, employee_name=name,
        ))
    return out


@router.post(
    "/projects/{project_id}/members",
    response_model=MemberOut, status_code=status.HTTP_201_CREATED,
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
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="PROJECT_MEMBER_ADDED",
        resource_type="project_member", resource_id=str(m.id),
        ip_address=request.client.host if request.client else None,
        after_state={"employee_id": str(m.employee_id), "allocation_pct": float(m.allocation_pct)},
    )
    nik, name = await _lookup_employee(session, m.employee_id)
    return MemberOut(
        id=m.id, project_id=m.project_id, employee_id=m.employee_id,
        role=m.role, allocation_pct=m.allocation_pct,
        start_date=m.start_date, end_date=m.end_date,
        employee_nik=nik, employee_name=name,
    )


@router.delete("/projects/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member_endpoint(
    request: Request,
    member_id: UUID,
    session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> None:
    try:
        await service.remove_member(session, member_id)
    except MemberNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="PROJECT_MEMBER_REMOVED",
        resource_type="project_member", resource_id=str(member_id),
        ip_address=request.client.host if request.client else None,
    )


# ─── Phase (replaces Milestone) ────────────────────────────────────


def _phase_to_out(p, epic_count: int = 0) -> PhaseOut:
    from datetime import date as _date
    is_overdue = bool(
        p.target_date and p.target_date < _date.today() and p.completed_at is None
    )
    return PhaseOut(
        id=p.id, project_id=p.project_id, name=p.name, description=p.description,
        order_index=p.order_index, target_date=p.target_date,
        completed_at=p.completed_at, status=p.status,
        progress_pct=p.progress_pct, is_overdue=is_overdue, epic_count=epic_count,
    )


@router.get("/projects/{project_id}/phases", response_model=list[PhaseOut])
async def list_phases_endpoint(
    project_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("project.view")),
) -> list[PhaseOut]:
    phases = await service.list_phases(session, project_id)
    out = []
    for p in phases:
        epics = await service.list_epics(session, phase_id=p.id)
        out.append(_phase_to_out(p, epic_count=len(epics)))
    return out


@router.post(
    "/projects/{project_id}/phases",
    response_model=PhaseOut, status_code=status.HTTP_201_CREATED,
)
async def create_phase_endpoint(
    request: Request,
    project_id: UUID,
    data: PhaseCreate,
    session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> PhaseOut:
    try:
        p = await service.create_phase(session, project_id, data)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="PHASE_CREATED",
        resource_type="project_phase", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
        after_state={"name": p.name, "project_id": str(project_id)},
    )
    return _phase_to_out(p)


@router.get("/projects/phases/{phase_id}", response_model=PhaseOut)
async def get_phase_endpoint(
    phase_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("project.view")),
) -> PhaseOut:
    try:
        p = await service.get_phase(session, phase_id)
    except PhaseNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    epics = await service.list_epics(session, phase_id=p.id)
    return _phase_to_out(p, epic_count=len(epics))


@router.patch("/projects/phases/{phase_id}", response_model=PhaseOut)
async def update_phase_endpoint(
    request: Request,
    phase_id: UUID,
    data: PhaseUpdate,
    session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> PhaseOut:
    try:
        p, triggered = await service.update_phase(session, phase_id, data)
    except PhaseNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="PHASE_UPDATED",
        resource_type="project_phase", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "progress_pct": float(p.progress_pct),
            "completed_at": str(p.completed_at) if p.completed_at else None,
            "triggered_invoices": [str(inv.id) for inv in triggered],
        },
    )
    return _phase_to_out(p)


@router.delete("/projects/phases/{phase_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_phase_endpoint(
    request: Request,
    phase_id: UUID,
    session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> None:
    try:
        await service.delete_phase(session, phase_id)
    except PhaseNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="PHASE_DELETED",
        resource_type="project_phase", resource_id=str(phase_id),
        ip_address=request.client.host if request.client else None,
    )


# Backward-compat milestone aliases (deprecated, akan dihapus setelah frontend migrate)
@router.get("/projects/{project_id}/milestones", response_model=list[PhaseOut], deprecated=True)
async def list_milestones_alias(project_id: UUID, session: DBSession,
                                 _user=Depends(require_permission("project.view"))) -> list[PhaseOut]:
    return await list_phases_endpoint(project_id, session, _user)


@router.post("/projects/{project_id}/milestones", response_model=PhaseOut,
             status_code=status.HTTP_201_CREATED, deprecated=True)
async def create_milestone_alias(request: Request, project_id: UUID, data: PhaseCreate,
                                  session: DBSession,
                                  user=Depends(require_permission("project.edit"))) -> PhaseOut:
    return await create_phase_endpoint(request, project_id, data, session, user)


@router.patch("/projects/milestones/{milestone_id}", response_model=PhaseOut, deprecated=True)
async def update_milestone_alias(request: Request, milestone_id: UUID, data: PhaseUpdate,
                                  session: DBSession,
                                  user=Depends(require_permission("project.edit"))) -> PhaseOut:
    return await update_phase_endpoint(request, milestone_id, data, session, user)


# ─── Epic ──────────────────────────────────────────────────────────


async def _epic_to_out(session, e) -> EpicOut:
    task_count = await service.count_tasks_in_epic(session, e.id)
    completed = await service.count_tasks_in_epic(session, e.id, completed_only=True)
    return EpicOut(
        id=e.id, phase_id=e.phase_id, project_id=e.project_id,
        name=e.name, description=e.description,
        order_index=e.order_index, status=e.status, color=e.color,
        task_count=task_count, completed_task_count=completed,
    )


@router.get("/projects/phases/{phase_id}/epics", response_model=list[EpicOut])
async def list_phase_epics_endpoint(
    phase_id: UUID, session: DBSession,
    _user=Depends(require_permission("project.view")),
) -> list[EpicOut]:
    epics = await service.list_epics(session, phase_id=phase_id)
    return [await _epic_to_out(session, e) for e in epics]


@router.get("/projects/{project_id}/epics", response_model=list[EpicOut])
async def list_project_epics_endpoint(
    project_id: UUID, session: DBSession,
    _user=Depends(require_permission("project.view")),
) -> list[EpicOut]:
    epics = await service.list_epics(session, project_id=project_id)
    return [await _epic_to_out(session, e) for e in epics]


@router.post(
    "/projects/phases/{phase_id}/epics",
    response_model=EpicOut, status_code=status.HTTP_201_CREATED,
)
async def create_epic_endpoint(
    request: Request, phase_id: UUID, data: EpicCreate, session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> EpicOut:
    try:
        e = await service.create_epic(session, phase_id, data)
    except PhaseNotFoundError as ex:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(ex)}) from ex
    await audit_log(
        session=session, actor=user, action="EPIC_CREATED",
        resource_type="project_epic", resource_id=str(e.id),
        ip_address=request.client.host if request.client else None,
        after_state={"name": e.name, "phase_id": str(phase_id)},
    )
    return await _epic_to_out(session, e)


@router.get("/projects/epics/{epic_id}", response_model=EpicOut)
async def get_epic_endpoint(
    epic_id: UUID, session: DBSession,
    _user=Depends(require_permission("project.view")),
) -> EpicOut:
    try:
        e = await service.get_epic(session, epic_id)
    except EpicNotFoundError as ex:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(ex)}) from ex
    return await _epic_to_out(session, e)


@router.patch("/projects/epics/{epic_id}", response_model=EpicOut)
async def update_epic_endpoint(
    request: Request, epic_id: UUID, data: EpicUpdate, session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> EpicOut:
    try:
        e = await service.update_epic(session, epic_id, data)
    except EpicNotFoundError as ex:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(ex)}) from ex
    await audit_log(
        session=session, actor=user, action="EPIC_UPDATED",
        resource_type="project_epic", resource_id=str(e.id),
        ip_address=request.client.host if request.client else None,
        after_state=data.model_dump(exclude_unset=True, mode="json"),
    )
    return await _epic_to_out(session, e)


@router.delete("/projects/epics/{epic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_epic_endpoint(
    request: Request, epic_id: UUID, session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> None:
    try:
        await service.delete_epic(session, epic_id)
    except EpicNotFoundError as ex:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(ex)}) from ex
    await audit_log(
        session=session, actor=user, action="EPIC_DELETED",
        resource_type="project_epic", resource_id=str(epic_id),
        ip_address=request.client.host if request.client else None,
    )


# ─── Tasks ─────────────────────────────────────────────────────────


async def _task_to_out(session, t) -> TaskOut:
    assignee_nik, assignee_name = await _lookup_employee(session, t.assignee_id)
    epic_name = None
    phase_name = None
    if t.epic_id:
        from app.project.models import ProjectEpic, ProjectPhase

        r = await session.execute(
            select(ProjectEpic.name, ProjectPhase.name)
            .join(ProjectPhase, ProjectEpic.phase_id == ProjectPhase.id)
            .where(ProjectEpic.id == t.epic_id)
        )
        row = r.one_or_none()
        if row:
            epic_name, phase_name = row
    subtask_count = await service.count_subtasks(session, t.id)
    completed_subtask_count = await service.count_subtasks(session, t.id, completed_only=True)
    comment_count = await service.count_task_comments(session, t.id)
    return TaskOut(
        id=t.id, project_id=t.project_id, epic_id=t.epic_id, slug=t.slug,
        title=t.title, description=t.description,
        assignee_id=t.assignee_id, status=t.status, priority=t.priority,
        story_points=t.story_points, due_date=t.due_date,
        created_at=t.created_at, updated_at=t.updated_at,
        assignee_nik=assignee_nik, assignee_name=assignee_name,
        epic_name=epic_name, phase_name=phase_name,
        subtask_count=subtask_count, completed_subtask_count=completed_subtask_count,
        comment_count=comment_count,
    )


@router.get("/projects/{project_id}/tasks", response_model=list[TaskOut])
async def list_tasks_endpoint(
    project_id: UUID, session: DBSession,
    epic_id: UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
    _user=Depends(require_permission("project.view")),
) -> list[TaskOut]:
    tasks = await service.list_tasks(session, project_id, epic_id=epic_id, status_filter=status_filter)
    return [await _task_to_out(session, t) for t in tasks]


@router.get("/projects/tasks/{task_id}", response_model=TaskOut)
async def get_task_endpoint(
    task_id: UUID, session: DBSession,
    _user=Depends(require_permission("project.view")),
) -> TaskOut:
    try:
        t = await service.get_task(session, task_id)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    return await _task_to_out(session, t)


@router.post(
    "/projects/{project_id}/tasks",
    response_model=TaskOut, status_code=status.HTTP_201_CREATED,
)
async def create_task_endpoint(
    request: Request, project_id: UUID, data: TaskCreate, session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> TaskOut:
    try:
        t = await service.create_task(session, project_id, data)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="TASK_CREATED",
        resource_type="project_task", resource_id=str(t.id),
        ip_address=request.client.host if request.client else None,
        after_state={"slug": t.slug, "title": t.title, "project_id": str(project_id)},
    )
    return await _task_to_out(session, t)


@router.patch("/projects/tasks/{task_id}", response_model=TaskOut)
async def update_task_endpoint(
    request: Request, task_id: UUID, data: TaskUpdate, session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> TaskOut:
    try:
        t = await service.update_task(session, task_id, data)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="TASK_UPDATED",
        resource_type="project_task", resource_id=str(t.id),
        ip_address=request.client.host if request.client else None,
        after_state=data.model_dump(exclude_unset=True, mode="json"),
    )
    return await _task_to_out(session, t)


@router.delete("/projects/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_endpoint(
    request: Request, task_id: UUID, session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> None:
    try:
        await service.delete_task(session, task_id)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="TASK_DELETED",
        resource_type="project_task", resource_id=str(task_id),
        ip_address=request.client.host if request.client else None,
    )


# ─── Subtasks ──────────────────────────────────────────────────────


async def _subtask_to_out(session, s) -> SubtaskOut:
    assignee_nik, assignee_name = await _lookup_employee(session, s.assignee_id)
    comment_count = await service.count_subtask_comments(session, s.id)
    return SubtaskOut(
        id=s.id, task_id=s.task_id, slug=s.slug, title=s.title,
        description=s.description, assignee_id=s.assignee_id,
        status=s.status, story_points=s.story_points, due_date=s.due_date,
        order_index=s.order_index, created_at=s.created_at, updated_at=s.updated_at,
        assignee_nik=assignee_nik, assignee_name=assignee_name,
        comment_count=comment_count,
    )


@router.get("/projects/tasks/{task_id}/subtasks", response_model=list[SubtaskOut])
async def list_subtasks_endpoint(
    task_id: UUID, session: DBSession,
    _user=Depends(require_permission("project.view")),
) -> list[SubtaskOut]:
    subs = await service.list_subtasks(session, task_id)
    return [await _subtask_to_out(session, s) for s in subs]


@router.post(
    "/projects/tasks/{task_id}/subtasks",
    response_model=SubtaskOut, status_code=status.HTTP_201_CREATED,
)
async def create_subtask_endpoint(
    request: Request, task_id: UUID, data: SubtaskCreate, session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> SubtaskOut:
    try:
        s = await service.create_subtask(session, task_id, data)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="SUBTASK_CREATED",
        resource_type="project_subtask", resource_id=str(s.id),
        ip_address=request.client.host if request.client else None,
        after_state={"slug": s.slug, "title": s.title, "task_id": str(task_id)},
    )
    return await _subtask_to_out(session, s)


@router.patch("/projects/subtasks/{subtask_id}", response_model=SubtaskOut)
async def update_subtask_endpoint(
    request: Request, subtask_id: UUID, data: SubtaskUpdate, session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> SubtaskOut:
    try:
        s = await service.update_subtask(session, subtask_id, data)
    except SubtaskNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="SUBTASK_UPDATED",
        resource_type="project_subtask", resource_id=str(s.id),
        ip_address=request.client.host if request.client else None,
        after_state=data.model_dump(exclude_unset=True, mode="json"),
    )
    return await _subtask_to_out(session, s)


@router.delete("/projects/subtasks/{subtask_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subtask_endpoint(
    request: Request, subtask_id: UUID, session: DBSession,
    user=Depends(require_permission("project.edit")),
) -> None:
    try:
        await service.delete_subtask(session, subtask_id)
    except SubtaskNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="SUBTASK_DELETED",
        resource_type="project_subtask", resource_id=str(subtask_id),
        ip_address=request.client.host if request.client else None,
    )


# ─── Comments ──────────────────────────────────────────────────────


async def _comment_to_out(session, c) -> CommentOut:
    nik, _ = await _lookup_user(session, c.author_user_id)
    name = None
    if c.author_user_id:
        from app.organization.models import Employee as Emp
        r = await session.execute(
            select(Emp.full_name)
            .join(User, Emp.user_id == User.id)
            .where(User.id == c.author_user_id)
        )
        name = r.scalar_one_or_none()
    return CommentOut(
        id=c.id, author_user_id=c.author_user_id, body=c.body,
        created_at=c.created_at, updated_at=c.updated_at,
        author_nik=nik, author_name=name,
    )


@router.get("/projects/tasks/{task_id}/comments", response_model=list[CommentOut])
async def list_task_comments_endpoint(
    task_id: UUID, session: DBSession,
    _user=Depends(require_permission("project.view")),
) -> list[CommentOut]:
    comments = await service.list_task_comments(session, task_id)
    return [await _comment_to_out(session, c) for c in comments]


@router.post(
    "/projects/tasks/{task_id}/comments",
    response_model=CommentOut, status_code=status.HTTP_201_CREATED,
)
async def create_task_comment_endpoint(
    request: Request, task_id: UUID, data: CommentCreate, session: DBSession,
    user=Depends(require_permission("project.view")),
) -> CommentOut:
    try:
        c = await service.create_task_comment(session, task_id, user.id, data)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="TASK_COMMENT_ADDED",
        resource_type="project_task_comment", resource_id=str(c.id),
        ip_address=request.client.host if request.client else None,
        after_state={"task_id": str(task_id), "body_len": len(c.body)},
    )
    return await _comment_to_out(session, c)


@router.patch("/projects/task-comments/{comment_id}", response_model=CommentOut)
async def update_task_comment_endpoint(
    request: Request, comment_id: UUID, data: CommentUpdate, session: DBSession,
    user=Depends(require_permission("project.view")),
) -> CommentOut:
    try:
        c = await service.update_task_comment(session, comment_id, user.id, data)
    except CommentNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidProjectStateError as e:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="TASK_COMMENT_UPDATED",
        resource_type="project_task_comment", resource_id=str(c.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _comment_to_out(session, c)


@router.delete("/projects/task-comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_comment_endpoint(
    request: Request, comment_id: UUID, session: DBSession,
    user=Depends(require_permission("project.view")),
) -> None:
    try:
        await service.delete_task_comment(session, comment_id, user.id)
    except CommentNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidProjectStateError as e:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="TASK_COMMENT_DELETED",
        resource_type="project_task_comment", resource_id=str(comment_id),
        ip_address=request.client.host if request.client else None,
    )


@router.get("/projects/subtasks/{subtask_id}/comments", response_model=list[CommentOut])
async def list_subtask_comments_endpoint(
    subtask_id: UUID, session: DBSession,
    _user=Depends(require_permission("project.view")),
) -> list[CommentOut]:
    comments = await service.list_subtask_comments(session, subtask_id)
    return [await _comment_to_out(session, c) for c in comments]


@router.post(
    "/projects/subtasks/{subtask_id}/comments",
    response_model=CommentOut, status_code=status.HTTP_201_CREATED,
)
async def create_subtask_comment_endpoint(
    request: Request, subtask_id: UUID, data: CommentCreate, session: DBSession,
    user=Depends(require_permission("project.view")),
) -> CommentOut:
    try:
        c = await service.create_subtask_comment(session, subtask_id, user.id, data)
    except SubtaskNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="SUBTASK_COMMENT_ADDED",
        resource_type="project_subtask_comment", resource_id=str(c.id),
        ip_address=request.client.host if request.client else None,
        after_state={"subtask_id": str(subtask_id), "body_len": len(c.body)},
    )
    return await _comment_to_out(session, c)


@router.patch("/projects/subtask-comments/{comment_id}", response_model=CommentOut)
async def update_subtask_comment_endpoint(
    request: Request, comment_id: UUID, data: CommentUpdate, session: DBSession,
    user=Depends(require_permission("project.view")),
) -> CommentOut:
    try:
        c = await service.update_subtask_comment(session, comment_id, user.id, data)
    except CommentNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidProjectStateError as e:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="SUBTASK_COMMENT_UPDATED",
        resource_type="project_subtask_comment", resource_id=str(c.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _comment_to_out(session, c)


@router.delete("/projects/subtask-comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subtask_comment_endpoint(
    request: Request, comment_id: UUID, session: DBSession,
    user=Depends(require_permission("project.view")),
) -> None:
    try:
        await service.delete_subtask_comment(session, comment_id, user.id)
    except CommentNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidProjectStateError as e:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="SUBTASK_COMMENT_DELETED",
        resource_type="project_subtask_comment", resource_id=str(comment_id),
        ip_address=request.client.host if request.client else None,
    )


# ─── Task deadline notifications (TSK-075) ────────────────────────


@router.get("/me/project-tasks-due")
async def my_tasks_due_summary_endpoint(
    session: DBSession,
    user: CurrentUser,
) -> dict:
    """Summary deadline task untuk current user as assignee.

    Returns:
      {
        overdue_count: int,
        due_h1_count: int,   # due today + tomorrow
        due_h3_count: int,   # due in 2-3 days
        items: [{ task_id, slug, title, due_date, status, project_id }]
      }
    """
    # Map user → employee (User punya relationship .employee, bukan employee_id direct)
    emp_stmt = select(Employee.id).where(Employee.user_id == user.id)
    employee_id = (await session.execute(emp_stmt)).scalar_one_or_none()
    if employee_id is None:
        return {"overdue_count": 0, "due_h1_count": 0, "due_h3_count": 0, "items": []}

    today = _date.today()
    h1_cutoff = today + _timedelta(days=1)
    h3_cutoff = today + _timedelta(days=3)

    stmt = (
        select(_ProjectTask)
        .where(
            _ProjectTask.assignee_id == employee_id,
            _ProjectTask.deleted_at.is_(None),
            _ProjectTask.due_date.is_not(None),
            _ProjectTask.status.notin_(["DONE"]),
            _ProjectTask.due_date <= h3_cutoff,
        )
        .order_by(_ProjectTask.due_date.asc())
        .limit(50)
    )
    tasks = list((await session.execute(stmt)).scalars().all())

    overdue = [t for t in tasks if t.due_date < today]
    due_h1 = [t for t in tasks if today <= t.due_date <= h1_cutoff]
    due_h3 = [t for t in tasks if h1_cutoff < t.due_date <= h3_cutoff]

    items = [
        {
            "task_id": str(t.id),
            "slug": t.slug,
            "title": t.title,
            "due_date": t.due_date.isoformat(),
            "status": t.status,
            "project_id": str(t.project_id),
            "is_overdue": t.due_date < today,
            "days_until_due": (t.due_date - today).days,
        }
        for t in tasks
    ]

    return {
        "overdue_count": len(overdue),
        "due_h1_count": len(due_h1),
        "due_h3_count": len(due_h3),
        "items": items,
    }
