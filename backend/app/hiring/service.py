"""Hiring domain — business logic untuk JobOpening/JobApplication/Interview.

TSK-015 (M1.2 / M1.3 starter):
- JobOpening lifecycle: DRAFT → PENDING_APPROVAL → OPEN → FILLED/CANCELLED/CLOSED
- JobApplication pipeline: APPLIED → SCREENING → HR → USER → OFFERING → HIRED
- Approval flow per knowledge.md sec.5 (2-layer Manager → GM/C-Level)

Note: Interview CRUD service deferred ke sub-chunk berikutnya.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.hiring.models import (
    ApplicationStage,
    JobApplication,
    JobOpening,
    JobOpeningStatus,
)
from app.hiring.schemas import (
    JobApplicationCreate,
    JobApplicationUpdate,
    JobOpeningCreate,
    JobOpeningUpdate,
    StageTransitionRequest,
)
from app.organization.models import Department, Position


# ─── Exceptions ────────────────────────────────────────────────────


class JobOpeningNotFoundError(Exception):
    pass


class JobApplicationNotFoundError(Exception):
    pass


class InvalidStageTransitionError(Exception):
    pass


class InvalidJobOpeningStateError(Exception):
    pass


# ─── JobOpening CRUD ───────────────────────────────────────────────


async def get_job_opening(session: AsyncSession, opening_id: UUID) -> JobOpening:
    stmt = (
        select(JobOpening)
        .where(JobOpening.id == opening_id, JobOpening.deleted_at.is_(None))
    )
    result = await session.execute(stmt)
    opening = result.scalar_one_or_none()
    if opening is None:
        raise JobOpeningNotFoundError(f"JobOpening {opening_id} not found")
    return opening


async def create_job_opening(
    session: AsyncSession,
    data: JobOpeningCreate,
    requested_by_user_id: UUID,
) -> JobOpening:
    """Create as DRAFT. Caller harus call submit_for_approval() supaya masuk
    PENDING_APPROVAL.
    """
    # Validate dept exists
    dept = await session.execute(
        select(Department).where(Department.id == data.department_id)
    )
    if dept.scalar_one_or_none() is None:
        raise InvalidJobOpeningStateError(f"Department {data.department_id} not found")

    # Validate position kalau diberikan
    if data.position_id is not None:
        pos = await session.execute(select(Position).where(Position.id == data.position_id))
        if pos.scalar_one_or_none() is None:
            raise InvalidJobOpeningStateError(f"Position {data.position_id} not found")

    # Validate salary range
    if data.min_salary is not None and data.max_salary is not None:
        if data.min_salary > data.max_salary:
            raise InvalidJobOpeningStateError("min_salary > max_salary")

    opening = JobOpening(
        **data.model_dump(),
        requested_by_user_id=requested_by_user_id,
        status=JobOpeningStatus.DRAFT,
    )
    session.add(opening)
    await session.commit()
    await session.refresh(opening)
    return opening


async def update_job_opening(
    session: AsyncSession, opening_id: UUID, data: JobOpeningUpdate
) -> JobOpening:
    opening = await get_job_opening(session, opening_id)
    # Hanya bisa update saat DRAFT atau PENDING_APPROVAL
    if opening.status not in {JobOpeningStatus.DRAFT, JobOpeningStatus.PENDING_APPROVAL}:
        raise InvalidJobOpeningStateError(
            f"Job opening status {opening.status.value} — tidak bisa diedit. "
            "Hanya DRAFT atau PENDING_APPROVAL yang editable."
        )

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(opening, field, value)

    await session.commit()
    await session.refresh(opening)
    return opening


async def submit_for_approval(session: AsyncSession, opening_id: UUID) -> JobOpening:
    """Manager submit DRAFT → PENDING_APPROVAL."""
    opening = await get_job_opening(session, opening_id)
    if opening.status != JobOpeningStatus.DRAFT:
        raise InvalidJobOpeningStateError(
            f"Status saat ini {opening.status.value} — hanya DRAFT yang bisa submit."
        )
    opening.status = JobOpeningStatus.PENDING_APPROVAL
    await session.commit()
    await session.refresh(opening)
    return opening


async def approve_or_reject_job_opening(
    session: AsyncSession,
    opening_id: UUID,
    approve: bool,
    approver_user_id: UUID,
    rejection_reason: str | None = None,
) -> JobOpening:
    """GM/C-Level approve atau reject job opening (US-OP-014)."""
    opening = await get_job_opening(session, opening_id)
    if opening.status != JobOpeningStatus.PENDING_APPROVAL:
        raise InvalidJobOpeningStateError(
            f"Status saat ini {opening.status.value} — hanya PENDING_APPROVAL yang bisa di-approve/reject."
        )
    if opening.requested_by_user_id == approver_user_id:
        raise InvalidJobOpeningStateError(
            "Self-approval blocked — tidak boleh approve request sendiri."
        )

    opening.approved_by_user_id = approver_user_id
    opening.approved_at = datetime.now(UTC)

    if approve:
        opening.status = JobOpeningStatus.OPEN
        opening.posted_date = date.today()
    else:
        if not rejection_reason or len(rejection_reason.strip()) < 10:
            raise InvalidJobOpeningStateError("Rejection reason wajib min 10 karakter")
        opening.status = JobOpeningStatus.CANCELLED
        opening.rejection_reason = rejection_reason
        opening.closed_date = date.today()

    await session.commit()
    await session.refresh(opening)
    return opening


async def close_job_opening(session: AsyncSession, opening_id: UUID) -> JobOpening:
    """Tutup lowongan secara manual (slots terpenuhi atau dibatalkan)."""
    opening = await get_job_opening(session, opening_id)
    if opening.status != JobOpeningStatus.OPEN:
        raise InvalidJobOpeningStateError(
            f"Hanya status OPEN yang bisa diclose. Saat ini: {opening.status.value}"
        )
    opening.status = (
        JobOpeningStatus.FILLED
        if opening.slots_filled >= opening.slots_needed
        else JobOpeningStatus.CLOSED
    )
    opening.closed_date = date.today()
    await session.commit()
    await session.refresh(opening)
    return opening


async def list_job_openings(
    session: AsyncSession,
    department_id: UUID | None = None,
    status: JobOpeningStatus | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[JobOpening], int]:
    page = max(page, 1)
    page_size = max(min(page_size, 200), 1)

    base = select(JobOpening).where(JobOpening.deleted_at.is_(None))
    if department_id is not None:
        base = base.where(JobOpening.department_id == department_id)
    if status is not None:
        base = base.where(JobOpening.status == status)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    stmt = (
        base.order_by(JobOpening.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_application_count_for_opening(
    session: AsyncSession, opening_id: UUID
) -> int:
    stmt = select(func.count(JobApplication.id)).where(
        JobApplication.job_opening_id == opening_id
    )
    return int((await session.execute(stmt)).scalar_one())


# ─── JobApplication CRUD + Pipeline ────────────────────────────────


async def get_application(session: AsyncSession, app_id: UUID) -> JobApplication:
    stmt = select(JobApplication).where(JobApplication.id == app_id)
    result = await session.execute(stmt)
    app_obj = result.scalar_one_or_none()
    if app_obj is None:
        raise JobApplicationNotFoundError(f"Application {app_id} not found")
    return app_obj


async def create_application(
    session: AsyncSession, data: JobApplicationCreate
) -> JobApplication:
    # Validate opening exists and is OPEN
    opening = await get_job_opening(session, data.job_opening_id)
    if opening.status != JobOpeningStatus.OPEN:
        raise InvalidJobOpeningStateError(
            f"Job opening status {opening.status.value} — tidak menerima aplikasi"
        )

    app_obj = JobApplication(**data.model_dump(), stage=ApplicationStage.APPLIED)
    app_obj.stage_changed_at = datetime.now(UTC)
    session.add(app_obj)
    await session.commit()
    await session.refresh(app_obj)
    return app_obj


async def update_application(
    session: AsyncSession, app_id: UUID, data: JobApplicationUpdate
) -> JobApplication:
    app_obj = await get_application(session, app_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(app_obj, field, value)
    await session.commit()
    await session.refresh(app_obj)
    return app_obj


# Valid stage transitions per pipeline
_STAGE_FLOW: dict[ApplicationStage, set[ApplicationStage]] = {
    ApplicationStage.APPLIED: {
        ApplicationStage.SCREENING,
        ApplicationStage.REJECTED,
        ApplicationStage.WITHDRAWN,
    },
    ApplicationStage.SCREENING: {
        ApplicationStage.HR_INTERVIEW,
        ApplicationStage.REJECTED,
        ApplicationStage.WITHDRAWN,
    },
    ApplicationStage.HR_INTERVIEW: {
        ApplicationStage.USER_INTERVIEW,
        ApplicationStage.TECHNICAL_TEST,
        ApplicationStage.OFFERING,
        ApplicationStage.REJECTED,
        ApplicationStage.WITHDRAWN,
    },
    ApplicationStage.USER_INTERVIEW: {
        ApplicationStage.TECHNICAL_TEST,
        ApplicationStage.OFFERING,
        ApplicationStage.REJECTED,
        ApplicationStage.WITHDRAWN,
    },
    ApplicationStage.TECHNICAL_TEST: {
        ApplicationStage.OFFERING,
        ApplicationStage.REJECTED,
        ApplicationStage.WITHDRAWN,
    },
    ApplicationStage.OFFERING: {
        ApplicationStage.HIRED,
        ApplicationStage.REJECTED,
        ApplicationStage.WITHDRAWN,
    },
    # Terminal stages
    ApplicationStage.HIRED: set(),
    ApplicationStage.REJECTED: set(),
    ApplicationStage.WITHDRAWN: set(),
}


async def transition_stage(
    session: AsyncSession,
    app_id: UUID,
    transition: StageTransitionRequest,
) -> JobApplication:
    """Pindahkan kandidat antar stage dengan validasi flow."""
    app_obj = await get_application(session, app_id)

    allowed = _STAGE_FLOW.get(app_obj.stage, set())
    if transition.new_stage not in allowed:
        raise InvalidStageTransitionError(
            f"Tidak boleh transisi {app_obj.stage.value} → {transition.new_stage.value}. "
            f"Allowed: {sorted(s.value for s in allowed)}"
        )

    if transition.new_stage == ApplicationStage.REJECTED:
        if not transition.rejection_reason or len(transition.rejection_reason.strip()) < 10:
            raise InvalidStageTransitionError("Rejection reason wajib min 10 karakter")
        app_obj.rejection_reason = transition.rejection_reason
        app_obj.rejection_stage = app_obj.stage  # snapshot stage saat di-reject

    if transition.notes:
        app_obj.notes = (
            f"{app_obj.notes}\n---\n{transition.notes}" if app_obj.notes else transition.notes
        )

    app_obj.stage = transition.new_stage
    app_obj.stage_changed_at = datetime.now(UTC)

    # Increment slots_filled kalau HIRED
    if transition.new_stage == ApplicationStage.HIRED:
        opening = await get_job_opening(session, app_obj.job_opening_id)
        opening.slots_filled += 1
        if opening.slots_filled >= opening.slots_needed:
            opening.status = JobOpeningStatus.FILLED
            opening.closed_date = date.today()

    await session.commit()
    await session.refresh(app_obj)
    return app_obj


async def list_applications_for_opening(
    session: AsyncSession, opening_id: UUID
) -> list[JobApplication]:
    stmt = (
        select(JobApplication)
        .where(JobApplication.job_opening_id == opening_id)
        .order_by(JobApplication.stage_changed_at.desc().nulls_last())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def build_pipeline_buckets(
    session: AsyncSession, opening_id: UUID
) -> tuple[JobOpening, dict[ApplicationStage, list[JobApplication]]]:
    """Bucket all applications by stage untuk kanban view."""
    opening = await get_job_opening(session, opening_id)
    applications = await list_applications_for_opening(session, opening_id)

    buckets: dict[ApplicationStage, list[JobApplication]] = {
        stage: [] for stage in ApplicationStage
    }
    for app_obj in applications:
        buckets[app_obj.stage].append(app_obj)
    return opening, buckets


# ─── Helpers ───────────────────────────────────────────────────────


def calc_total_pages(total: int, page_size: int) -> int:
    if total == 0:
        return 0
    return math.ceil(total / page_size)


def days_in_stage(app_obj: JobApplication) -> int | None:
    if app_obj.stage_changed_at is None:
        return None
    delta = datetime.now(UTC) - app_obj.stage_changed_at
    return delta.days
