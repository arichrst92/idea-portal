"""Pydantic schemas — assessment domain TSK-021.

Per knowledge.md sec.6:
- Score per karyawan = (OKR × bobot_okr%) + (Weighted × bobot_weighted%)
- Bobot di-set per dept oleh GM/C-Level via AssessmentConfig
- Weighted = sum (AssessmentItem.weight_pct × item_score) — e.g. Attitude 30% + Kehadiran 30% + Kolaborasi 40%
- Threshold: bln-1 kuning, bln-2 oranye, bln-3 → SP otomatis
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


# ─── AssessmentPeriod ──────────────────────────────────────────────


class PeriodCreate(BaseModel):
    year: Annotated[int, Field(ge=2020, le=2099)]
    month: Annotated[int, Field(ge=1, le=12)]


class PeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    year: int
    month: int
    is_closed: bool
    created_at: datetime


# ─── AssessmentConfig + Items ──────────────────────────────────────


class ItemSpec(BaseModel):
    """Item Weighted dengan bobot."""

    code: Annotated[str, StringConstraints(min_length=1, max_length=50, strip_whitespace=True)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    weight_pct: Annotated[Decimal, Field(ge=0, le=100)]


class ConfigCreate(BaseModel):
    department_id: UUID
    okr_weight_pct: Annotated[Decimal, Field(ge=0, le=100)]
    weighted_weight_pct: Annotated[Decimal, Field(ge=0, le=100)]
    effective_date: date
    items: list[ItemSpec] = Field(default_factory=list)


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    config_id: UUID
    code: str
    name: str
    weight_pct: Decimal


class ConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    department_id: UUID
    okr_weight_pct: Decimal
    weighted_weight_pct: Decimal
    effective_date: date
    configured_by_user_id: UUID | None
    created_at: datetime

    # Derived
    department_name: str | None = None
    items: list[ItemOut] = Field(default_factory=list)


# ─── OKR ───────────────────────────────────────────────────────────


class KeyResultSpec(BaseModel):
    description: Annotated[str, StringConstraints(min_length=5, max_length=1000)]
    target: str | None = None


class KeyResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    objective_id: UUID
    description: str
    target: str | None
    achieved: Decimal | None
    progress_pct: Decimal


class KeyResultUpdate(BaseModel):
    achieved: Decimal | None = None
    progress_pct: Annotated[Decimal, Field(ge=0, le=100)] | None = None


class ObjectiveCreate(BaseModel):
    employee_id: UUID
    year: Annotated[int, Field(ge=2020, le=2099)]
    quarter: Annotated[int, Field(ge=1, le=4)]
    objective: Annotated[str, StringConstraints(min_length=10, max_length=2000)]
    key_results: list[KeyResultSpec] = Field(default_factory=list)


class ObjectiveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    year: int
    quarter: int
    objective: str
    set_by_user_id: UUID | None
    created_at: datetime

    # Derived
    employee_nik: str | None = None
    employee_name: str | None = None
    key_results: list[KeyResultOut] = Field(default_factory=list)
    avg_progress: Decimal | None = None


# ─── Assessment ────────────────────────────────────────────────────


class WeightedItemScore(BaseModel):
    """Score per item Weighted (untuk submit)."""

    item_code: str  # match AssessmentItem.code
    score: Annotated[Decimal, Field(ge=0, le=100)]


class AssessmentSubmit(BaseModel):
    """Submit score untuk 1 karyawan 1 periode.

    Backend akan:
    1. Compute weighted_score = sum (item.weight_pct × score) / 100
    2. Compute final_score = okr_score × okr_weight + weighted_score × weighted_weight
    """

    employee_id: UUID
    period_id: UUID
    okr_score: Annotated[Decimal, Field(ge=0, le=100)]
    weighted_items: list[WeightedItemScore]
    notes: str | None = None


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    period_id: UUID
    okr_score: Decimal | None
    weighted_score: Decimal | None
    final_score: Decimal | None
    notes: str | None
    submitted_by_user_id: UUID | None
    created_at: datetime

    # Derived
    employee_nik: str | None = None
    employee_name: str | None = None
    department_name: str | None = None
    period_label: str | None = None  # "Apr 2026"
    threshold_flag: str | None = None  # GREEN / YELLOW / ORANGE / RED


class AssessmentListResponse(BaseModel):
    items: list[AssessmentOut]
    total: int
    page: int
    page_size: int
    total_pages: int


# ─── Warning Letter (SP) ───────────────────────────────────────────


class WarningLetterCreate(BaseModel):
    employee_id: UUID
    level: Annotated[str, StringConstraints(pattern="^SP[123]$")]
    issued_date: date
    reason: Annotated[str, StringConstraints(min_length=20, max_length=5000)]
    document_url: str | None = None


class WarningLetterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    level: str
    issued_date: date
    reason: str
    document_url: str | None
    is_ai_drafted: bool
    acknowledged_at: date | None
    approved_by_user_id: UUID | None
    created_at: datetime

    employee_nik: str | None = None
    employee_name: str | None = None


# ─── SP Threshold Check ────────────────────────────────────────────


class ThresholdCheckResponse(BaseModel):
    """Hasil check threshold per employee — alert kalau perlu SP."""

    employee_id: UUID
    employee_nik: str | None
    employee_name: str | None
    department_id: UUID | None
    department_name: str | None
    consecutive_low_months: int
    threshold_score: Decimal
    recent_scores: list[dict]  # [{period: "Apr 2026", final_score: 65, flag: "YELLOW"}, ...]
    suggested_sp_level: str | None  # SP1/SP2/SP3 atau None
    action_required: bool
