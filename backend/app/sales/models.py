"""Sales domain — 7 tabel per ERD knowledge.md sec.20.

Tabel:
- leads                  — funnel 6-stage
- lead_activities        — log per lead (call/email/meeting)
- proposals              — template per services, versioning
- proposal_items         — line items
- sales_targets          — individu + tim
- sales_action_items     — AI-generated per lead per stage (US-SM-005)
- sales_commissions      — link ke payroll variable (US-EX-005 trigger)

Schema detail full per EP-14/15/16 (M3.1).
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class LeadStage(str, enum.Enum):
    """Funnel 6-stage per knowledge.md sec.7."""

    PROSPECT = "PROSPECT"
    QUALIFIED = "QUALIFIED"
    PROPOSAL = "PROPOSAL"
    NEGOTIATION = "NEGOTIATION"
    CLOSED_WON = "CLOSED_WON"
    CLOSED_LOST = "CLOSED_LOST"


class Lead(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Lead funnel."""

    __tablename__ = "leads"

    company_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    pic_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pic_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pic_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    services: Mapped[str | None] = mapped_column(String(200), nullable=True)
    stage: Mapped[LeadStage] = mapped_column(String(30), nullable=False, index=True)
    estimated_value: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="IDR", nullable=False)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    assigned_to_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    referred_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_direktur_driven: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # ↑ Direktur-driven = no commission (knowledge.md sec.7)
    closed_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class LeadActivity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Log activity per lead."""

    __tablename__ = "lead_activities"

    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    activity_date: Mapped[date] = mapped_column(Date, nullable=False)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # call/email/meeting
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    logged_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class Proposal(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Proposal dengan versioning + approval (knowledge.md sec.7)."""

    __tablename__ = "proposals"

    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    proposal_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="v1.0", nullable=False)
    total_value: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProposalItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Line items dalam proposal."""

    __tablename__ = "proposal_items"

    proposal_id: Mapped[UUID] = mapped_column(ForeignKey("proposals.id"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)


class SalesTarget(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Target sales individu + tim."""

    __tablename__ = "sales_targets"

    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    year: Mapped[int] = mapped_column(nullable=False, index=True)
    month: Mapped[int | None] = mapped_column(nullable=True)
    target_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="IDR", nullable=False)


class SalesActionItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """AI-generated action item per lead (US-SM-005)."""

    __tablename__ = "sales_action_items"

    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    # PENDING/ACCEPTED/IGNORED/COMPLETED
    suggested_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class SalesCommission(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Komisi sales auto-flow ke payroll variable (knowledge.md sec.7 + US-EX-005).

    Trigger: lead.stage = CLOSED_WON dan is_direktur_driven = False.
    Direktur-driven deal → NO commission (per aturan).
    """

    __tablename__ = "sales_commissions"

    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    sales_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    commission_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    commission_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    target_payroll_period_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("payroll_periods.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    # PENDING → PAID (saat masuk slip gaji)
