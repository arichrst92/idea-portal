"""Pydantic schemas — project domain (TSK-022, TSK-022C, TSK-022B).

Hierarki: Project > Phase > Epic > Task > Subtask
+ TaskComment & SubtaskComment (markdown).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.project.models import PhaseStatus, ProjectStatus, ProjectType


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
    phase_count: int = 0
    completed_phases: int = 0
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


# ─── Phase (replaces Milestone) ────────────────────────────────────


class PhaseCreate(BaseModel):
    name: Title
    description: str | None = None
    target_date: date | None = None
    order_index: int = 0


class PhaseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    target_date: date | None = None
    order_index: int | None = None
    status: PhaseStatus | None = None
    progress_pct: Annotated[Decimal, Field(ge=0, le=100)] | None = None
    completed_at: date | None = None


class PhaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    description: str | None
    order_index: int
    target_date: date | None
    completed_at: date | None
    status: PhaseStatus
    progress_pct: Decimal
    is_overdue: bool = False
    epic_count: int = 0


# Backward-compat alias (kode lama masih reference MilestoneCreate/Out/Update)
MilestoneCreate = PhaseCreate
MilestoneUpdate = PhaseUpdate
MilestoneOut = PhaseOut


# ─── Epic ──────────────────────────────────────────────────────────


class EpicCreate(BaseModel):
    name: Title
    description: str | None = None
    color: str | None = None
    order_index: int = 0


class EpicUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    order_index: int | None = None
    status: str | None = None


class EpicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phase_id: UUID
    project_id: UUID
    name: str
    description: str | None
    order_index: int
    status: str
    color: str | None
    task_count: int = 0
    completed_task_count: int = 0


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


_TASK_STATUS_PATTERN = "^(BACKLOG|TODO|IN_PROGRESS|IN_REVIEW|DONE|BLOCKED)$"
_TASK_PRIORITY_PATTERN = "^(LOW|MEDIUM|HIGH|CRITICAL)$"


class TaskCreate(BaseModel):
    title: Title
    description: str | None = None
    epic_id: UUID | None = None
    assignee_id: UUID | None = None
    status: Annotated[str, StringConstraints(pattern=_TASK_STATUS_PATTERN)] = "BACKLOG"
    priority: Annotated[str, StringConstraints(pattern=_TASK_PRIORITY_PATTERN)] = "MEDIUM"
    story_points: int | None = Field(None, ge=0, le=99)
    due_date: date | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    epic_id: UUID | None = None
    assignee_id: UUID | None = None
    status: str | None = None
    priority: str | None = None
    story_points: int | None = None
    due_date: date | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    epic_id: UUID | None
    slug: str
    title: str
    description: str | None
    assignee_id: UUID | None
    status: str
    priority: str
    story_points: int | None
    due_date: date | None
    created_at: datetime
    updated_at: datetime

    assignee_nik: str | None = None
    assignee_name: str | None = None
    epic_name: str | None = None
    phase_name: str | None = None
    subtask_count: int = 0
    completed_subtask_count: int = 0
    comment_count: int = 0


# ─── Subtasks ──────────────────────────────────────────────────────


class SubtaskCreate(BaseModel):
    title: Title
    description: str | None = None
    assignee_id: UUID | None = None
    status: Annotated[str, StringConstraints(pattern=_TASK_STATUS_PATTERN)] = "BACKLOG"
    story_points: int | None = Field(None, ge=0, le=99)
    due_date: date | None = None
    order_index: int = 0


class SubtaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assignee_id: UUID | None = None
    status: str | None = None
    story_points: int | None = None
    due_date: date | None = None
    order_index: int | None = None


class SubtaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    slug: str
    title: str
    description: str | None
    assignee_id: UUID | None
    status: str
    story_points: int | None
    due_date: date | None
    order_index: int
    created_at: datetime
    updated_at: datetime

    assignee_nik: str | None = None
    assignee_name: str | None = None
    comment_count: int = 0


# ─── Comments (markdown) ───────────────────────────────────────────


class CommentCreate(BaseModel):
    body: Annotated[str, StringConstraints(min_length=1, max_length=5000, strip_whitespace=True)]


class CommentUpdate(BaseModel):
    body: Annotated[str, StringConstraints(min_length=1, max_length=5000, strip_whitespace=True)]


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_user_id: UUID
    body: str
    created_at: datetime
    updated_at: datetime

    author_nik: str | None = None
    author_name: str | None = None
