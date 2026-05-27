"""Organization domain — 5 tabel per ERD knowledge.md sec.20.

Tabel:
- departments         — 4 dept utama: Teknologi, Operation, Sales & Marketing, Finance & Tax
- positions           — jabatan fungsional per dept
- employees           — master karyawan (Type A internal / B outsource-IDEA / C outsource-eksternal)
- employee_contracts  — kontrak PKWT/PKWTT dengan alert H-30/H-7
- org_changes         — audit promosi/mutasi/role assignment

Schema detail full per EP-02 (M1.2). Sprint 1 hanya butuh `Employee` untuk link ke User.
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.identity.models import User


class EmployeeType(str, enum.Enum):
    """Tipe karyawan per knowledge.md sec.4."""

    TYPE_A_INTERNAL = "A"  # Karyawan IDEA langsung
    TYPE_B_OUTSOURCE_PLACED = "B"  # Outsource IDEA placed at client
    TYPE_C_OUTSOURCE_CONTRACT = "C"  # Outsource kontrak eksternal


class ContractType(str, enum.Enum):
    """Jenis kontrak per knowledge.md sec.11."""

    PKWT = "PKWT"  # Fixed-term
    PKWTT = "PKWTT"  # Permanent


class EmployeeStatus(str, enum.Enum):
    """Status karyawan lifecycle per knowledge.md sec.11."""

    PROBATION = "PROBATION"
    ACTIVE = "ACTIVE"
    ON_LEAVE = "ON_LEAVE"
    RESIGNED = "RESIGNED"
    TERMINATED = "TERMINATED"
    ALUMNI = "ALUMNI"


class Department(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """4 dept utama per knowledge.md sec.3."""

    __tablename__ = "departments"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    head_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    employees: Mapped[list[Employee]] = relationship(back_populates="department")
    positions: Mapped[list[Position]] = relationship(back_populates="department")


class Position(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Jabatan fungsional per dept."""

    __tablename__ = "positions"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id"), nullable=False)
    level: Mapped[int] = mapped_column(nullable=False)  # 1-6 hierarchy
    salary_range_min: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    salary_range_max: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)

    department: Mapped[Department] = relationship(back_populates="positions")


class Employee(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Master employee record. Link 1:1 ke User untuk login credentials."""

    __tablename__ = "employees"

    # Identity (NIK link ke users.nik)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Personal info
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    emergency_contact: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Employment
    employee_type: Mapped[EmployeeType] = mapped_column(String(1), nullable=False)
    status: Mapped[EmployeeStatus] = mapped_column(String(20), nullable=False, index=True)
    department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    position_id: Mapped[UUID | None] = mapped_column(ForeignKey("positions.id"), nullable=True)
    supervisor_id: Mapped[UUID | None] = mapped_column(ForeignKey("employees.id"), nullable=True)

    # Dates
    joined_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    probation_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_working_day: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Financial (basic — payroll detail di EP-05)
    bank_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(50), nullable=True)
    npwp: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Relationships
    user: Mapped[User] = relationship(back_populates="employee")
    department: Mapped[Department | None] = relationship(back_populates="employees")
    position: Mapped[Position | None] = relationship()


class EmployeeContract(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Kontrak PKWT/PKWTT dengan alert H-30/H-7 (TSK-020, TSK-199)."""

    __tablename__ = "employee_contracts"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    contract_type: Mapped[ContractType] = mapped_column(String(10), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    salary: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    document_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class OrgChange(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Audit trail untuk promosi/mutasi/role change (US-OP-012, US-OP-013)."""

    __tablename__ = "org_changes"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)  # promosi/mutasi/role/salary
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    before_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    initiated_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
