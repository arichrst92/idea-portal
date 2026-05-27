"""Assessment & Performance domain — 7 tabel per ERD knowledge.md sec.20.

Tabel:
- assessment_configs    — bobot OKR vs Weighted per dept (config GM/C-Level)
- assessment_items      — komponen Weighted: Attitude, Kehadiran, Kolaborasi
- assessment_periods    — periode bulanan
- assessments           — score per karyawan per periode
- okr_objectives        — OKR per kuartal
- okr_key_results       — KR di bawah objective
- warning_letters       — SP1/SP2/SP3 internal (SP-O ada di outsource domain)

Schema detail full per EP-08 (M2.1). Sprint 1 skeleton only.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AssessmentConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Config bobot scoring per dept (knowledge.md sec.6)."""

    __tablename__ = "assessment_configs"

    department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id"), nullable=False)
    okr_weight_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    weighted_weight_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    configured_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class AssessmentItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Item Weighted: Attitude/Kehadiran/Kolaborasi dengan bobot."""

    __tablename__ = "assessment_items"

    config_id: Mapped[UUID] = mapped_column(ForeignKey("assessment_configs.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    weight_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)


class AssessmentPeriod(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Periode penilaian bulanan."""

    __tablename__ = "assessment_periods"

    year: Mapped[int] = mapped_column(nullable=False)
    month: Mapped[int] = mapped_column(nullable=False)
    is_closed: Mapped[bool] = mapped_column(default=False, nullable=False)


class Assessment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Score per karyawan per periode. Final = OKR×% + Weighted×%."""

    __tablename__ = "assessments"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    period_id: Mapped[UUID] = mapped_column(ForeignKey("assessment_periods.id"), nullable=False)
    okr_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    weighted_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    final_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class OkrObjective(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """OKR Objective per karyawan per kuartal."""

    __tablename__ = "okr_objectives"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(nullable=False)
    quarter: Mapped[int] = mapped_column(nullable=False)  # 1-4
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    set_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class OkrKeyResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Key Result di bawah Objective."""

    __tablename__ = "okr_key_results"

    objective_id: Mapped[UUID] = mapped_column(ForeignKey("okr_objectives.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str | None] = mapped_column(String(200), nullable=True)
    achieved: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    progress_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)


class WarningLetter(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """SP internal SP1/SP2/SP3 (SP-O outsource ada di outsource domain)."""

    __tablename__ = "warning_letters"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(10), nullable=False)  # SP1, SP2, SP3
    issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    document_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_ai_drafted: Mapped[bool] = mapped_column(default=False, nullable=False)
    acknowledged_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
