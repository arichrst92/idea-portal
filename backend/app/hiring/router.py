"""Hiring router — FastAPI endpoints TSK-015.

Endpoints:
- /api/v1/job-openings              — list, create, detail, update, submit, approve, close
- /api/v1/job-openings/{id}/applications      — list applications for opening
- /api/v1/job-openings/{id}/pipeline          — kanban grouped by stage
- /api/v1/applications              — create (public-able), update, transition stage
- /api/v1/applications/{id}/transition        — stage transition with validation

RBAC:
- hiring.view → semua authenticated user (Manager+ untuk dept-nya, GM+ all)
- hiring.create → Manager+ (create draft + submit)
- hiring.approve → GM/C-Level/Executive (approve/reject)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.audit import audit_log
from app.core.deps import CurrentUser, DBSession, require_permission
from app.hiring import service
from app.hiring.models import ApplicationStage, JobOpeningStatus
from app.hiring.schemas import (
    JobApplicationCreate,
    JobApplicationOut,
    JobApplicationUpdate,
    JobOpeningApproveRequest,
    JobOpeningCreate,
    JobOpeningListItem,
    JobOpeningListResponse,
    JobOpeningOut,
    JobOpeningUpdate,
    PipelineResponse,
    PipelineStageBucket,
    StageTransitionRequest,
)
from app.hiring.service import (
    InvalidJobOpeningStateError,
    InvalidStageTransitionError,
    JobApplicationNotFoundError,
    JobOpeningNotFoundError,
)
from app.organization.models import Department, Position
from app.identity.models import User
from sqlalchemy import select

router = APIRouter(tags=["hiring"])


# ─── Stage display labels (Indonesian) ─────────────────────────────


_STAGE_LABELS: dict[ApplicationStage, str] = {
    ApplicationStage.APPLIED: "Applied",
    ApplicationStage.SCREENING: "Screening",
    ApplicationStage.HR_INTERVIEW: "HR Interview",
    ApplicationStage.USER_INTERVIEW: "User Interview",
    ApplicationStage.TECHNICAL_TEST: "Technical Test",
    ApplicationStage.OFFERING: "Offering",
    ApplicationStage.HIRED: "Hired",
    ApplicationStage.REJECTED: "Rejected",
    ApplicationStage.WITHDRAWN: "Withdrawn",
}


# ─── Helpers — build response with derived fields ──────────────────


async def _opening_to_out(session, opening) -> JobOpeningOut:
    """Build JobOpeningOut dengan derived fields (dept_name, position_name, dst)."""
    dept_name = None
    position_name = None
    requested_by_nik = None
    if opening.department_id:
        d = await session.execute(
            select(Department.name).where(Department.id == opening.department_id)
        )
        dept_name = d.scalar_one_or_none()
    if opening.position_id:
        p = await session.execute(
            select(Position.name).where(Position.id == opening.position_id)
        )
        position_name = p.scalar_one_or_none()
    if opening.requested_by_user_id:
        u = await session.execute(
            select(User.nik).where(User.id == opening.requested_by_user_id)
        )
        requested_by_nik = u.scalar_one_or_none()
    app_count = await service.get_application_count_for_opening(session, opening.id)

    return JobOpeningOut(
        id=opening.id,
        title=opening.title,
        description=opening.description,
        requirements=opening.requirements,
        department_id=opening.department_id,
        position_id=opening.position_id,
        slots_needed=opening.slots_needed,
        slots_filled=opening.slots_filled,
        min_salary=opening.min_salary,
        max_salary=opening.max_salary,
        currency=opening.currency,
        deadline=opening.deadline,
        is_public=opening.is_public,
        status=opening.status,
        posted_date=opening.posted_date,
        closed_date=opening.closed_date,
        requested_by_user_id=opening.requested_by_user_id,
        approved_by_user_id=opening.approved_by_user_id,
        approved_at=opening.approved_at,
        rejection_reason=opening.rejection_reason,
        created_at=opening.created_at,
        updated_at=opening.updated_at,
        department_name=dept_name,
        position_name=position_name,
        requested_by_nik=requested_by_nik,
        application_count=app_count,
    )


async def _application_to_out(application, job_title: str | None = None) -> JobApplicationOut:
    days = service.days_in_stage(application)
    return JobApplicationOut(
        id=application.id,
        job_opening_id=application.job_opening_id,
        candidate_name=application.candidate_name,
        candidate_email=application.candidate_email,
        candidate_phone=application.candidate_phone,
        resume_url=application.resume_url,
        cover_letter=application.cover_letter,
        linkedin_url=application.linkedin_url,
        source=application.source,
        referrer_user_id=application.referrer_user_id,
        stage=application.stage,
        stage_changed_at=application.stage_changed_at,
        rejection_reason=application.rejection_reason,
        rejection_stage=application.rejection_stage,
        notes=application.notes,
        offered_salary=application.offered_salary,
        offered_start_date=application.offered_start_date,
        created_at=application.created_at,
        updated_at=application.updated_at,
        job_title=job_title,
        days_in_stage=days,
    )


# ─── JobOpening endpoints ──────────────────────────────────────────


@router.get("/job-openings", response_model=JobOpeningListResponse)
async def list_openings(
    session: DBSession,
    _user=Depends(require_permission("hiring.view")),
    department_id: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> JobOpeningListResponse:
    status_enum = JobOpeningStatus(status_filter) if status_filter else None
    openings, total = await service.list_job_openings(
        session, department_id=department_id, status=status_enum, page=page, page_size=page_size
    )

    items: list[JobOpeningListItem] = []
    for o in openings:
        dept_name = None
        position_name = None
        if o.department_id:
            d = await session.execute(
                select(Department.name).where(Department.id == o.department_id)
            )
            dept_name = d.scalar_one_or_none()
        if o.position_id:
            p = await session.execute(select(Position.name).where(Position.id == o.position_id))
            position_name = p.scalar_one_or_none()
        app_count = await service.get_application_count_for_opening(session, o.id)
        items.append(
            JobOpeningListItem(
                id=o.id,
                title=o.title,
                department_name=dept_name,
                position_name=position_name,
                status=o.status,
                slots_needed=o.slots_needed,
                slots_filled=o.slots_filled,
                deadline=o.deadline,
                application_count=app_count,
                created_at=o.created_at,
            )
        )

    return JobOpeningListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=service.calc_total_pages(total, page_size),
    )


@router.post("/job-openings", response_model=JobOpeningOut, status_code=status.HTTP_201_CREATED)
async def create_opening(
    request: Request,
    data: JobOpeningCreate,
    session: DBSession,
    user=Depends(require_permission("hiring.create")),
) -> JobOpeningOut:
    try:
        opening = await service.create_job_opening(session, data, user.id)
    except InvalidJobOpeningStateError as e:
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_INPUT", "message": str(e)}
        ) from e

    await audit_log(
        session=session,
        actor=user,
        action="JOB_OPENING_CREATED",
        resource_type="job_opening",
        resource_id=str(opening.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        after_state={"title": opening.title, "status": opening.status.value},
    )
    return await _opening_to_out(session, opening)


@router.get("/job-openings/{opening_id}", response_model=JobOpeningOut)
async def get_opening(
    opening_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("hiring.view")),
) -> JobOpeningOut:
    try:
        opening = await service.get_job_opening(session, opening_id)
    except JobOpeningNotFoundError as e:
        raise HTTPException(
            status_code=404, detail={"code": "OPENING_NOT_FOUND", "message": str(e)}
        ) from e
    return await _opening_to_out(session, opening)


@router.patch("/job-openings/{opening_id}", response_model=JobOpeningOut)
async def update_opening(
    request: Request,
    opening_id: UUID,
    data: JobOpeningUpdate,
    session: DBSession,
    user=Depends(require_permission("hiring.create")),
) -> JobOpeningOut:
    try:
        opening = await service.update_job_opening(session, opening_id, data)
    except JobOpeningNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "OPENING_NOT_FOUND", "message": str(e)}) from e
    except InvalidJobOpeningStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="JOB_OPENING_UPDATED",
        resource_type="job_opening",
        resource_id=str(opening.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        after_state=data.model_dump(exclude_unset=True),
    )
    return await _opening_to_out(session, opening)


@router.post("/job-openings/{opening_id}/submit", response_model=JobOpeningOut)
async def submit_opening(
    request: Request,
    opening_id: UUID,
    session: DBSession,
    user=Depends(require_permission("hiring.create")),
) -> JobOpeningOut:
    """Submit DRAFT → PENDING_APPROVAL."""
    try:
        opening = await service.submit_for_approval(session, opening_id)
    except JobOpeningNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "OPENING_NOT_FOUND", "message": str(e)}) from e
    except InvalidJobOpeningStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="JOB_OPENING_SUBMITTED",
        resource_type="job_opening",
        resource_id=str(opening.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _opening_to_out(session, opening)


@router.post("/job-openings/{opening_id}/approve", response_model=JobOpeningOut)
async def approve_opening(
    request: Request,
    opening_id: UUID,
    data: JobOpeningApproveRequest,
    session: DBSession,
    user=Depends(require_permission("hiring.approve")),
) -> JobOpeningOut:
    """GM+/Executive approve atau reject job opening (US-OP-014)."""
    try:
        opening = await service.approve_or_reject_job_opening(
            session=session,
            opening_id=opening_id,
            approve=data.approve,
            approver_user_id=user.id,
            rejection_reason=data.rejection_reason,
        )
    except JobOpeningNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "OPENING_NOT_FOUND", "message": str(e)}) from e
    except InvalidJobOpeningStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_APPROVAL", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="JOB_OPENING_APPROVED" if data.approve else "JOB_OPENING_REJECTED",
        resource_type="job_opening",
        resource_id=str(opening.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "status": opening.status.value,
            "rejection_reason": data.rejection_reason,
        },
    )
    return await _opening_to_out(session, opening)


@router.post("/job-openings/{opening_id}/close", response_model=JobOpeningOut)
async def close_opening(
    request: Request,
    opening_id: UUID,
    session: DBSession,
    user=Depends(require_permission("hiring.approve")),
) -> JobOpeningOut:
    """Manual close lowongan (CLOSED atau FILLED tergantung slots_filled)."""
    try:
        opening = await service.close_job_opening(session, opening_id)
    except JobOpeningNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "OPENING_NOT_FOUND", "message": str(e)}) from e
    except InvalidJobOpeningStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="JOB_OPENING_CLOSED",
        resource_type="job_opening",
        resource_id=str(opening.id),
        ip_address=request.client.host if request.client else None,
        after_state={"status": opening.status.value},
    )
    return await _opening_to_out(session, opening)


# ─── Pipeline (kanban) ─────────────────────────────────────────────


@router.get("/job-openings/{opening_id}/pipeline", response_model=PipelineResponse)
async def get_pipeline(
    opening_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("hiring.view")),
) -> PipelineResponse:
    try:
        opening, buckets = await service.build_pipeline_buckets(session, opening_id)
    except JobOpeningNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "OPENING_NOT_FOUND", "message": str(e)}) from e

    total = sum(len(v) for v in buckets.values())
    stage_buckets = []
    for stage in ApplicationStage:
        apps = buckets.get(stage, [])
        out_apps = [await _application_to_out(a, opening.title) for a in apps]
        stage_buckets.append(
            PipelineStageBucket(
                stage=stage,
                label=_STAGE_LABELS[stage],
                count=len(apps),
                applications=out_apps,
            )
        )

    return PipelineResponse(
        job_opening_id=opening.id,
        job_title=opening.title,
        total_applications=total,
        stages=stage_buckets,
    )


# ─── Application endpoints ─────────────────────────────────────────


@router.post("/applications", response_model=JobApplicationOut, status_code=status.HTTP_201_CREATED)
async def create_application(
    request: Request,
    data: JobApplicationCreate,
    session: DBSession,
    user=Depends(require_permission("hiring.view")),
) -> JobApplicationOut:
    """HR/Manager input pendaftar baru. (Public career page submission akan
    pakai endpoint terpisah dengan rate limit di sub-chunk berikutnya.)
    """
    try:
        app_obj = await service.create_application(session, data)
    except JobOpeningNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "OPENING_NOT_FOUND", "message": str(e)}) from e
    except InvalidJobOpeningStateError as e:
        raise HTTPException(status_code=400, detail={"code": "OPENING_NOT_OPEN", "message": str(e)}) from e

    opening = await service.get_job_opening(session, app_obj.job_opening_id)
    await audit_log(
        session=session,
        actor=user,
        action="APPLICATION_CREATED",
        resource_type="job_application",
        resource_id=str(app_obj.id),
        ip_address=request.client.host if request.client else None,
        after_state={"candidate": app_obj.candidate_name, "stage": app_obj.stage.value},
    )
    return await _application_to_out(app_obj, opening.title)


@router.get("/applications/{app_id}", response_model=JobApplicationOut)
async def get_application(
    app_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("hiring.view")),
) -> JobApplicationOut:
    try:
        app_obj = await service.get_application(session, app_id)
    except JobApplicationNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "APPLICATION_NOT_FOUND", "message": str(e)}) from e
    opening = await service.get_job_opening(session, app_obj.job_opening_id)
    return await _application_to_out(app_obj, opening.title)


@router.patch("/applications/{app_id}", response_model=JobApplicationOut)
async def update_application(
    request: Request,
    app_id: UUID,
    data: JobApplicationUpdate,
    session: DBSession,
    user=Depends(require_permission("hiring.view")),
) -> JobApplicationOut:
    try:
        app_obj = await service.update_application(session, app_id, data)
    except JobApplicationNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "APPLICATION_NOT_FOUND", "message": str(e)}) from e

    opening = await service.get_job_opening(session, app_obj.job_opening_id)
    await audit_log(
        session=session,
        actor=user,
        action="APPLICATION_UPDATED",
        resource_type="job_application",
        resource_id=str(app_obj.id),
        ip_address=request.client.host if request.client else None,
        after_state=data.model_dump(exclude_unset=True),
    )
    return await _application_to_out(app_obj, opening.title)


@router.post("/applications/{app_id}/transition", response_model=JobApplicationOut)
async def transition_application_stage(
    request: Request,
    app_id: UUID,
    data: StageTransitionRequest,
    session: DBSession,
    user=Depends(require_permission("hiring.view")),
) -> JobApplicationOut:
    """Pindahkan kandidat ke stage berikutnya / reject / withdraw."""
    try:
        app_obj = await service.transition_stage(session, app_id, data)
    except JobApplicationNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "APPLICATION_NOT_FOUND", "message": str(e)}) from e
    except InvalidStageTransitionError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_TRANSITION", "message": str(e)}) from e

    opening = await service.get_job_opening(session, app_obj.job_opening_id)
    await audit_log(
        session=session,
        actor=user,
        action="APPLICATION_STAGE_TRANSITIONED",
        resource_type="job_application",
        resource_id=str(app_obj.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "new_stage": app_obj.stage.value,
            "notes": data.notes,
            "rejection_reason": data.rejection_reason,
        },
    )
    return await _application_to_out(app_obj, opening.title)
