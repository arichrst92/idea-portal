"""Finance domain models — TSK-022C.

Tabel utama (current):
- invoices  — AR / billing termin, optionally linked to project & trigger phase

Future tables (EP-09 — M2.2):
- chart_of_accounts        — CoA tree
- transactions             — accrual basis, multi-currency
- journal_entries          — debit/credit entries
- currencies               — exchange rates
- tax_reports              — PPh21, PPN 11% (IDEA PKP)

Catatan: Reimbursement, Procurement, Payroll tetap di app/payroll/ karena
secara use-case lebih HR/operational; Finance domain ini fokus billing/AR.
"""

from __future__ import annotations

import enum
from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class InvoiceStatus(str, enum.Enum):
    """AR status flow per knowledge.md sec.13 + mockup IDEA_InvoiceAR.html."""

    PENDING = "PENDING"  # Belum di-issue (default)
    SENT = "SENT"  # Sudah dikirim ke client, menunggu pembayaran
    PARTIAL = "PARTIAL"  # Sebagian sudah dibayar
    PAID = "PAID"  # Lunas
    OVERDUE = "OVERDUE"  # Lewat due date, belum lunas
    CANCELLED = "CANCELLED"


class Invoice(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Invoice / AR record — dipakai untuk billing termin project (CLIENT type)
    maupun invoice ad-hoc dari Finance."""

    __tablename__ = "invoices"

    invoice_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    # Optional link ke project (nullable supaya invoice ad-hoc juga bisa)
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    # Trigger source: phase completion (nullable, kalau project_id juga set)
    trigger_phase_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("project_phases.id", use_alter=True), nullable=True
    )

    # Recipient — client (nullable kalau internal/ad-hoc)
    client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clients.id"), nullable=True, index=True
    )
    client_name_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Termin metadata (project-related)
    termin_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Amount
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="IDR", nullable=False)
    tax_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=11.0, nullable=False)  # PPN 11%
    tax_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)  # amount + tax_amount

    # Dates
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notified_finance_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Status & payment tracking
    status: Mapped[InvoiceStatus] = mapped_column(
        String(20), default=InvoiceStatus.PENDING, nullable=False, index=True
    )
    paid_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    paid_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
