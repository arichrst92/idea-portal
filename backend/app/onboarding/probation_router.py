"""Probation Assessment router — TSK-044."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit_log
from app.core.deps import CurrentUser, DBSession, require_permission
from app.identity.models import User
from app.onboarding.models import ProbationAssessment
from app.organization.models import Employee

router = APIRouter(prefix="/probation", tags=["probation"])


# ─── Schemas ──────────────────────────────────────────────────────


class ProbationDecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(PASS|EXTEND|TERMINATE)$")
    score: Decimal | None = Field(None, ge=0, le=100)
    notes: str | None = None
    extended_to: date | None = None  # required kalau decision=EXTEND


class ProbationOut(BaseModel):
    id: UUID
    employee_id: UUID
    employee_name: str | None = None
    employee_nik: str | None = None
    probation_start: date
    probation_end: date
    decision: str
    score: Decimal | None
    notes: str | None
    extended_to: date | None
    reviewer_user_id: UUID | None
    decided_at: datetime | None
    created_at: datetime
    days_until_end: int | None = None


async def _enrich(session: AsyncSession, p: ProbationAssessment) -> ProbationOut:
    from app.identity.models import User as _User
    out = ProbationOut(
        id=p.id,
        employee_id=p.employee_id,
        probation_start=p.probation_start,
        probation_end=p.probation_end,
        decision=p.decision,
        score=p.score,
        notes=p.notes,
        extended_to=p.extended_to,
        reviewer_user_id=p.reviewer_user_id,
        decided_at=p.decided_at,
        created_at=p.created_at,
        days_until_end=(p.probation_end - date.today()).days if p.probation_end else None,
    )
    emp = await session.get(Employee, p.employee_id)
    if emp:
        out.employee_name = emp.full_name
        if emp.user_id:
            user_stmt = select(_User.nik).where(_User.id == emp.user_id)
            nik = (await session.execute(user_stmt)).scalar_one_or_none()
            out.employee_nik = nik
    return out


# ─── Endpoints ────────────────────────────────────────────────────


@router.get("", response_model=list[ProbationOut])
async def list_probations_endpoint(
    session: DBSession,
    _user: Annotated[User, Depends(require_permission("employee.view"))],
    decision_filter: str | None = Query(None, description="PENDING/PASS/EXTEND/TERMINATE"),
) -> list[ProbationOut]:
    """List all probation assessments. Filter by decision optional."""
    stmt = select(ProbationAssessment)
    if decision_filter:
        stmt = stmt.where(ProbationAssessment.decision == decision_filter)
    stmt = stmt.order_by(ProbationAssessment.probation_end.asc())
    rows = list((await session.execute(stmt)).scalars().all())
    return [await _enrich(session, p) for p in rows]


@router.post("/{employee_id}", response_model=ProbationOut, status_code=status.HTTP_201_CREATED)
async def create_probation_endpoint(
    employee_id: UUID,
    session: DBSession,
    _current: CurrentUser,
    _user: Annotated[User, Depends(require_permission("employee.edit"))],
) -> ProbationOut:
    """Auto-create PENDING assessment row dari employee joined_date + probation_end_date.

    Hanya buat kalau belum ada PENDING untuk employee ini.
    """
    emp = await session.get(Employee, employee_id)
    if emp is None:
        raise HTTPException(404, detail={"message": "Employee not found"})
    if not emp.joined_date or not emp.probation_end_date:
        raise HTTPException(
            422,
            detail={
                "message": "Employee belum punya joined_date / probation_end_date. Set dulu."
            },
        )

    # Check if PENDING already exists
    existing_stmt = (
        select(ProbationAssessment)
        .where(ProbationAssessment.employee_id == employee_id)
        .where(ProbationAssessment.decision == "PENDING")
    )
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()
    if existing:
        return await _enrich(session, existing)

    pa = ProbationAssessment(
        employee_id=employee_id,
        probation_start=emp.joined_date,
        probation_end=emp.probation_end_date,
        decision="PENDING",
    )
    session.add(pa)
    await session.commit()
    await session.refresh(pa)
    return await _enrich(session, pa)


@router.post("/{probation_id}/decide", response_model=ProbationOut)
async def decide_probation_endpoint(
    probation_id: UUID,
    data: ProbationDecisionRequest,
    session: DBSession,
    current_user: CurrentUser,
    _user: Annotated[User, Depends(require_permission("employee.edit"))],
) -> ProbationOut:
    """Submit decision (PASS / EXTEND / TERMINATE)."""
    pa = await session.get(ProbationAssessment, probation_id)
    if pa is None:
        raise HTTPException(404, detail={"message": "Probation assessment not found"})
    if pa.decision != "PENDING":
        raise HTTPException(
            409,
            detail={
                "message": f"Decision sudah diambil ({pa.decision}). Tidak bisa diubah."
            },
        )

    if data.decision == "EXTEND" and data.extended_to is None:
        raise HTTPException(
            422, detail={"message": "extended_to wajib untuk decision=EXTEND"}
        )

    pa.decision = data.decision
    pa.score = data.score
    pa.notes = data.notes
    pa.reviewer_user_id = current_user.id
    pa.decided_at = datetime.now(UTC)

    if data.decision == "EXTEND":
        pa.extended_to = data.extended_to
        # Update Employee.probation_end_date
        emp = await session.get(Employee, pa.employee_id)
        if emp:
            emp.probation_end_date = data.extended_to

    await session.commit()
    await session.refresh(pa)

    await audit_log(
        session=session,
        actor=current_user,
        action="PROBATION_DECISION",
        resource_type="probation_assessment",
        resource_id=str(pa.id),
        after_state={"decision": data.decision, "score": str(data.score) if data.score else None},
    )

    # Notify employee
    try:
        from app.notification.models import NotificationType
        from app.notification.templates import notify_from_template

        emp = await session.get(Employee, pa.employee_id)
        if emp and emp.user_id:
            await notify_from_template(
                session,
                user_id=emp.user_id,
                type=NotificationType.SYSTEM,
                context={
                    "title": f"Probation Assessment: {data.decision}",
                    "body": (
                        f"Hasil review probation Anda: {data.decision}."
                        + (f" Score: {data.score}." if data.score else "")
                        + (f" Notes: {data.notes}." if data.notes else "")
                    ),
                    "link": "/welcome",
                },
            )
            await session.commit()
    except Exception:  # noqa: BLE001
        pass

    return await _enrich(session, pa)
