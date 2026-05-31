"""FastAPI router untuk Notification domain — TSK-057.

Endpoints (all scoped to current authenticated user):
- GET    /api/v1/notifications              — paginated list (filter unread)
- GET    /api/v1/notifications/unread-count — cheap badge count
- POST   /api/v1/notifications/{id}/read    — mark single read
- POST   /api/v1/notifications/read-all     — mark all unread → read
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import DBSession, get_current_user
from app.identity.models import User
from app.notification import service
from app.notification.schemas import (
    MarkAllReadResponse,
    MarkReadResponse,
    NotificationListResponse,
    NotificationOut,
    UnreadCountResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    session: DBSession,
    current_user: Annotated[User, Depends(get_current_user)],
) -> UnreadCountResponse:
    """Cheap unread count untuk bell badge. Poll setiap 30s."""
    count = await service.get_unread_count(session, current_user.id)
    return UnreadCountResponse(unread_count=count)


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    session: DBSession,
    current_user: Annotated[User, Depends(get_current_user)],
    unread_only: bool = Query(False, description="Filter ke unread saja"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> NotificationListResponse:
    """Paginated list, ordered by created_at DESC."""
    items, total = await service.list_for_user(
        session,
        current_user.id,
        unread_only=unread_only,
        page=page,
        page_size=page_size,
    )
    unread = await service.get_unread_count(session, current_user.id)
    return NotificationListResponse(
        items=[NotificationOut.model_validate(n) for n in items],
        total=total,
        unread_count=unread,
        page=page,
        page_size=page_size,
    )


@router.post("/read-all", response_model=MarkAllReadResponse)
async def mark_all_read(
    session: DBSession,
    current_user: Annotated[User, Depends(get_current_user)],
) -> MarkAllReadResponse:
    """Mark semua unread → read."""
    count = await service.mark_all_read(session, current_user.id)
    await session.commit()
    return MarkAllReadResponse(marked_count=count)


@router.post("/{notif_id}/read", response_model=MarkReadResponse)
async def mark_read(
    notif_id: UUID,
    session: DBSession,
    current_user: Annotated[User, Depends(get_current_user)],
) -> MarkReadResponse:
    """Mark satu notification read. Returns 404 jika bukan milik user atau tidak ada."""
    notif = await service.mark_read(session, notif_id, current_user.id)
    if notif is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Notifikasi tidak ditemukan"},
        )
    await session.commit()
    assert notif.read_at is not None  # set by service
    return MarkReadResponse(id=notif.id, read_at=notif.read_at)
