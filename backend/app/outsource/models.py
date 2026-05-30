"""Outsource domain — 7 tabel per ERD knowledge.md sec.20.

Tabel:
- clients                       — master client perusahaan
- outsource_placements          — per orang per client
- timesheets                    — bulanan
- timesheet_items               — daily entries
- berita_acara                  — BA dengan digital signature (US-OP-007)
- client_complaints             — feed SP-O flow (US-OP-011)
- warning_letters_outsource     — SP-O1/SP-O2/SP-O3 (knowledge.md sec.5)

Schema detail full per EP-10 (M2.3) + US-OP-011.
"""

from __future__ import annotations

import enum
from datetime import date
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class BillingType(str, enum.Enum):
    """2 tipe billing per knowledge.md sec.14."""

    FLAT_MONTHLY = "FLAT"  # Nominal tetap per bulan
    PER_WORKDAY = "PER_WORKDAY"  # Rate × hari kerja aktual dari timesheet


class SpoLevel(str, enum.Enum):
    """SP-O sequence per knowledge.md sec.5."""

    SPO1 = "SP-O1"  # Warning + coaching
    SPO2 = "SP-O2"  # Final warning + 2-week eval
    SPO3 = "SP-O3"  # Replacement recommendation


class Client(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Master client perusahaan."""

    __tablename__ = "clients"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    pic_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pic_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pic_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class OutsourcePlacement(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Penempatan karyawan outsource di client."""

    __tablename__ = "outsource_placements"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    role_at_client: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    billing_type: Mapped[BillingType] = mapped_column(String(20), nullable=False)
    billing_rate: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)


class PlacementAmendment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Riwayat amendment placement (TSK-107).

    Snapshot of rate/end_date change. History audit log + attach
    document amendment (PDF kontrak amandemen).
    """

    __tablename__ = "placement_amendments"

    placement_id: Mapped[UUID] = mapped_column(
        ForeignKey("outsource_placements.id"), nullable=False, index=True,
    )
    amendment_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)

    old_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    old_billing_rate: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)

    new_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    new_billing_rate: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)

    document_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )


class Timesheet(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Timesheet bulanan."""

    __tablename__ = "timesheets"

    placement_id: Mapped[UUID] = mapped_column(ForeignKey("outsource_placements.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(nullable=False)
    month: Mapped[int] = mapped_column(nullable=False)
    workdays_count: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    submitted_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    approved_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class TimesheetItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Entry per hari di timesheet."""

    __tablename__ = "timesheet_items"

    timesheet_id: Mapped[UUID] = mapped_column(ForeignKey("timesheets.id"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_present: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class BeritaAcara(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """BA dengan digital signature (knowledge.md sec.14)."""

    __tablename__ = "berita_acara"

    timesheet_id: Mapped[UUID] = mapped_column(ForeignKey("timesheets.id"), nullable=False, index=True)
    ba_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    signed_by_ide: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    signed_by_client: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    client_signature_token: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    client_signed_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class ClientKpiAssessment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """KPI assessment dari client untuk outsource karyawan (TSK-108).

    Workflow:
    1. Operation generate token → kirim link ke client PIC.
    2. Client buka link (no login) → isi form rating 1-5 per kategori.
    3. Submit → save scores + invalidate token (used_at).
    """

    __tablename__ = "client_kpi_assessments"

    placement_id: Mapped[UUID] = mapped_column(
        ForeignKey("outsource_placements.id"), nullable=False, index=True,
    )
    assessment_period: Mapped[str] = mapped_column(String(20), nullable=False)
    # Format: 2026-05 (year-month)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    token_expires_at: Mapped[date] = mapped_column(Date, nullable=False)

    # Rating 1-5 (Pydantic validate)
    score_quality: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    score_communication: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    score_attendance: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    score_professionalism: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    score_initiative: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)

    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    sent_at: Mapped[date] = mapped_column(Date, nullable=False)
    submitted_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )


class ClientComplaint(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Client complaint → feed SP-O flow (US-OP-011)."""

    __tablename__ = "client_complaints"

    placement_id: Mapped[UUID] = mapped_column(ForeignKey("outsource_placements.id"), nullable=False, index=True)
    complaint_date: Mapped[date] = mapped_column(Date, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    logged_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class WarningLetterOutsource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """SP-O1/SP-O2/SP-O3 — TERPISAH dari WarningLetter internal (knowledge.md sec.5)."""

    __tablename__ = "warning_letters_outsource"

    placement_id: Mapped[UUID] = mapped_column(ForeignKey("outsource_placements.id"), nullable=False, index=True)
    level: Mapped[SpoLevel] = mapped_column(String(10), nullable=False)
    issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    triggered_by_complaint_id: Mapped[UUID | None] = mapped_column(ForeignKey("client_complaints.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evaluation_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # SP-O2 2-week eval
    triggers_replacement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # SP-O3
