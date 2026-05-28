"""Pydantic schemas untuk organization domain (Employee + Department + Position).

Per knowledge.md sec.3 (departments), sec.4 (employee types), sec.11 (employment lifecycle).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.organization.models import ContractType, EmployeeStatus, EmployeeType

# Forward enum for contract status (derived: ACTIVE, EXPIRING_SOON, EXPIRED, ENDED)
ContractStatus = Annotated[str, Field(pattern="^(ACTIVE|EXPIRING_SOON|EXPIRED|ENDED)$")]


# ─── Reusable types ────────────────────────────────────────────────

NIKType = Annotated[str, StringConstraints(min_length=3, max_length=30, strip_whitespace=True)]
CodeType = Annotated[str, StringConstraints(min_length=1, max_length=50, strip_whitespace=True)]


# ─── Department ────────────────────────────────────────────────────


class DepartmentBase(BaseModel):
    """Base dept fields."""

    code: CodeType
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    description: str | None = None


class DepartmentCreate(DepartmentBase):
    """Create dept request — Executive only."""

    head_user_id: UUID | None = None


class DepartmentUpdate(BaseModel):
    """Patch dept — partial update."""

    name: str | None = None
    description: str | None = None
    head_user_id: UUID | None = None


class DepartmentOut(DepartmentBase):
    """Dept response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    head_user_id: UUID | None
    created_at: datetime
    employee_count: int | None = None  # populated by service.list_departments


# ─── Position ──────────────────────────────────────────────────────


class PositionBase(BaseModel):
    code: CodeType
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    department_id: UUID
    level: Annotated[int, Field(ge=1, le=6)]
    salary_range_min: Decimal | None = None
    salary_range_max: Decimal | None = None


class PositionCreate(PositionBase):
    pass


class PositionUpdate(BaseModel):
    name: str | None = None
    level: int | None = Field(default=None, ge=1, le=6)
    salary_range_min: Decimal | None = None
    salary_range_max: Decimal | None = None


