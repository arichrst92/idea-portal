"""Change Request schemas — TSK-070."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.project.models import CRImpact, CRStatus


Title = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]


class CRCreate(BaseModel):
    title: Title
    description: str | None = None
    impact_category: CRImpact = CRImpact.MIXED
    scope_delta: str | None = None
    timeline_delta_days: int = 0
    cost_delta: Annotated[Decimal, Field(ge=-9_999_999_999, le=9_999_999_999)] = Decimal("0")
    currency: Annotated[str, StringConstraints(min_length=3, max_length=3)] = "IDR"


class CRUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    impact_category: CRImpact | None = None
    scope_delta: str | None = None
    timeline_delta_days: int | None = None
    cost_delta: Decimal | None = None


class CRApprove(BaseModel):
    notes: str | None = None


class CRReject(BaseModel):
    rejection_reason: Annotated[str, StringConstraints(min_length=5, max_length=1000)]


class CROut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    cr_number: str
    title: str
    description: str | None
    impact_category: CRImpact
    scope_delta: str | None
    timeline_delta_days: int
    cost_delta: Decimal
    currency: str

    requester_user_id: UUID
    status: CRStatus

    layer1_approver_id: UUID | None
    layer1_approved_at: date | None
    layer1_notes: str | None
    layer2_approver_id: UUID | None
    layer2_approved_at: date | None
    layer2_notes: str | None

    rejected_at: date | None
    rejection_reason: str | None

    sales_notified_at: date | None
    finance_notified_at: date | None

    created_at: datetime
    updated_at: datetime

    # Derived
    requester_nik: str | None = None
    layer1_approver_nik: str | None = None
    layer2_approver_nik: str | None = None
    project_code: str | None = None
