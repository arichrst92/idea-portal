"""Separation models — TSK-017.

Tabel:
- employee_separations: 1 record per separation request, with full audit trail
  (initiator + L1 approver + L2 approver + executor + rejector).
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SeparationType(str, enum.Enum):
    RESIGNATION = "RESIGNATION"  # employee self-initiated
    LAYOFF = "LAYOFF"  # company efisiensi/restrukturisasi
    TERMINATION = "TERMINATION"  # disciplinary (SP3 trigger)
    END_OF_CONTRACT = "END_OF_CONTRACT"  # PKWT habis
    RETIREMENT = "RETIREMENT"


class SeparationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL_L1 = "PENDING_APPROVAL_L1"
    PENDING_APPROVAL_L2 = "PENDING_APPROVAL_L2"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"  # employee.status sudah di-update
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class EmployeeSeparation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Catatan separation untuk audit trail lengkap.

    Tidak pakai SoftDeleteMixin karena record ini SENDIRI adalah audit log.
    Status final EXECUTED tidak pernah dihapus, hanya bisa di-CANCEL sebelum
    execute.
    """

    __tablename__ = "employee_separations"

    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("employees.id"), nullable=False, index=True
    )
    separation_type: Mapped[SeparationType] = mapped_column(
        String(30), nullable=False, index=True
    )
    status: Mapped[SeparationStatus] = mapped_column(
        String(40), nullable=False, default=SeparationStatus.DRAFT, index=True
    )

    # Reason + context
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    notice_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    # Compensation (severance untuk layoff, no severance untuk resignation/termination biasanya)
    severance_amount: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="IDR")

    # Asset return checklist (JSONB: [{"item": "Laptop MacBook Pro", "returned": false}, ...])
    assets_to_return: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Link ke SP3 kalau TERMINATION (warning_letters table di assessment domain)
    related_warning_letter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("warning_letters.id"), nullable=True
    )

    # Exit interview
    exit_interview_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_interview_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ─── Audit trail (siapa initiate, approve, reject, execute) ────
    initiated_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    approval_l1_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approval_l1_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_l1_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    approval_l2_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approval_l2_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_l2_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    rejected_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    executed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_separation_status_type", "status", "separation_type"),
        Index("ix_separation_employee_status", "employee_id", "status"),
    )
