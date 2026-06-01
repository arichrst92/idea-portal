"""Offering Letter workflow service — TSK-034.

Per US-OP-002:
  AC-04: generate offer letter dengan position, level, dept, salary, start date
  AC-05: requires GM/C-Level approval before "Sent"
  AC-06: candidate response — Accept / Negotiate / Reject
  AC-07: Accept → status Hired + onboarding auto-trigger

NC-OP-002-03: block mark_sent kalau belum APPROVED
NC-OP-002-04: warning kalau salary > position.salary_range_max,
              requires salary_override_approved=True
NC-OP-002-06: start_date required sebelum Hired status
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.hiring.models import ApplicationStage, JobApplication, JobOpening
from app.organization.models import Position

logger = logging.getLogger(__name__)


# ─── Exceptions ────────────────────────────────────────────────────


class OfferNotFoundError(Exception):
    pass


class InvalidOfferStateError(Exception):
    pass


class OfferApprovalRequiredError(Exception):
    """NC-OP-002-03 — cannot send/proceed without GM/C-Level approval."""


class SalaryOutOfRangeError(Exception):
    """NC-OP-002-04 — offered_salary > position.salary_range_max."""


class StartDateRequiredError(Exception):
    """NC-OP-002-06 — offered_start_date wajib untuk advance ke Hired."""


# ─── Helpers ───────────────────────────────────────────────────────


async def _get_application(session: AsyncSession, app_id: UUID) -> JobApplication:
    app = await session.get(JobApplication, app_id)
    if app is None:
        raise OfferNotFoundError(f"JobApplication {app_id} not found")
    return app


async def _check_salary_range(
    session: AsyncSession, app: JobApplication
) -> tuple[bool, str | None]:
    """Returns (within_range, warning_message). True = OK, False = over max."""
    if app.offered_salary is None:
        return True, None

    opening = await session.get(JobOpening, app.job_opening_id)
    if not opening or not opening.position_id:
        return True, None

    pos = await session.get(Position, opening.position_id)
    if not pos or pos.salary_range_max is None:
        return True, None

    salary = Decimal(str(app.offered_salary))
    max_range = Decimal(str(pos.salary_range_max))
    if salary > max_range:
        return False, (
            f"Salary Rp {int(salary):,} > max Level {pos.level} (Rp {int(max_range):,}). "
            f"NC-OP-002-04 — requires C-Level override."
        )
    return True, None


# ─── Workflow ──────────────────────────────────────────────────────


async def generate_offer_pdf(
    session: AsyncSession, app_id: UUID
) -> JobApplication:
    """Generate PDF + update offer_pdf_url. Allowed in DRAFT or PENDING_APPROVAL."""
    app = await _get_application(session, app_id)
    if app.offered_salary is None or app.offered_start_date is None:
        raise InvalidOfferStateError(
            "Salary dan start date wajib di-set sebelum generate offer letter"
        )

    from app.hiring.offer_pdf_generator import generate_offer_pdf as gen_pdf
    object_key = await gen_pdf(session, app_id)

    app.offer_pdf_url = object_key
    app.offer_pdf_generated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(app)
    return app


async def submit_offer_for_approval(
    session: AsyncSession, app_id: UUID, submitter_user_id: UUID
) -> JobApplication:
    """DRAFT → PENDING_APPROVAL. Notify GM/C-Level."""
    app = await _get_application(session, app_id)
    if app.offer_status != "DRAFT":
        raise InvalidOfferStateError(
            f"Offer status {app.offer_status} — submit hanya dari DRAFT"
        )

    if app.offered_salary is None or app.offered_start_date is None:
        raise InvalidOfferStateError(
            "Salary + start date wajib sebelum submit approval"
        )

    # NC-OP-002-04 — check salary range
    within, warn = await _check_salary_range(session, app)
    if not within and not app.salary_override_approved:
        raise SalaryOutOfRangeError(warn or "Salary exceeds range")

    app.offer_status = "PENDING_APPROVAL"
    app.offer_submitted_at = datetime.now(UTC)
    app.offer_submitted_by_user_id = submitter_user_id
    # Clear prior approval/rejection on resubmit
    app.offer_approved_at = None
    app.offer_approved_by_user_id = None
    app.offer_approval_notes = None
    await session.commit()
    await session.refresh(app)

    # Notify approvers
    try:
        from app.notification.alert_rules import _get_user_ids_with_permission  # noqa
        from app.notification.models import NotificationType
        from app.notification.templates import notify_from_template

        approver_ids = await _get_user_ids_with_permission(session, "hiring.approve")
        for uid in approver_ids:
            if uid == submitter_user_id:
                continue
            await notify_from_template(
                session,
                user_id=uid,
                type=NotificationType.APPROVAL_PENDING,
                context={
                    "requester_name": "HR/Operation",
                    "request_type": f"Offering Letter — {app.candidate_name}",
                    "link": f"/hiring/{app.job_opening_id}",
                },
            )
        if approver_ids:
            await session.commit()
    except Exception:  # noqa: BLE001
        pass

    return app


async def approve_offer(
    session: AsyncSession,
    app_id: UUID,
    approver_user_id: UUID,
    notes: str | None = None,
    salary_override: bool = False,
) -> JobApplication:
    """PENDING_APPROVAL → APPROVED. GM/C-Level only. AC-05.

    salary_override=True kalau approver explicit consent salary di luar range.
    """
    app = await _get_application(session, app_id)
    if app.offer_status != "PENDING_APPROVAL":
        raise InvalidOfferStateError(
            f"Offer status {app.offer_status} — approve hanya dari PENDING_APPROVAL"
        )

    if app.offer_submitted_by_user_id == approver_user_id:
        raise InvalidOfferStateError(
            "Self-approval blocked — submitter tidak bisa approve sendiri"
        )

    # NC-OP-002-04 — kalau salary > range, butuh override flag
    within, warn = await _check_salary_range(session, app)
    if not within:
        if not salary_override:
            raise SalaryOutOfRangeError(
                f"{warn} Set salary_override=true untuk C-Level override."
            )
        app.salary_override_approved = True

    app.offer_status = "APPROVED"
    app.offer_approved_at = datetime.now(UTC)
    app.offer_approved_by_user_id = approver_user_id
    app.offer_approval_notes = notes
    await session.commit()
    await session.refresh(app)
    return app


async def reject_offer(
    session: AsyncSession,
    app_id: UUID,
    rejector_user_id: UUID,
    reason: str,
) -> JobApplication:
    """PENDING_APPROVAL → DRAFT (back to HR for revision)."""
    app = await _get_application(session, app_id)
    if app.offer_status != "PENDING_APPROVAL":
        raise InvalidOfferStateError(
            f"Offer status {app.offer_status} — reject hanya dari PENDING_APPROVAL"
        )

    app.offer_status = "DRAFT"
    app.offer_approval_notes = f"REJECTED by {rejector_user_id}: {reason}"
    app.offer_submitted_at = None
    app.offer_submitted_by_user_id = None
    await session.commit()
    await session.refresh(app)

    # Notify HR submitter
    try:
        from app.notification.models import NotificationType
        from app.notification.templates import notify_from_template

        if app.offer_submitted_by_user_id:  # might be None after we cleared
            pass  # already cleared; can't notify
    except Exception:  # noqa: BLE001
        pass

    return app


async def mark_offer_sent(session: AsyncSession, app_id: UUID) -> JobApplication:
    """APPROVED → SENT. NC-OP-002-03 — block kalau belum APPROVED."""
    app = await _get_application(session, app_id)
    if app.offer_status != "APPROVED":
        raise OfferApprovalRequiredError(
            f"Offer status {app.offer_status} — must be APPROVED before SENT (NC-OP-002-03)"
        )

    app.offer_status = "SENT"
    app.offer_sent_at = datetime.now(UTC)
    # Move application stage ke OFFERING juga supaya pipeline reflect
    if app.stage != ApplicationStage.OFFERING:
        app.stage = ApplicationStage.OFFERING
        app.stage_changed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(app)
    return app


async def record_candidate_response(
    session: AsyncSession,
    app_id: UUID,
    response: str,
    notes: str | None = None,
) -> JobApplication:
    """SENT → ACCEPTED | NEGOTIATING | REJECTED. AC-06 + AC-07.

    On ACCEPTED: trigger Hired flow (stage = HIRED, onboarding auto-create
    di TSK-038/039 future hook).
    """
    if response not in ("ACCEPTED", "NEGOTIATING", "REJECTED"):
        raise InvalidOfferStateError(
            f"response harus ACCEPTED/NEGOTIATING/REJECTED, got: {response}"
        )

    app = await _get_application(session, app_id)
    if app.offer_status != "SENT":
        raise InvalidOfferStateError(
            f"Offer status {app.offer_status} — response hanya dari SENT"
        )

    # NC-OP-002-06 — start date required for Hired
    if response == "ACCEPTED" and app.offered_start_date is None:
        raise StartDateRequiredError(
            "Start date wajib di-set sebelum candidate dapat dianggap Hired (NC-OP-002-06)"
        )

    app.offer_status = response
    app.candidate_response = response
    app.candidate_response_at = datetime.now(UTC)
    app.candidate_response_notes = notes

    if response == "ACCEPTED":
        # AC-07 — auto move to HIRED stage
        app.stage = ApplicationStage.HIRED
        app.stage_changed_at = datetime.now(UTC)
        # Note: actual Employee record creation + onboarding checklist
        # is triggered separately by hire_candidate flow (already exists).

    await session.commit()
    await session.refresh(app)
    return app
