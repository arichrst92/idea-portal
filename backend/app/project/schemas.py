"""Pydantic schemas — project domain TSK-022."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.project.models import ProjectStatus, ProjectType

Title = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]
Code = Annotated[str, StringConstraints(min_length=2, max_length=50, strip_whitespace=True)]


# ─── Project ───────────────────────────────────────────────────────


class ProjectBase(BaseModel):
    code: Code
    name: Title
    type: ProjectType
    description: str | None = None
    pm_user_id: UUID | None = None
    client_id: UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    contract_value: Decimal | None = None
    currency: Annotated[str, StringConstraints(min_length=3, max_length=3)] = "IDR"


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    pm_user_id: UUID | None = None
    client_id: UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    contract_value: Decimal | None = None
    currency: str | None = None


class ProjectClose(BaseModel):
    """Close project. Direktur Utama can override at any status."""

    new_status: ProjectStatus  # COMPLETED atau TERMINATED
    reason: Annotated[str, StringConstraints(min_length=10, max_length=2000)]


class ProjectOut(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime

    pm_nik: str | None = None
    pm_name: str | None = None
    client_name: str | None = None
    member_count: int = 0
    milestone_count: int = 0
    completed_milestones: int = 0
    overall_progress_pct: Decimal | None = None


class ProjectListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    type: ProjectType
    status: ProjectStatus
    pm_nik: str | None = None
    client_name: str | None = None
    start_date: date | None
    end_date: date | None
    contract_value: Decimal | None
    currency: str
    member_count: int = 0
    overall_progress_pct: Decimal | None = None


class ProjectListResponse(BaseModel):
    items: list[ProjectListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ─── Members ───────────────────────────────────────────────────────


class MemberAdd(BaseModel):
    employee_id: UUID
    role: Annotated[str, StringConstraints(max_length=50)] | None = None
    allocation_pct: Annotated[Decimal, Field(ge=0, le=100)]
    start_date: date
    end_date: date | None = None


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    employee_id: UUID
    role: str | None
    allocation_pct: Decimal
    start_date: date
    end_date: date | None
    employee_nik: str | None = None
    employee_name: str | None = None


# ─── Milestones ────────────────────────────────────────────────────


class MilestoneCreate(BaseModel):
    name: Title
    target_date: date


class MilestoneUpdate(BaseModel):
    name: str | None = None
    target_date: date | None = None
    progress_pct: Annotated[Decimal, Field(ge=0, le=100)] | None = None
    completed_at: date | None = None


class MilestoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    target_date: date
    completed_at: date | None
    progress_pct: Decimal
    is_overdue: bool = False  # derived: target_date < today AND completed_at is None


# ─── Tasks (Kanban) ────────────────────────────────────────────────


class TaskStatus:
    """Status values untuk task kanban."""

    BACKLOG = "BACKLOG"
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    DONE = "DONE"
    BLOCKED = "BLOCKED"


class TaskPriority:
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskCreate(BaseModel):
    title: Title
    description: str | None = None
    milestone_id: UUID | None = None
    assignee_id: UUID | None = None
    status: Annotated[str, StringConstraints(pattern="^(BACKLOG|TODO|IN_PROGRESS|IN_REVIEW|DONE|BLOCKED)$")] = "BACKLOG"
    priority: Annotated[str, StringConstraints(pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")] = "MEDIUM"
    due_date: date | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    milestone_id: UUID | None = None
    assignee_id: UUID | None = None
    status: str | None = None
    priority: str | None = None
    due_date: date | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    milestone_id: UUID | None
    title: str
    description: str | None
    assignee_id: UUID | None
    status: str
    priority: str
    due_date: date | None
    created_at: datetime

    assignee_nik: str | None = None
    assignee_name: str | None = None
    milestone_name: str | None = None


# ─── Invoices ──────────────────────────────────────────────────────


class InvoiceCreate(BaseModel):
    invoice_no: Annotated[str, StringConstraints(min_length=3, max_length=50)]
    termin_pct: Annotated[Decimal, Field(ge=0, le=100)]
    amount: Annotated[Decimal, Field(ge=0)]
    trigger_milestone_id: UUID | None = None


class InvoiceUpdate(BaseModel):
    status: str | None = None  # PENDING/SENT/PARTIAL/PAID
    paid_amount: Decimal | None = None
    paid_at: date | None = None


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    invoice_no: str
    termin_pct: Decimal
    amount: Decimal
    trigger_milestone_id: UUID | None
    trigger_date: date | None
    status: str
    notified_finance_at: date | None
    paid_amount: Decimal
    paid_at: date | None
    created_at: datetime

    milestone_name: str | None = None
