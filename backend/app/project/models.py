"""Project & Work domain — 5 tabel per ERD knowledge.md sec.20.

Tabel:
- projects             — Client/Internal/R&D types
- project_members      — assignee + allocation %
- project_milestones   — milestone tracking (akan diganti Phase di TSK-022B)
- project_tasks        — task per project (Kanban + Gantt)
- project_documents    — link ke dokumentasi teknis per project (US-TK-003)

CATATAN (TSK-022C, 2026-05-29):
Invoice termin di-pindah ke app/finance/ (lihat app.finance.models.Invoice).
Tabel `project_invoices` di-drop via migration a7c2f5e8b401. Phase completion
akan trigger `app.finance.service.trigger_invoices_on_phase_complete()`
setelah TSK-022B selesai.
"""

from __future__ import annotations

import enum
from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
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


class ProjectMember(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Member project dengan allocation %."""

    __tablename__ = "project_members"

    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    allocation_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class ProjectMilestone(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "project_milestones"

    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    progress_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)


class ProjectTask(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "project_tasks"

    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    milestone_id: Mapped[UUID | None] = mapped_column(ForeignKey("project_milestones.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee_id: Mapped[UUID | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="BACKLOG", nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class ProjectDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Dokumentasi teknis per project (US-TK-003)."""

    __tablename__ = "project_documents"

    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    folder_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)  # MinIO URL
    version: Mapped[str] = mapped_column(String(20), default="v1.0", nullable=False)
    uploaded_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


# ProjectInvoice — REMOVED (TSK-022C). Lihat app.finance.models.Invoice.
