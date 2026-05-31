"""Notification service — TSK-057.

Single entry point: `notify(session, user_id, type, ...)` creates & flushes
a notification row. Callers from other domains should use this rather than
hitting the model directly.

Future: TSK-058 templates wrap this with `notify_from_template(session, user_id, type, context)`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.notification.models import (
    Notification,
    NotificationPriority,
    NotificationType,
)

logger = logging.getLogger(__name__)


async def notify(
    session: AsyncSession,
    *,
    user_id: UUID,
    type: NotificationType,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    meta: dict[str, Any] | None = None,
) -> Notification:
    """Create a single notification row.

    Caller's session must commit after — service only adds + flushes.
    """
    notif = Notification(
        user_id=user_id,
        type=type.value if isinstance(type, NotificationType) else type,
        priority=priority.value if isinstance(priority, NotificationPriority) else priority,
        title=title,
        body=body,
        link_url=link_url,
        meta=meta,
    )
    session.add(notif)
    await session.flush()
    logger.info("notify: user=%s type=%s title=%r", user_id, type, title[:60])
    return notif


async def notify_bulk(
    session: AsyncSession,
    *,
    user_ids: list[UUID],
    type: NotificationType,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    meta: dict[str, Any] | None = None,
) -> int:
    """Bulk create — same content fan-out to many users.

    Returns count of created rows.
    """
    if not user_ids:
        return 0
    notifs = [
        Notification(
            user_id=uid,
            type=type.value if isinstance(type, NotificationType) else type,
            priority=priority.value if isinstance(priority, NotificationPriority) else priority,
            title=title,
            body=body,
            link_url=link_url,
            meta=meta,
        )
        for uid in user_ids
    ]
    session.add_all(notifs)
    await session.flush()
    logger.info("notify_bulk: %d users type=%s", len(user_ids), type)
    return len(notifs)


async def get_unread_count(session: AsyncSession, user_id: UUID) -> int:
    """Cheap unread count for badge."""
    stmt = (
        select(func.count(Notification.id))
        .where(Notification.user_id == user_id)
        .where(Notification.read_at.is_(None))
        .where(Notification.deleted_at.is_(None))
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def list_for_user(
    session: AsyncSession,
    user_id: UUID,
    *,
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Notification], int]:
    """Paginated list. Returns (items, total)."""
    base = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .where(Notification.deleted_at.is_(None))
    )
    if unread_only:
        base = base.where(Notification.read_at.is_(None))

    # Count
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    # Page
    offset = max(0, (page - 1) * page_size)
    page_stmt = base.order_by(Notification.created_at.desc()).offset(offset).limit(page_size)
    rows = (await session.execute(page_stmt)).scalars().all()
    return list(rows), total


async def mark_read(
    session: AsyncSession, notif_id: UUID, user_id: UUID
) -> Notification | None:
    """Mark single notification read. Returns row or None if not owned/exists."""
    stmt = (
        select(Notification)
        .where(Notification.id == notif_id)
        .where(Notification.user_id == user_id)
        .where(Notification.deleted_at.is_(None))
    )
    notif = (await session.execute(stmt)).scalar_one_or_none()
    if notif is None:
        return None
    if notif.read_at is None:
        notif.read_at = datetime.now(timezone.utc)
        await session.flush()
    return notif


async def mark_all_read(session: AsyncSession, user_id: UUID) -> int:
    """Mark all unread → read. Returns count marked."""
    now = datetime.now(timezone.utc)
    stmt = (
        update(Notification)
        .where(Notification.user_id == user_id)
        .where(Notification.read_at.is_(None))
        .where(Notification.deleted_at.is_(None))
        .values(read_at=now)
    )
    result = await session.execute(stmt)
    await session.flush()
    return result.rowcount or 0
