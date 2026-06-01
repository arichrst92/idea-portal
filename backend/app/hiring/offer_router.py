"""Offering Letter workflow router — TSK-034.

Endpoints (under /api/v1/hiring prefix di main.py):
- POST /applications/{app_id}/offer/generate-pdf
- POST /applications/{app_id}/offer/submit-approval
- POST /applications/{app_id}/offer/approve     (GM/C-Level)
- POST /applications/{app_id}/offer/reject      (GM/C-Level)
- POST /applications/{app_id}/offer/mark-sent
- POST /applications/{app_id}/offer/candidate-response
- GET  /applications/{app_id}/offer/pdf-url     (presigned download)
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.audit import audit_log
from app.core.deps import DBSession, require_permission
from app.core.storage import get_presigned_url
from app.identity.models import User
from app.hiring import offer_service as service
from app.hiring.offer_service import (
    InvalidOfferStateError,
    OfferApprovalRequiredError,
    OfferNotFoundError,
    SalaryOutOfRangeError,
    StartDateRequiredError,
)

router = APIRouter(prefix="/hiring", tags=["hiring-offers"])


# ─── Schemas ──────────────────────────────────────────────────────


class OfferApprovalRequest(BaseModel):
    notes: str | None = None
    salary_override: bool = False


class OfferRejectRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class CandidateResponseRequest(BaseModel):
    response: str = Field(..., pattern="^(ACCEPTED|NEGOTIATING|REJECTED)$")
    notes: str | None = None


class OfferOut(BaseModel):
    application_id: UUID
    offer_status: str
    offer_pdf_url: str | None
    offer_pdf_generated_at: datetime | None
    offered_salary: str | None
    offered_start_date: str | None
    offer_submitted_at: datetime | None
    offer_approved_at: datetime | None
    offer_sent_at: datetime | None
    candidate_response: str | None
    candidate_response_at: datetime | None
    salary_override_approved: bool


def _to_out(app) -> OfferOut:
    return OfferOut(
        application_id=app.id,
        offer_status=app.offer_status,
        offer_pdf_url=app.offer_pdf_url,
        offer_pdf_generated_at=app.offer_pdf_generated_at,
        offered_salary=str(app.offered_salary) if app.offered_salary is not None else None,
        offered_start_date=str(app.offered_start_date) if app.offered_start_date else None,
        offer_submitted_at=app.offer_submitted_at,
        offer_approved_at=app.offer_approved_at,
        offer_sent_at=app.offer_sent_at,
        candidate_response=app.candidate_response,
        candidate_response_at=app.candidate_response_at,
        salary_override_approved=app.salary_override_approved,
    )


# ─── Endpoints ────────────────────────────────────────────────────


@router.post("/applications/{app_id}/offer/generate-pdf", response_model=OfferOut)
async def generate_offer_pdf_endpoint(
    app_id: UUID,
    session: DBSession,
    user: Annotated[User, Depends(require_permission("hiring.create"))],
) -> OfferOut:
    """Generate Offering Letter PDF + upload to MinIO."""
    try:
        app = await service.generate_offer_pdf(session, app_id)
    except OfferNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidOfferStateError as e:
        raise HTTPException(status_code=422, detail={"code": "INVALID_STATE", "message": str(e)}) from e
    except RuntimeError as e:
        # WeasyPrint native libs missing
        raise HTTPException(status_code=500, detail={"code": "PDF_GEN_FAILED", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="OFFER_PDF_GENERATED",
        resource_type="job_application", resource_id=str(app_id),
    )
    return _to_out(app)


@router.get("/applications/{app_id}/offer/pdf-url")
async def get_offer_pdf_url_endpoint(
    app_id: UUID,
    session: DBSession,
    _user: Annotated[User, Depends(require_permission("hiring.view"))],
) -> dict:
    """Presigned download URL for offer PDF."""
    try:
        app = await service._get_application(session, app_id)
    except OfferNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e

    if not app.offer_pdf_url:
        return {"url": None}
    url = get_presigned_url(app.offer_pdf_url, expires_seconds=3600)
    return {"url": url}


@router.post("/applications/{app_id}/offer/submit-approval", response_model=OfferOut)
async def submit_offer_endpoint(
    app_id: UUID,
    session: DBSession,
    user: Annotated[User, Depends(require_permission("hiring.create"))],
) -> OfferOut:
    """Submit offer ke GM/C-Level approval queue."""
    try:
        app = await service.submit_offer_for_approval(session, app_id, user.id)
    except OfferNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidOfferStateError as e:
        raise HTTPException(status_code=422, detail={"code": "INVALID_STATE", "message": str(e)}) from e
    except SalaryOutOfRangeError as e:
        raise HTTPException(status_code=422, detail={"code": "SALARY_OVER_RANGE", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="OFFER_SUBMITTED_FOR_APPROVAL",
        resource_type="job_application", resource_id=str(app_id),
    )
    return _to_out(app)


@router.post("/applications/{app_id}/offer/approve", response_model=OfferOut)
async def approve_offer_endpoint(
    app_id: UUID,
    data: OfferApprovalRequest,
    session: DBSession,
    user: Annotated[User, Depends(require_permission("hiring.approve"))],
) -> OfferOut:
    """GM/C-Level approve offer (AC-05)."""
    try:
        app = await service.approve_offer(
            session, app_id, user.id, notes=data.notes,
            salary_override=data.salary_override,
        )
    except OfferNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidOfferStateError as e:
        raise HTTPException(status_code=422, detail={"code": "INVALID_STATE", "message": str(e)}) from e
    except SalaryOutOfRangeError as e:
        raise HTTPException(status_code=422, detail={"code": "SALARY_OVER_RANGE", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="OFFER_APPROVED",
        resource_type="job_application", resource_id=str(app_id),
        after_state={"notes": data.notes, "salary_override": data.salary_override},
    )
    return _to_out(app)


@router.post("/applications/{app_id}/offer/reject", response_model=OfferOut)
async def reject_offer_endpoint(
    app_id: UUID,
    data: OfferRejectRequest,
    session: DBSession,
    user: Annotated[User, Depends(require_permission("hiring.approve"))],
) -> OfferOut:
    try:
        app = await service.reject_offer(session, app_id, user.id, data.reason)
    except OfferNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidOfferStateError as e:
        raise HTTPException(status_code=422, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="OFFER_REJECTED",
        resource_type="job_application", resource_id=str(app_id),
        after_state={"reason": data.reason},
    )
    return _to_out(app)


@router.post("/applications/{app_id}/offer/mark-sent", response_model=OfferOut)
async def mark_offer_sent_endpoint(
    app_id: UUID,
    session: DBSession,
    user: Annotated[User, Depends(require_permission("hiring.create"))],
) -> OfferOut:
    """Mark offer as SENT setelah APPROVED (NC-OP-002-03)."""
    try:
        app = await service.mark_offer_sent(session, app_id)
    except OfferNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except OfferApprovalRequiredError as e:
        raise HTTPException(status_code=422, detail={"code": "APPROVAL_REQUIRED", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="OFFER_MARKED_SENT",
        resource_type="job_application", resource_id=str(app_id),
    )
    return _to_out(app)


@router.post("/applications/{app_id}/offer/candidate-response", response_model=OfferOut)
async def candidate_response_endpoint(
    app_id: UUID,
    data: CandidateResponseRequest,
    session: DBSession,
    user: Annotated[User, Depends(require_permission("hiring.create"))],
) -> OfferOut:
    """Record candidate response (AC-06). ACCEPTED → auto Hired (AC-07)."""
    try:
        app = await service.record_candidate_response(
            session, app_id, data.response, notes=data.notes
        )
    except OfferNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidOfferStateError as e:
        raise HTTPException(status_code=422, detail={"code": "INVALID_STATE", "message": str(e)}) from e
    except StartDateRequiredError as e:
        raise HTTPException(status_code=422, detail={"code": "START_DATE_REQUIRED", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="OFFER_CANDIDATE_RESPONSE",
        resource_type="job_application", resource_id=str(app_id),
        after_state={"response": data.response, "notes": data.notes},
    )
    return _to_out(app)
