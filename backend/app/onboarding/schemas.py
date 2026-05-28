"""Pydantic schemas — onboarding TSK-016."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.onboarding.models import (
    AssignmentStatus,
    TaskAssignedRole,
    TaskCategory,
    TaskCompletionStatus,
)

Title = Annotated[str, StringConstraints(min_length=1, max_length=300, strip_whitespace=True)]


# ─── OnboardingTask (template item) ────────────────────────────────


class TaskBase(BaseModel):
    category: TaskCategory
    title: Title
    description: str | None = None
    instructions: str | None = None
    order_index: int = 0
    default_due_offset_days: Annotated[int, Field(ge=0, le=365)] = 7
    assigned_role: TaskAssignedRole = TaskAssignedRole.EMPLOYEE
    is_required: bool = True
    reference_url: str | None = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    category: TaskCategory | None = None
    title: str | None = None
    description: str | None = None
    instructions: str | None = None
    order_index: int | None = None
    default_due_offset_days: int | None = Field(default=None, ge=0, le=365)
    assigned_role: TaskAssignedRole | None = None
    is_required: bool | None = None
    reference_url: str | None = None


class TaskOut(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_id: UUID
    created_at: datetime


# ─── OnboardingTemplate ────────────────────────────────────────────


class TemplateBase(BaseModel):
    name: Title
    description: str | None = None
    target_department_id: UUID | None = None
    target_position_level: Annotated[int, Field(ge=1, le=6)] | None = None
    estimated_duration_days: Annotated[int, Field(ge=1, le=365)] = 30


class TemplateCreate(TemplateBase):
    """Create dengan optional initial tasks."""

    tasks: list[TaskCreate] = Field(default_factory=list)


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    target_department_id: UUID | None = None
    target_position_level: int | None = Field(default=None, ge=1, le=6)
    estimated_duration_days: int | None = Field(default=None, ge=1, le=365)
    is_active: bool | None = None


class TemplateOut(TemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    created_at: datetime

    # Derived
    department_name: str | None = None
    task_count: int = 0
    assignment_count: int = 0


class TemplateDetailOut(TemplateOut):
    """Detail dengan list tasks."""

    tasks: list[TaskOut] = Field(default_factory=list)


# ─── TaskCompletion ────────────────────────────────────────────────


class TaskCompletionUpdate(BaseModel):
    """Update status individual task completion."""

    status: TaskCompletionStatus
    notes: str | None = None
    blocker_reason: str | None = None  # wajib kalau status=BLOCKED


class TaskCompletionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assignment_id: UUID
    task_id: UUID
    status: TaskCompletionStatus
    due_date: date | None
    completed_at: datetime | None
    completed_by_user_id: UUID | None
    notes: str | None
    blocker_reason: str | None
    created_at: datetime
    updated_at: datetime

    # Joined task data untuk UI checklist
    task_title: str | None = None
    task_category: TaskCategory | None = None
    task_assigned_role: TaskAssignedRole | None = None
    task_is_required: bool | None = None
    task_instructions: str | None = None
    task_reference_url: str | None = None


# ─── OnboardingAssignment ──────────────────────────────────────────


class AssignmentCreate(BaseModel):
    """Assign template ke karyawan baru."""

    employee_id: UUID
    template_id: UUID
    started_at: date | None = None  # default = today
    target_completion_date: date | None = None
    notes: str | None = None


class AssignmentUpdate(BaseModel):
    notes: str | None = None
    target_completion_date: date | None = None
    status: AssignmentStatus | None = None


class AssignmentListItem(BaseModel):
    """Slim payload untuk list view."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    template_id: UUID
    status: AssignmentStatus
    started_at: date
    target_completion_date: date | None
    completed_at: datetime | None

    # Derived
    employee_nik: str | None = None
    employee_name: str | None = None
    employee_department: str | None = None
    template_name: str | None = None
    total_tasks: int = 0
    completed_tasks: int = 0
    progress_percent: int = 0


class AssignmentDetailOut(BaseModel):
    """Detail dengan tasks + completions."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    template_id: UUID
    status: AssignmentStatus
    started_at: date
    target_completion_date: date | None
    completed_at: datetime | None
    assigned_by_user_id: UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    employee_nik: str | None = None
    employee_name: str | None = None
    employee_department: str | None = None
    template_name: str | None = None

    total_tasks: int = 0
    completed_tasks: int = 0
    progress_percent: int = 0

    # Completions grouped by category
    completions_by_category: dict[str, list[TaskCompletionOut]] = Field(default_factory=dict)


class AssignmentListResponse(BaseModel):
    items: list[AssignmentListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
