"""Hiring domain models — TSK-015.

Tabel:
- job_openings        — lowongan dari Manager → approved by GM/C-Level
- job_applications    — pendaftar / kandidat dengan stage pipeline
- interviews          — schedule + feedback per stage interview
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING
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

from app.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


# ─── Enums ─────────────────────────────────────────────────────────


class JobOpeningStatus(str, enum.Enum):
    """Lifecycle lowongan."""

    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    OPEN = "OPEN"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"


class ApplicationStage(str, enum.Enum):
    """Stage pipeline candidate (per mockup IDEA_HiringModule.html)."""

    APPLIED = "APPLIED"
    SCREENING = "SCREENING"
    HR_INTERVIEW = "HR_INTERVIEW"
    USER_INTERVIEW = "USER_INTERVIEW"
    TECHNICAL_TEST = "TECHNICAL_TEST"
    OFFERING = "OFFERING"
    HIRED = "HIRED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class ApplicationSource(str, enum.Enum):
    """Sumber kandidat untuk analytics."""

    REFERRAL = "REFERRAL"
    LINKEDIN = "LINKEDIN"
    JOBSTREET = "JOBSTREET"
    INDEED = "INDEED"
    KARIR_COM = "KARIR_COM"
    COMPANY_WEBSITE = "COMPANY_WEBSITE"
    AGENCY = "AGENCY"
    WALK_IN = "WALK_IN"
    OTHER = "OTHER"


class InterviewType(str, enum.Enum):
    """Jenis interview di pipeline."""

    HR_SCREENING = "HR_SCREENING"
    USER_TECHNICAL = "USER_TECHNICAL"
    BEHAVIORAL = "BEHAVIORAL"
    FINAL = "FINAL"


class InterviewResult(str, enum.Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    NO_SHOW = "NO_SHOW"


# ─── JobOpening ────────────────────────────────────────────────────


class JobOpening(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Lowongan kerja — di-request Manager+, approved by GM/C-Level.

    Per US-OP-014: hiring approval flow 2-layer (atasan langsung → GM).
    """

    __tablename__ = "job_openings"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)

    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("departments.id"), nullable=False, index=True
    )
    position_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("positions.id"), nullable=True
    )

    status: Mapped[JobOpeningStatus] = mapped_column(
        String(30), nullable=False, default=JobOpeningStatus.DRAFT, index=True
    )
    slots_needed: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    slots_filled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Compensation transparency
    min_salary: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    max_salary: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="IDR")

    # Posting timeline
    posted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Approval audit (2-layer per knowledge.md)
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Public posting flag (tampil di public career page nanti)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    applications: Mapped[list[JobApplication]] = relationship(
        back_populates="job_opening", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_job_openings_status_dept", "status", "department_id"),
    )


# ─── JobApplication ────────────────────────────────────────────────


class JobApplication(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Pendaftar kandidat untuk JobOpening."""

    __tablename__ = "job_applications"

    job_opening_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_openings.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Candidate info (denormalized — kalau internal employee bisa link via referrer_user_id)
    candidate_name: Mapped[str] = mapped_column(String(200), nullable=False)
    candidate_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    candidate_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resume_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Source tracking
    source: Mapped[ApplicationSource] = mapped_column(
        String(30), nullable=False, default=ApplicationSource.OTHER
    )
    referrer_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Pipeline stage
    stage: Mapped[ApplicationStage] = mapped_column(
        String(30), nullable=False, default=ApplicationStage.APPLIED, index=True
    )
    stage_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Decision context
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_stage: Mapped[ApplicationStage | None] = mapped_column(String(30), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Offer details (filled saat stage OFFERING/HIRED)
    offered_salary: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    offered_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Relationships
    job_opening: Mapped[JobOpening] = relationship(back_populates="applications")
    interviews: Mapped[list[Interview]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_applications_opening_stage", "job_opening_id", "stage"),
    )


# ─── Interview ─────────────────────────────────────────────────────


class Interview(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Schedule + result per stage interview."""

    __tablename__ = "interviews"

    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    interview_type: Mapped[InterviewType] = mapped_column(String(30), nullable=False)

    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    location_or_link: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Interviewers (array of user IDs untuk multi-interviewer)
    interviewer_user_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    # Result + feedback
    result: Mapped[InterviewResult] = mapped_column(
        String(20), nullable=False, default=InterviewResult.PENDING
    )
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Relationships
    application: Mapped[JobApplication] = relationship(back_populates="interviews")
