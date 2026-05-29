"""Pydantic schemas — sales domain TSK-024."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.sales.models import LeadStage

Title = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]


# ─── Lead ──────────────────────────────────────────────────────────


class LeadCreate(BaseModel):
    company_name: Title
    pic_name: str | None = None
    pic_email: EmailStr | None = None
    pic_phone: Annotated[str, StringConstraints(max_length=30)] | None = None
    services: str | None = None
    estimated_value: Decimal | None = None
    currency: Annotated[str, StringConstraints(min_length=3, max_length=3)] = "IDR"
    source: str | None = None
    assigned_to_user_id: UUID | None = None
    referred_by_user_id: UUID | None = None
    is_direktur_driven: bool = False


class LeadUpdate(BaseModel):
    company_name: str | None = None
    pic_name: str | None = None
    pic_email: EmailStr | None = None
    pic_phone: str | None = None
    services: str | None = None
    estimated_value: Decimal | None = None
    source: str | None = None
    assigned_to_user_id: UUID | None = None
    is_direktur_driven: bool | None = None


class LeadStageTransition(BaseModel):
    """Pindahkan lead ke stage berikutnya. Untuk CLOSED_WON trigger commission."""

    new_stage: LeadStage
    commission_pct: Decimal | None = None  # wajib kalau CLOSED_WON dan bukan direktur-driven
    notes: str | None = None


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_name: str
    pic_name: str | None
    pic_email: str | None
    pic_phone: str | None
    services: str | None
    stage: LeadStage
    estimated_value: Decimal | None
    currency: str
    source: str | None
    assigned_to_user_id: UUID | None
    referred_by_user_id: UUID | None
    is_direktur_driven: bool
    closed_at: date | None
    created_at: datetime
    updated_at: datetime

    assigned_to_nik: str | None = None
    days_in_stage: int | None = None
    activity_count: int = 0
    proposal_count: int = 0


class LeadListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_name: str
    pic_name: str | None
    stage: LeadStage
    estimated_value: Decimal | None
    currency: str
    assigned_to_nik: str | None = None
    is_direktur_driven: bool
    days_in_stage: int | None = None
    created_at: datetime


# ─── LeadActivity ──────────────────────────────────────────────────


class ActivityCreate(BaseModel):
    activity_date: date
    activity_type: Annotated[str, StringConstraints(pattern="^(call|email|meeting|demo|followup|other)$")]
    notes: Annotated[str, StringConstraints(min_length=5, max_length=2000)]


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    activity_date: date
    activity_type: str
    notes: str | None
    logged_by_user_id: UUID | None
    created_at: datetime
    logged_by_nik: str | None = None


# ─── Proposal ──────────────────────────────────────────────────────


class ProposalItemSpec(BaseModel):
    description: Annotated[str, StringConstraints(min_length=5, max_length=1000)]
    quantity: Annotated[Decimal, Field(ge=0)] = Decimal("1")
    unit_price: Annotated[Decimal, Field(ge=0)]


class ProposalCreate(BaseModel):
    proposal_no: Annotated[str, StringConstraints(min_length=3, max_length=50)]
    version: Annotated[str, StringConstraints(min_length=2, max_length=20)] = "v1.0"
    pdf_url: str | None = None
    items: list[ProposalItemSpec] = Field(default_factory=list)


class ProposalItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    proposal_id: UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    subtotal: Decimal


class ProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    proposal_no: str
    version: str
    total_value: Decimal
    pdf_url: str | None
    status: str
    approved_by_user_id: UUID | None
    sent_at: datetime | None
    created_at: datetime

    items: list[ProposalItemOut] = Field(default_factory=list)


# ─── Commission ────────────────────────────────────────────────────


class CommissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    sales_user_id: UUID
    commission_pct: Decimal
    commission_amount: Decimal
    target_payroll_period_id: UUID | None
    status: str
    created_at: datetime

    sales_nik: str | None = None
    lead_company: str | None = None


# ─── Pipeline view ─────────────────────────────────────────────────


class PipelineStageBucket(BaseModel):
    stage: LeadStage
    label: str
    count: int
    total_value: Decimal
    leads: list[LeadListItem]


class PipelineResponse(BaseModel):
    stages: list[PipelineStageBucket]
    total_leads: int
    total_pipeline_value: Decimal
    closed_won_value_ytd: Decimal


# ─── SalesTarget ───────────────────────────────────────────────────


class TargetCreate(BaseModel):
    user_id: UUID | None = None
    department_id: UUID | None = None
    year: int
    month: int | None = None
    target_amount: Annotated[Decimal, Field(ge=0)]
    currency: str = "IDR"


class TargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    department_id: UUID | None
    year: int
    month: int | None
    target_amount: Decimal
    currency: str
    user_nik: str | None = None
    department_name: str | None = None
    achieved_amount: Decimal = Decimal("0")
    achievement_pct: Decimal = Decimal("0")
