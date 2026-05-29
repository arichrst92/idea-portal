"""Pydantic schemas — reimbursement + procurement + vendor (TSK-023)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Reason = Annotated[str, StringConstraints(min_length=10, max_length=2000, strip_whitespace=True)]

REIMB_CATEGORIES = [
    "MEDICAL",
    "TRANSPORT",
    "MEAL",
    "BUSINESS_TRIP",
    "COMMUNICATION",
    "ENTERTAINMENT",
    "OTHER",
]

PROCUREMENT_CATEGORIES = [
    "IT_EQUIPMENT",
    "OFFICE_SUPPLIES",
    "FURNITURE",
    "SOFTWARE_LICENSE",
    "MARKETING",
    "OTHER",
]


# ─── Reimbursement ─────────────────────────────────────────────────


class ReimbursementCreate(BaseModel):
    employee_id: UUID
    request_date: date
    category: Annotated[str, StringConstraints(pattern="^(MEDICAL|TRANSPORT|MEAL|BUSINESS_TRIP|COMMUNICATION|ENTERTAINMENT|OTHER)$")] = "OTHER"
    amount: Annotated[Decimal, Field(ge=0)]
    currency: Annotated[str, StringConstraints(min_length=3, max_length=3)] = "IDR"
    description: Annotated[str, StringConstraints(min_length=10, max_length=2000)]
    receipt_url: str | None = None
    project_id: UUID | None = None


class ReimbursementApprove(BaseModel):
    notes: str | None = None


class ReimbursementReject(BaseModel):
    rejection_reason: Reason


class ReimbursementTransfer(BaseModel):
    """Mark sebagai TRANSFERRED setelah Finance kirim transfer."""

    transfer_reference: Annotated[str, StringConstraints(min_length=3, max_length=100)]


class ReimbursementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    request_date: date
    category: str
    amount: Decimal
    currency: str
    description: str
    receipt_url: str | None
    project_id: UUID | None
    status: str

    layer1_approver_id: UUID | None
    layer1_approved_at: datetime | None
    layer1_notes: str | None
    layer2_approver_id: UUID | None
    layer2_approved_at: datetime | None
    layer2_notes: str | None
    rejected_by_user_id: UUID | None
    rejected_at: datetime | None
    rejection_reason: str | None
    cancelled_at: datetime | None

    transferred_at: date | None
    transferred_by_user_id: UUID | None
    transfer_reference: str | None

    created_at: datetime
    updated_at: datetime

    # Derived
    employee_nik: str | None = None
    employee_name: str | None = None
    project_name: str | None = None
    layer1_approver_nik: str | None = None
    layer2_approver_nik: str | None = None


class ReimbursementListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    employee_nik: str | None = None
    employee_name: str | None = None
    request_date: date
    category: str
    amount: Decimal
    currency: str
    status: str
    transferred_at: date | None
    project_name: str | None = None
    created_at: datetime


class ReimbursementListResponse(BaseModel):
    items: list[ReimbursementListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ─── Vendor ────────────────────────────────────────────────────────


class VendorCreate(BaseModel):
    code: Annotated[str, StringConstraints(min_length=2, max_length=50, strip_whitespace=True)]
    name: Annotated[str, StringConstraints(min_length=2, max_length=200)]
    contact_info: str | None = None


class VendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    contact_info: str | None
    created_at: datetime


# ─── Procurement ───────────────────────────────────────────────────


class ProcurementCreate(BaseModel):
    item_description: Annotated[str, StringConstraints(min_length=10, max_length=2000)]
    item_category: Annotated[str, StringConstraints(pattern="^(IT_EQUIPMENT|OFFICE_SUPPLIES|FURNITURE|SOFTWARE_LICENSE|MARKETING|OTHER)$")] = "OTHER"
    quantity: Annotated[int, Field(ge=1, le=9999)] = 1
    estimated_amount: Decimal | None = None
    currency: Annotated[str, StringConstraints(min_length=3, max_length=3)] = "IDR"
    vendor_id: UUID | None = None
    is_asset: bool = False
    expected_delivery_date: date | None = None
    request_date: date | None = None
    notes: str | None = None


class ProcurementOrder(BaseModel):
    """Mark sebagai ORDERED dengan PO number."""

    po_number: Annotated[str, StringConstraints(min_length=3, max_length=50)]
    vendor_id: UUID | None = None
    actual_amount: Decimal | None = None


class ProcurementDeliver(BaseModel):
    """Mark sebagai DELIVERED."""

    actual_delivery_date: date


class ProcurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    requested_by_user_id: UUID
    request_date: date | None
    item_description: str
    item_category: str
    quantity: int
    estimated_amount: Decimal | None
    actual_amount: Decimal | None
    currency: str
    vendor_id: UUID | None
    is_asset: bool
    expected_delivery_date: date | None
    actual_delivery_date: date | None
    notes: str | None
    status: str

    layer1_approver_id: UUID | None
    layer1_approved_at: datetime | None
    layer1_notes: str | None
    layer2_approver_id: UUID | None
    layer2_approved_at: datetime | None
    layer2_notes: str | None
    rejected_by_user_id: UUID | None
    rejected_at: datetime | None
    rejection_reason: str | None
    cancelled_at: datetime | None

    po_number: str | None
    ordered_at: date | None

    created_at: datetime
    updated_at: datetime

    # Derived
    requested_by_nik: str | None = None
    vendor_name: str | None = None
    vendor_code: str | None = None


class ProcurementListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    requested_by_nik: str | None = None
    item_description: str
    item_category: str
    quantity: int
    estimated_amount: Decimal | None
    actual_amount: Decimal | None
    currency: str
    vendor_name: str | None = None
    status: str
    is_asset: bool
    expected_delivery_date: date | None
    actual_delivery_date: date | None
    created_at: datetime


class ProcurementListResponse(BaseModel):
    items: list[ProcurementListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
