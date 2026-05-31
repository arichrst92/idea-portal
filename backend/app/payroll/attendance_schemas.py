"""Attendance schemas — TSK-047."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AttendanceRow(BaseModel):
    """Single attendance record — input."""

    employee_id: UUID
    days_present: int = Field(..., ge=0, le=31)
    days_absent_paid: int = Field(0, ge=0, le=31)
    days_absent_unpaid: int = Field(0, ge=0, le=31)
    overtime_hours: Decimal = Field(0, ge=0, le=300)  # max 300h/month sanity
    notes: str | None = None

    @field_validator("overtime_hours", mode="before")
    @classmethod
    def parse_decimal(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v


class AttendanceBulkUpsert(BaseModel):
    """Bulk upsert for a single period (Operation submits all at once)."""

    period_id: UUID
    rows: list[AttendanceRow]


class AttendanceOut(BaseModel):
    """Single attendance record — output."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    period_id: UUID
    days_present: int
    days_absent_paid: int
    days_absent_unpaid: int
    overtime_hours: Decimal
    notes: str | None
    input_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    # Enriched (joined) — populated by service
    employee_nik: str | None = None
    employee_name: str | None = None
    department_name: str | None = None


class AttendanceListResponse(BaseModel):
    """List attendance for a period + completeness info."""

    period_id: UUID
    period_year: int
    period_month: int
    period_status: str
    calendar_working_days: int  # total business days in period (excl weekend+holiday)
    total_active_employees: int
    submitted_count: int
    missing_count: int
    items: list[AttendanceOut]


class AttendanceCompletenessResponse(BaseModel):
    """Cheap completeness check — no item list."""

    period_id: UUID
    calendar_working_days: int
    total_active_employees: int
    submitted_count: int
    missing_count: int
    missing_employee_ids: list[UUID]


class AttendanceUpdate(BaseModel):
    """PATCH single record."""

    days_present: int | None = Field(None, ge=0, le=31)
    days_absent_paid: int | None = Field(None, ge=0, le=31)
    days_absent_unpaid: int | None = Field(None, ge=0, le=31)
    overtime_hours: Decimal | None = Field(None, ge=0, le=300)
    notes: str | None = None
