"""THR router — TSK-053 (US-FN-003)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.audit import audit_log
from app.core.deps import DBSession, get_current_user, require_permission
from app.identity.models import User
from app.organization.models import Employee
from app.payroll import thr_service as service
from app.payroll.thr_schemas import (
    ThrGenerateRequest,
    ThrGenerateResponse,
    ThrMarkPaidRequest,
    ThrOut,
)
from app.payroll.thr_service import ThrAlreadyPaidError, ThrNotFoundError

router = APIRouter(prefix="/payroll/thr", tags=["payroll-thr"])


async def _enrich(session, t) -> ThrOut:
    out = ThrOut.model_validate(t)
    emp = await session.get(Employee, t.employee_id)
    if emp:
        out.employee_name = emp.full_name
        if emp.user_id:
            from app.identity.models import User as _User
            user_stmt = select(_User.nik).where(_User.id == emp.user_id)
            nik = (await session.execute(user_stmt)).scalar_one_or_none()
            out.employee_nik = nik
    return out


# Static routes first (NC-DEV-002)
@router.get("/mine", response_model=list[ThrOut])
async def list_my_thr_endpoint(
    session: DBSession,
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ThrOut]:
    """Self-service: current user lihat THR yang sudah APPROVED/PAID."""
    rows = await service.list_my_thr(session, current_user.id)
    return [await _enrich(session, t) for t in rows]


@router.post(
    "/generate", response_model=ThrGenerateResponse, status_code=status.HTTP_201_CREATED
)
async def generate_thr_endpoint(
    data: ThrGenerateRequest,
    session: DBSession,
    user: Annotated[User, Depends(require_permission("payroll.create"))],
) -> ThrGenerateResponse:
    """Bulk generate THR untuk semua eligible employee.

    Prorata <12 bulan masa kerja (US-FN-003 AC-02).
    """
    result = await service.generate_thr_bulk(session, data, user.id)
    await audit_log(
        session=session,
        actor=user,
        action="THR_BULK_GENERATED",
        resource_type="thr_payment",
        resource_id=f"year-{data.thr_year}",
        after_state={
            "generated": result.generated,
            "skipped": result.skipped,
            "total_amount": str(result.total_amount_idr),
        },
    )
    return result


@router.get("", response_model=list[ThrOut])
async def list_thr_endpoint(
    session: DBSession,
    _user: Annotated[User, Depends(require_permission("payroll.view"))],
    thr_year: int | None = None,
    status_filter: str | None = None,
) -> list[ThrOut]:
    rows = await service.list_thr(session, thr_year=thr_year, status=status_filter)
    return [await _enrich(session, t) for t in rows]


@router.post("/{thr_id}/mark-paid", response_model=ThrOut)
async def mark_thr_paid_endpoint(
    thr_id: UUID,
    data: ThrMarkPaidRequest,
    session: DBSession,
    user: Annotated[User, Depends(require_permission("payroll.approve"))],
) -> ThrOut:
    """Finance mark THR as PAID setelah transfer."""
    try:
        t = await service.mark_thr_paid(
            session, thr_id, data.payment_date, data.transfer_ref
        )
    except ThrNotFoundError as e:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}
        ) from e
    except ThrAlreadyPaidError as e:
        raise HTTPException(
            status_code=409, detail={"code": "ALREADY_PAID", "message": str(e)}
        ) from e

    await audit_log(
        session=session,
        actor=user,
        action="THR_PAID",
        resource_type="thr_payment",
        resource_id=str(t.id),
        after_state={"payment_date": str(t.payment_date), "ref": t.transfer_ref},
    )

    # Notify employee
    try:
        from app.notification.models import NotificationType
        from app.notification.templates import notify_from_template

        emp = await session.get(Employee, t.employee_id)
        if emp and emp.user_id:
            await notify_from_template(
                session,
                user_id=emp.user_id,
                type=NotificationType.SYSTEM,
                context={
                    "title": f"THR {t.thr_year} sudah ditransfer",
                    "body": f"Rp {t.thr_amount:,.0f} ditransfer pada {t.payment_date}.",
                    "link": "/my-payslips",
                },
            )
            await session.commit()
    except Exception:  # noqa: BLE001
        pass

    return await _enrich(session, t)
