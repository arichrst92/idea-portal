"""Pydantic schemas — hiring domain TSK-015."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.hiring.models import (
    ApplicationSource,
    ApplicationStage,
    InterviewResult,
    InterviewType,
    JobOpeningStatus,
)

Title = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]


# ─── JobOpening ────────────────────────────────────────────────────


class JobOpeningBase(BaseModel):
    title: Title
    description: str | None = None
    requirements: str | None = None
    department_id: UUID
    position_id: UUID | None = None
    slots_needed: Annotated[int, Field(ge=1, le=999)] = 1
    min_salary: Decimal | None = None
    max_salary: Decimal | None = None
    currency: Annotated[str, StringConstraints(min_length=3, max_length=3)] = "IDR"
    deadline: date | None = None
    is_public: bool = False


class JobOpeningCreate(JobOpeningBase):
    pass


class JobOpeningUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    requirements: str | None = None
    position_id: UUID | None = None
    slots_needed: int | None = Field(default=None, ge=1, le=999)
    min_salary: Decimal | None = None
    max_salary: Decimal | None = None
    deadline: date | None = None
    is_public: bool | None = None


class JobOpeningApproveRequest(BaseModel):
    """Approve/reject job opening — Executive only."""

    approve: bool
    rejection_reason: str | None = None


class JobOpeningOut(JobOpeningBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: JobOpeningStatus
    slots_filled: int
    posted_date: date | None
    closed_date: date | None
    requested_by_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime

    # Derived
    department_name: str | None = None
    position_name: str | None = None
    requested_by_nik: str | None = None
    application_count: int = 0


class JobOpeningListItem(BaseModel):
    """Slim version untuk list view."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    department_name: str | None
    position_name: str | None
    status: JobOpeningStatus
    slots_needed: int
    slots_filled: int
    deadline: date | None
    application_count: int
    created_at: datetime


class JobOpeningListResponse(BaseModel):
    items: list[JobOpeningListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ─── JobApplication ────────────────────────────────────────────────


class JobApplicationBase(BaseModel):
    candidate_name: Title
    candidate_email: EmailStr
    candidate_phone: Annotated[str, StringConstraints(max_length=20)] | None = None
    resume_url: str | None = None
    cover_letter: str | None = None
    linkedin_url: str | None = None
    source: ApplicationSource = ApplicationSource.OTHER
    referrer_user_id: UUID | None = None


class JobApplicationCreate(JobApplicationBase):
    job_opening_id: UUID


class JobApplicationUpdate(BaseModel):
    candidate_phone: str | None = None
    resume_url: str | None = None
    cover_letter: str | None = None
    linkedin_url: str | None = None
    notes: str | None = None
    offered_salary: Decimal | None = None
    offered_start_date: date | None = None


class StageTransitionRequest(BaseModel):
    """Pindahkan kandidat ke stage berikutnya / reject / withdraw."""

    new_stage: ApplicationStage
    notes: str | None = None
    rejection_reason: str | None = None  # wajib kalau new_stage=REJECTED


class JobApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_opening_id: UUID
    candidate_name: str
    candidate_email: str
    candidate_phone: str | None
    resume_url: str | None
    cover_letter: str | None
    linkedin_url: str | None
    source: ApplicationSource
    referrer_user_id: UUID | None
    stage: ApplicationStage
    stage_changed_at: datetime | None
    rejection_reason: str | None
    rejection_stage: ApplicationStage | None
    notes: str | None
    offered_salary: Decimal | None
    offered_start_date: date | None
    created_at: datetime
    updated_at: datetime

    # Derived
    job_title: str | None = None
    days_in_stage: int | None = None


class PipelineStageBucket(BaseModel):
    """1 kolom kanban: stage + list applications."""

    stage: ApplicationStage
    label: str
    count: int
    applications: list[JobApplicationOut]


class PipelineResponse(BaseModel):
    """Kanban board response: dikelompokkan per stage."""

    job_opening_id: UUID
    job_title: str
    total_applications: int
    stages: list[PipelineStageBucket]


# ─── Interview ─────────────────────────────────────────────────────


class InterviewCreate(BaseModel):
    application_id: UUID
    interview_type: InterviewType
    scheduled_at: datetime
    duration_minutes: Annotated[int, Field(ge=15, le=480)] = 60
    location_or_link: str | None = None
    interviewer_user_ids: list[UUID] = Field(default_factory=list)


class InterviewUpdate(BaseModel):
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=15, le=480)
    location_or_link: str | None = None
    interviewer_user_ids: list[UUID] | None = None
    result: InterviewResult | None = None
    feedback: str | None = None
    score: Decimal | None = None


class InterviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    application_id: UUID
    interview_type: InterviewType
    scheduled_at: datetime
    duration_minutes: int
    location_or_link: str | None
    interviewer_user_ids: list[str] | None
    result: InterviewResult
    feedback: str | None
    score: Decimal | None
    created_at: datetime
