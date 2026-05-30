"""Pydantic schemas — outsource domain (TSK-100)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.outsource.models import BillingType


# ─── Placement ─────────────────────────────────────────────────────


class PlacementCreate(BaseModel):
    employee_id: UUID
    client_id: UUID
    role_at_client: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    start_date: date
    end_date: date | None = None
    billing_type: BillingType
    billing_rate: Annotated[Decimal, Field(ge=0)]


class PlacementUpdate(BaseModel):
    role_at_client: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    billing_type: BillingType | None = None
    billing_rate: Decimal | None = None
    is_active: bool | None = None


class PlacementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    client_id: UUID
    role_at_client: str
    start_date: date
    end_date: date | None
    billing_type: BillingType
    billing_rate: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Derived
    employee_nik: str | None = None
    employee_name: str | None = None
    client_code: str | None = None
    client_name: str | None = None
    monthly_billing_estimate: Decimal | None = None
    duration_days: int | None = None
    days_until_end: int | None = None


class PlacementListResponse(BaseModel):
    items: list[PlacementOut]
    total: int
    active_count: int
    expiring_30d: int


# ─── Client ────────────────────────────────────────────────────────


class ClientCreate(BaseModel):
    code: Annotated[str, StringConstraints(min_length=2, max_length=50)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    pic_name: str | None = None
    pic_email: str | None = None
    pic_phone: str | None = None
    address: str | None = None


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    pic_name: str | None
    pic_email: str | None
    pic_phone: str | None
    address: str | None
    is_active: bool
    created_at: datetime

    placement_count: int = 0
    active_placement_count: int = 0
