"""THR schemas — TSK-053 (US-FN-003)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ThrGenerateRequest(BaseModel):
    """Bulk generate THR untuk tahun tertentu."""

    thr_year: Annotated[int, Field(ge=2020, le=2099)]
    # Reference date — biasanya H-7 Lebaran. Used to compute months_worked.
    reference_date: date
    # Force regenerate untuk yang sudah ada (default skip)
    overwrite_existing: bool = False


class ThrMarkPaidRequest(BaseModel):
    payment_date: date
    transfer_ref: str | None = None


class ThrOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    thr_year: int
    base_salary: Decimal
    months_worked: Decimal
    thr_amount: Decimal
    currency: str
    status: str
    paid_at: datetime | None
    payment_date: date | None
    transfer_ref: str | None
    notes: str | None
    generated_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    # Enriched (populated by router)
    employee_nik: str | None = None
    employee_name: str | None = None


class ThrGenerateResponse(BaseModel):
    thr_year: int
    generated: int
    skipped: int  # already exists & overwrite_existing=False
    total_amount_idr: Decimal
    employee_count: int
    errors: list[str] = Field(default_factory=list)
