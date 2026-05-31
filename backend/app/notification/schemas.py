"""Pydantic schemas — TSK-057."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.notification.models import NotificationPriority, NotificationType


class NotificationOut(BaseModel):
    """Single notification — list/detail response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: NotificationType
    priority: NotificationPriority
    title: str
    body: str | None
    link_url: str | None
    meta: dict[str, Any] | None
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Paginated list."""

    items: list[NotificationOut]
    total: int
    unread_count: int
    page: int
    page_size: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkReadResponse(BaseModel):
    """Echo after mark read."""

    id: UUID
    read_at: datetime


class MarkAllReadResponse(BaseModel):
    marked_count: int


class NotificationCreate(BaseModel):
    """Internal — used by service.notify() callers (not exposed via API)."""

    user_id: UUID
    type: NotificationType
    title: str = Field(..., max_length=200)
    body: str | None = None
    link_url: str | None = Field(None, max_length=500)
    priority: NotificationPriority = NotificationPriority.NORMAL
    meta: dict[str, Any] | None = None