class PositionOut(PositionBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    department_name: str | None = None  # populated by service


# ─── Employee ──────────────────────────────────────────────────────


class EmployeeBase(BaseModel):
    """Personal + employment info (tidak termasuk NIK + user credentials)."""

    full_name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    photo_url: str | None = None
    date_of_birth: date | None = None
    gender: Annotated[str, StringConstraints(max_length=10)] | None = None
    phone_number: Annotated[str, StringConstraints(max_length=20)] | None = None
    address: str | None = None
    emergency_contact: str | None = None

    employee_type: EmployeeType
    status: EmployeeStatus = EmployeeStatus.PROBATION
    department_id: UUID | None = None
    position_id: UUID | None = None
    supervisor_id: UUID | None = None

    joined_date: date | None = None
    probation_end_date: date | None = None

    bank_name: Annotated[str, StringConstraints(max_length=50)] | None = None
    bank_account: Annotated[str, StringConstraints(max_length=50)] | None = None
    npwp: Annotated[str, StringConstraints(max_length=30)] | None = None


class EmployeeCreate(EmployeeBase):
    """Create employee — also creates User record with NIK + password.

    Aturan (knowledge.md sec.1): NIK = login identifier.
    Password default = NIK reversed (must change on first login).
    """

    nik: NIKType
    email: EmailStr | None = None
    initial_password: Annotated[str, StringConstraints(min_length=8, max_length=72)] | None = None
    role_codes: list[CodeType] = Field(default_factory=list)


class EmployeeUpdate(BaseModel):
    """Patch employee — all fields optional."""

    full_name: str | None = None
    photo_url: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    phone_number: str | None = None
    address: str | None = None
    emergency_contact: str | None = None

    status: EmployeeStatus | None = None
    department_id: UUID | None = None
    position_id: UUID | None = None
    supervisor_id: UUID | None = None

    probation_end_date: date | None = None
    last_working_day: date | None = None

    bank_name: str | None = None
    bank_account: str | None = None
    npwp: str | None = None


class EmployeeListItem(BaseModel):
    """Slim payload untuk list view — hanya field yang tampak di tabel."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID  # employees.id — dibutuhkan untuk cross-domain FK (mis. onboarding assignment)
    nik: str
    full_name: str
    email: str | None
    photo_url: str | None
    employee_type: EmployeeType
    status: EmployeeStatus
    department_name: str | None
    position_name: str | None
    supervisor_name: str | None
    joined_date: date | None


class EmployeeOut(EmployeeBase):
    """Full employee detail."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nik: str
    email: str | None
    last_working_day: date | None

    department_name: str | None = None
    position_name: str | None = None
    supervisor_name: str | None = None

    created_at: datetime
    updated_at: datetime


# ─── List + filter ─────────────────────────────────────────────────


class EmployeeListResponse(BaseModel):
    """Paginated employee list response."""

    items: list[EmployeeListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class EmployeeFilters(BaseModel):
    """Query filter untuk list employees."""

    q: str | None = None  # search by NIK / name / email
    department_id: UUID | None = None
    position_id: UUID | None = None
    employee_type: EmployeeType | None = None
    status: EmployeeStatus | None = None
    supervisor_id: UUID | None = None


# ─── Promote / Mutate / OrgChange ──────────────────────────────────


class EmployeePromote(BaseModel):
    """Promote employee — change position to higher level (US-OP-012)."""

    new_position_id: UUID
    effective_date: date
    new_salary: Decimal | None = None
    reason: Annotated[str, StringConstraints(min_length=10, max_length=1000)]


class EmployeeMutate(BaseModel):
    """Mutate employee — change department/position lateral (US-OP-013)."""

    new_department_id: UUID | None = None
    new_position_id: UUID | None = None
    new_supervisor_id: UUID | None = None
    effective_date: date
    reason: Annotated[str, StringConstraints(min_length=10, max_length=1000)]


class OrgChangeOut(BaseModel):
    """Audit log entry untuk org change history."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    change_type: str
    effective_date: date
    before_snapshot: dict | None
    after_snapshot: dict | None
    reason: str | None
    initiated_by_user_id: UUID | None
    approved_by_user_id: UUID | None
    created_at: datetime


# ─── Bulk import ────────────────────────────────────────────────────


class BulkImportResult(BaseModel):
    """Hasil bulk import — sukses count + error rows."""

    total_rows: int
    success_count: int
    error_count: int
    errors: list[dict] = Field(default_factory=list)
    created_niks: list[str] = Field(default_factory=list)


# ─── EmployeeContract (TSK-018) ────────────────────────────────────


class ContractBase(BaseModel):
    contract_type: ContractType
    start_date: date
    end_date: date | None = None
    salary: Decimal | None = None
    document_url: Annotated[str, StringConstraints(max_length=500)] | None = None


class ContractCreate(ContractBase):
    employee_id: UUID


class ContractUpdate(BaseModel):
    """Patch contract fields. Tidak bisa ubah type (gunakan renew/new contract)."""

    end_date: date | None = None
    salary: Decimal | None = None
    document_url: str | None = None
    is_active: bool | None = None


class ContractRenewRequest(BaseModel):
    """Renew PKWT — create new contract following existing one."""

    new_start_date: date
    new_end_date: date | None = None
    new_contract_type: ContractType  # bisa rotate ke PKWTT
    new_salary: Decimal | None = None
    notes: Annotated[str, StringConstraints(min_length=10, max_length=1000)]


class ContractTerminateRequest(BaseModel):
    """End contract earlier than end_date."""

    termination_date: date
    reason: Annotated[str, StringConstraints(min_length=10, max_length=1000)]


class ContractOut(ContractBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Derived
    employee_nik: str | None = None
    employee_name: str | None = None
    days_until_expiry: int | None = None
    derived_status: str | None = None  # ACTIVE / EXPIRING_SOON_30 / EXPIRING_SOON_7 / EXPIRED / ENDED


class ContractListItem(BaseModel):
    """Slim payload untuk list."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    employee_nik: str | None = None
    employee_name: str | None = None
    employee_department: str | None = None
    contract_type: ContractType
    start_date: date
    end_date: date | None
    is_active: bool
    days_until_expiry: int | None
    derived_status: str


class ContractListResponse(BaseModel):
    items: list[ContractListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class ContractExpiringAlert(BaseModel):
    """Dashboard widget data — contracts expiring dalam X hari."""

    total_h30: int  # contracts expiring 8-30 hari
    total_h7: int  # contracts expiring 0-7 hari (critical)
    total_expired_unrenewed: int  # already expired tapi masih is_active=true
    items: list[ContractListItem]


# ─── Org Chart (TSK-014) ───────────────────────────────────────────


class OrgChartNode(BaseModel):
    """Single node di org chart — employee dengan children.

    Built recursively: setiap employee bisa punya direct reports (employees
    yang supervisor_id-nya = node.id).
    """

    id: UUID
    nik: str
    full_name: str
    photo_url: str | None = None
    position_name: str | None = None
    position_level: int | None = None
    department_name: str | None = None
    employee_type: EmployeeType
    status: EmployeeStatus
    direct_reports_count: int = 0
    children: list["OrgChartNode"] = Field(default_factory=list)


class OrgChartResponse(BaseModel):
    """Org chart response — list of root nodes (employee tanpa supervisor)."""

    roots: list[OrgChartNode]
    total_employees: int
    department_id: UUID | None = None
    department_name: str | None = None
