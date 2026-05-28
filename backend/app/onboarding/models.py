"""Onboarding domain models — TSK-016.

Tabel:
- onboarding_templates       — blueprint checklist (mis. "Engineer Onboarding TECH L6")
- onboarding_tasks           — items dalam template, grouped by category
- onboarding_assignments     — instance template di-assign ke karyawan baru
- task_completions           — status per task per assignment
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
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


# ─── Enums ─────────────────────────────────────────────────────────


class TaskCategory(str, enum.Enum):
    """Grouping task untuk UI checklist."""

    HR_DOCUMENTS = "HR_DOCUMENTS"  # KTP, NPWP, BPJS forms
    IT_SETUP = "IT_SETUP"  # email, laptop, accounts
    TRAINING = "TRAINING"  # orientation, mandatory training
    DEPT_SPECIFIC = "DEPT_SPECIFIC"  # task khusus departemen
    BUDDY_INTRO = "BUDDY_INTRO"  # intro tim, buddy assignment
    COMPLIANCE = "COMPLIANCE"  # code of conduct, NDA
    OTHER = "OTHER"


class TaskAssignedRole(str, enum.Enum):
    """Siapa yang bertanggung jawab handle task."""

    HR = "HR"
    IT = "IT"
    MANAGER = "MANAGER"  # supervisor langsung
    BUDDY = "BUDDY"  # peer assigned
    EMPLOYEE = "EMPLOYEE"  # task untuk dilakukan sendiri
    FINANCE = "FINANCE"
    EXECUTIVE = "EXECUTIVE"


class AssignmentStatus(str, enum.Enum):
    """Lifecycle assignment."""

    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TaskCompletionStatus(str, enum.Enum):
    """Status per task instance."""

    PENDING = "PENDING"
    DONE = "DONE"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"  # waiting on external dependency


# ─── OnboardingTemplate ────────────────────────────────────────────


class OnboardingTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Blueprint checklist — bisa filter by dept atau hierarchy level."""

    __tablename__ = "onboarding_templates"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id"), nullable=True, index=True
    )
    # None = berlaku semua level, else specific level (1-6)
    target_position_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Estimated total days untuk complete onboarding
    estimated_duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    tasks: Mapped[list[OnboardingTask]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="OnboardingTask.order_index",
    )
    assignments: Mapped[list[OnboardingAssignment]] = relationship(back_populates="template")

    __table_args__ = (
        Index("ix_templates_dept_level_active", "target_department_id", "target_position_level", "is_active"),
    )


# ─── OnboardingTask (template items) ───────────────────────────────


class OnboardingTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Item dalam template — define apa yang harus di-check off."""

    __tablename__ = "onboarding_tasks"

    template_id: Mapped[UUID] = mapped_column(
        ForeignKey("onboarding_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[TaskCategory] = mapped_column(String(30), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)  # detailed step-by-step

    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Offset hari dari joined_date untuk default due date
    default_due_offset_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    # Siapa yang bertanggung jawab
    assigned_role: Mapped[TaskAssignedRole] = mapped_column(
        String(30), nullable=False, default=TaskAssignedRole.EMPLOYEE
    )
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Link ke dokumen/template (optional)
    reference_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    template: Mapped[OnboardingTemplate] = relationship(back_populates="tasks")

    __table_args__ = (
        Index("ix_tasks_template_order", "template_id", "order_index"),
    )


# ─── OnboardingAssignment (instance per employee) ──────────────────


class OnboardingAssignment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Template di-assign ke 1 karyawan saat hire."""

    __tablename__ = "onboarding_assignments"

    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[UUID] = mapped_column(
        ForeignKey("onboarding_templates.id"), nullable=False
    )

    status: Mapped[AssignmentStatus] = mapped_column(
        String(20), nullable=False, default=AssignmentStatus.NOT_STARTED, index=True
    )
    started_at: Mapped[date] = mapped_column(Date, nullable=False)
    target_completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Audit
    assigned_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    template: Mapped[OnboardingTemplate] = relationship(back_populates="assignments")
    completions: Mapped[list[TaskCompletion]] = relationship(
        back_populates="assignment",
        cascade="all, delete-orphan",
        order_by="TaskCompletion.created_at",
    )

    __table_args__ = (
        UniqueConstraint("employee_id", "template_id", name="uq_assignment_employee_template"),
        Index("ix_assignments_status", "status"),
    )


# ─── TaskCompletion (per assignment task status) ───────────────────


class TaskCompletion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Status setiap task untuk 1 assignment."""

    __tablename__ = "task_completions"

    assignment_id: Mapped[UUID] = mapped_column(
        ForeignKey("onboarding_assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("onboarding_tasks.id"), nullable=False
    )

    status: Mapped[TaskCompletionStatus] = mapped_column(
        String(20), nullable=False, default=TaskCompletionStatus.PENDING, index=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocker_reason: Mapped[str | None] = mapped_column(Text, nullable=True)  # diisi kalau BLOCKED

    # Relationships
    assignment: Mapped[OnboardingAssignment] = relationship(back_populates="completions")
    task: Mapped[OnboardingTask] = relationship()

    __table_args__ = (
        UniqueConstraint("assignment_id", "task_id", name="uq_completion_assignment_task"),
    )
