"""Notification domain — TSK-057 (EP-06).

knowledge.md sec.10: in-app notification system.

Tabel:
- notifications — queue per user (in-app)

Fields:
- type (enum) — kategori (PAYROLL_APPROVED, LEAVE_APPROVED_L1, …)
- title — display heading
- body — preview text (1-2 sentence)
- link_url — frontend route untuk click action (nullable)
- read_at — set saat user mark read (nullable)
- meta — JSONB context (extra fields for templates)

Soft delete via deleted_at (TimestampMixin + SoftDeleteMixin) — never hard delete.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.identity.models import User


class NotificationType(str, enum.Enum):
    """Notification kategori. Add new types as modules need them.

    Naming: {DOMAIN}_{EVENT} — e.g. LEAVE_APPROVED_L1, CONTRACT_EXPIRING.
    Templates referenced by these keys in app/notification/templates.py.
    """

    # Approval flows
    APPROVAL_PENDING = "APPROVAL_PENDING"  # generic: you have something to approve
    APPROVAL_APPROVED = "APPROVAL_APPROVED"  # your request was approved
    APPROVAL_REJECTED = "APPROVAL_REJECTED"  # your request was rejected

    # Specific domains
    PAYROLL_PENDING_APPROVAL = "PAYROLL_PENDING_APPROVAL"
    PAYROLL_APPROVED = "PAYROLL_APPROVED"
    PAYROLL_PUBLISHED = "PAYROLL_PUBLISHED"

    LEAVE_PENDING_APPROVAL = "LEAVE_PENDING_APPROVAL"
    LEAVE_APPROVED = "LEAVE_APPROVED"
    LEAVE_REJECTED = "LEAVE_REJECTED"

    CONTRACT_EXPIRING = "CONTRACT_EXPIRING"  # H-30/14/7
    CONTRACT_RENEWED = "CONTRACT_RENEWED"

    TASK_DEADLINE = "TASK_DEADLINE"  # H-3 to due_date
    TASK_OVERDUE = "TASK_OVERDUE"

    SEPARATION_PENDING = "SEPARATION_PENDING"
    SEPARATION_EXECUTED = "SEPARATION_EXECUTED"

    PROCUREMENT_PENDING = "PROCUREMENT_PENDING"
    PROCUREMENT_APPROVED = "PROCUREMENT_APPROVED"

    INVOICE_TRIGGER = "INVOICE_TRIGGER"  # Phase complete → Finance please bill

    KPI_DEADLINE = "KPI_DEADLINE"  # client KPI not yet submitted, H-7

    SP_ISSUED = "SP_ISSUED"  # SP / SP-O notice to employee
    SP_O_ISSUED = "SP_O_ISSUED"

    CHANGE_REQUEST_PENDING = "CHANGE_REQUEST_PENDING"
    CHANGE_REQUEST_RESOLVED = "CHANGE_REQUEST_RESOLVED"

    # Catch-all
    SYSTEM = "SYSTEM"


class NotificationPriority(str, enum.Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """In-app notification queue, 1 row per user per event."""

    __tablename__ = "notifications"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[NotificationType] = mapped_column(
        String(50), nullable=False, index=True
    )
    priority: Mapped[NotificationPriority] = mapped_column(
        String(10), nullable=False, default=NotificationPriority.NORMAL
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Free-form context (e.g. {"request_id": "...", "amount": 5000000})
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # NULL = unread, datetime = when user marked read
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationship — User
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_notifications_user_unread", "user_id", "read_at"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Notification {self.type} → {self.user_id} read={self.read_at is not None}>"
