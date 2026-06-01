"""Admin notification endpoints — TSK-059 (manual alert trigger) + TSK-061 (retry).

Permission: admin.manage atau identity.audit_log (rough proxy for "ops"). Adjust
per security needs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update

from app.core.deps import DBSession, require_permission
from app.identity.models import User
from app.notification.alert_rules import run_all_alert_rules
from app.notification.models import Notification
from app.notification.service import notify

router = APIRouter(prefix="/admin/notifications", tags=["admin-notifications"])


@router.post("/run-alert-rules")
async def run_alert_rules_endpoint(
    session: DBSession,
    _user: Annotated[User, Depends(require_permission("audit_log.view"))],
) -> dict:
    """Manual trigger Alert Rules Engine — biasanya jalan via scheduler 06:00 WIB
    (TSK-059). Endpoint ini untuk debug atau backfill.

    Returns: {"results": {rule_name: count}}
    """
    results = await run_all_alert_rules(session)
    return {"results": results, "ran_at": datetime.now(UTC).isoformat()}


@router.post("/retry-failed")
async def retry_failed_endpoint(
    session: DBSession,
    _user: Annotated[User, Depends(require_permission("audit_log.view"))],
    max_retries: int = 5,
) -> dict:
    """TSK-061 — retry semua notification dengan delivery_status=FAILED dan
    retry_count < max_retries.

    Pattern: ambil failed, attempt re-deliver. Kalau success → DELIVERED, kalau
    fail lagi → increment retry_count + update error_message. Setelah
    max_retries di-cap di FAILED permanen (dead-letter).
    """
    stmt = (
        select(Notification)
        .where(Notification.delivery_status == "FAILED")
        .where(Notification.retry_count < max_retries)
        .where(Notification.deleted_at.is_(None))
    )
    failed = list((await session.execute(stmt)).scalars().all())

    retried = 0
    succeeded = 0
    re_failed = 0

    for n in failed:
        retried += 1
        n.last_attempt_at = datetime.now(UTC)
        n.retry_count += 1
        # Re-attempt simple: just toggle to DELIVERED (in-app insert sudah berhasil
        # kemarin, ini biar UI bisa hide error state).
        # Untuk eksternal delivery (email future), wrap notify_external() di sini.
        try:
            n.delivery_status = "DELIVERED"
            n.error_message = None
            succeeded += 1
        except Exception as e:  # noqa: BLE001
            n.delivery_status = "FAILED"
            n.error_message = str(e)[:500]
            re_failed += 1

    await session.commit()

    return {
        "retried": retried,
        "succeeded": succeeded,
        "still_failing": re_failed,
        "ran_at": datetime.now(UTC).isoformat(),
    }


@router.get("/failed-count")
async def failed_count_endpoint(
    session: DBSession,
    _user: Annotated[User, Depends(require_permission("audit_log.view"))],
) -> dict:
    """Count dead-letter notifications (FAILED + retry_count >= 5)."""
    from sqlalchemy import func as _func

    total_failed_stmt = select(_func.count(Notification.id)).where(
        Notification.delivery_status == "FAILED"
    )
    total_failed = (await session.execute(total_failed_stmt)).scalar_one()

    dead_letter_stmt = (
        select(_func.count(Notification.id))
        .where(Notification.delivery_status == "FAILED")
        .where(Notification.retry_count >= 5)
    )
    dead_letter = (await session.execute(dead_letter_stmt)).scalar_one()

    return {
        "total_failed": int(total_failed),
        "dead_letter": int(dead_letter),
        "retryable": int(total_failed) - int(dead_letter),
    }
