"""Project & Work domain — TSK-022B refactor.

Hierarki pekerjaan (4-level):

    Project
      └─ Phase           (replace Milestone)
           └─ Epic
                └─ Task           (slug WEB-123, assignee, story_points)
                     └─ Subtask   (slug WEB-123.1, assignee, story_points)

Tabel:
- projects             — Client/Internal/R&D types
- project_members      — assignee + allocation %
- project_phases       — replaces project_milestones (TSK-022B)
- project_epics        — grouping di dalam phase (TSK-022B)
- project_tasks        — unit kerja kanban (slug + story_points + comments)
- project_subtasks     — breakdown task (TSK-022B)
- project_task_comments     — markdown comments per task (TSK-022B)
- project_subtask_comments  — markdown comments per subtask (TSK-022B)
- project_documents    — link ke dokumentasi teknis per project (US-TK-003)

CATATAN:
- ProjectMilestone DROP — diganti ProjectPhase.
- ProjectInvoice DROP (TSK-022C) — pindah ke app.finance.models.Invoice.
- Phase completion akan trigger app.finance.service.trigger_invoices_on_phase_complete().
"""

from __future__ import annotations

import enum
from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ProjectType(str, enum.Enum):
    """3 tipe project per knowledge.md sec.13."""

    CLIENT = "CLIENT"  # Revenue
    INTERNAL = "INTERNAL"  # Cost OPEX/CAPEX
    R_AND_D = "RND"  # Sub-internal, kategori terpisah


class ProjectStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Master project record."""

    __tablename__ = "projects"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[ProjectType] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[ProjectStatus] = mapped_column(String(20), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    pm_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    client_id: Mapped[UUID | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_value: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="IDR", nullable=False)

    # Counter untuk slug Task (atomic increment via SELECT FOR UPDATE)
    task_slug_counter: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ProjectMember(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Member project dengan allocation %."""

    __tablename__ = "project_members"

    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    allocation_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class PhaseStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ProjectPhase(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Phase per project — replace milestone.

    Phase completion akan trigger Finance untuk invoice termin
    (lihat app.finance.service.trigger_invoices_on_phase_complete).
    """

    __tablename__ = "project_phases"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[PhaseStatus] = mapped_column(
        String(20), default=PhaseStatus.PLANNED, nullable=False
    )
    progress_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)


class ProjectEpic(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Epic = grouping of related tasks dalam phase."""

    __tablename__ = "project_epics"

    phase_id: Mapped[UUID] = mapped_column(
        ForeignKey("project_phases.id"), nullable=False, index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PLANNED", nullable=False)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)  # CSS color hint


class ProjectTask(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Task per project — slug Jira-style + story_points + assignee + comments."""

    __tablename__ = "project_tasks"

    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    epic_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("project_epics.id"), nullable=True, index=True
    )
    slug: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # e.g. WEB-123
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee_id: Mapped[UUID | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="BACKLOG", nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False)
    story_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class ProjectSubtask(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Subtask = breakdown task. Slug = {task_slug}.{counter} (e.g. WEB-123.1)."""

    __tablename__ = "project_subtasks"

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("project_tasks.id"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee_id: Mapped[UUID | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="BACKLOG", nullable=False)
    story_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ProjectTaskComment(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Markdown comment thread per task."""

    __tablename__ = "project_task_comments"

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("project_tasks.id"), nullable=False, index=True
    )
    author_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)  # markdown raw text


class ProjectSubtaskComment(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Markdown comment thread per subtask."""

    __tablename__ = "project_subtask_comments"

    subtask_id: Mapped[UUID] = mapped_column(
        ForeignKey("project_subtasks.id"), nullable=False, index=True
    )
    author_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)


class CRStatus(str, enum.Enum):
    """Change Request status flow (TSK-070)."""

    DRAFT = "DRAFT"
    PENDING_L1 = "PENDING_L1"  # Atasan langsung / PM
    PENDING_L2 = "PENDING_L2"  # GM/C-Level
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class CRImpact(str, enum.Enum):
    """Impact category for change request."""

    SCOPE = "SCOPE"
    TIMELINE = "TIMELINE"
    COST = "COST"
    MIXED = "MIXED"


class ProjectChangeRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Change Request per project — 2-layer approval; trigger Finance & Sales.

    Workflow:
      DRAFT → submit → PENDING_L1 → approve → PENDING_L2 → approve → APPROVED
                                          → reject → REJECTED
    Setelah APPROVED:
      - Kalau cost_delta != 0 → notify Finance (untuk addendum invoice)
      - Kalau scope ke client project → notify Sales (untuk update lead/proposal)
    """

    __tablename__ = "project_change_requests"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    cr_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    impact_category: Mapped[CRImpact] = mapped_column(
        String(20), default=CRImpact.MIXED, nullable=False
    )
    scope_delta: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeline_delta_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_delta: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="IDR", nullable=False)

    requester_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    status: Mapped[CRStatus] = mapped_column(
        String(20), default=CRStatus.DRAFT, nullable=False, index=True
    )

    layer1_approver_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    layer1_approved_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    layer1_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    layer2_approver_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    layer2_approved_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    layer2_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    rejected_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    sales_notified_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    finance_notified_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class ProjectDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Dokumentasi teknis per project (US-TK-003)."""

    __tablename__ = "project_documents"

    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    folder_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)  # MinIO URL
    version: Mapped[str] = mapped_column(String(20), default="v1.0", nullable=False)
    uploaded_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


# ─── Backward-compat alias ────────────────────────────────────────────
# Kode lain (mis. service.py) masih reference ProjectMilestone selama transisi.
# Akan dihapus setelah service.py & router.py di-refactor penuh ke Phase.
ProjectMilestone = ProjectPhase
