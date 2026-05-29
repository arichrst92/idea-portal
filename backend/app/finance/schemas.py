"""Pydantic schemas — finance/invoice domain (TSK-022C)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.finance.models import InvoiceStatus


InvoiceNo = Annotated[str, StringConstraints(min_length=3, max_length=50, strip_whitespace=True)]


# ─── Invoice ───────────────────────────────────────────────────────


class InvoiceCreate(BaseModel):
    invoice_no: InvoiceNo
    project_id: UUID | None = None
    trigger_phase_id: UUID | None = None
    client_id: UUID | None = None
    client_name_snapshot: str | None = None
    termin_pct: Annotated[Decimal, Field(ge=0, le=100)] | None = None
    amount: Annotated[Decimal, Field(ge=0)]
    currency: Annotated[str, StringConstraints(min_length=3, max_length=3)] = "IDR"
    tax_pct: Annotated[Decimal, Field(ge=0, le=100)] = Decimal("11.0")
    issue_date: date | None = None
    due_date: date | None = None
    notes: str | None = None


class InvoiceUpdate(BaseModel):
    status: InvoiceStatus | None = None
    paid_amount: Decimal | None = None
    paid_at: date | None = None
    due_date: date | None = None
    notes: str | None = None


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_no: str
    project_id: UUID | None
    trigger_phase_id: UUID | None
    client_id: UUID | None
    client_name_snapshot: str | None
    termin_pct: Decimal | None
    amount: Decimal
    currency: str
    tax_pct: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    issue_date: date | None
    due_date: date | None
    notified_finance_at: date | None
    status: InvoiceStatus
    paid_amount: Decimal
    paid_at: date | None
    notes: str | None
    created_at: datetime

    # Derived
    project_code: str | None = None
    project_name: str | None = None
    days_overdue: int | None = None
    aging_bucket: str | None = None  # CURRENT / 1-30 / 31-60 / 61-90 / 90+


class InvoiceListResponse(BaseModel):
    items: list[InvoiceOut]
    total: int
    page: int
    page_size: int
    total_pages: int
