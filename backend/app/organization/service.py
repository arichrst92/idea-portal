"""Organization domain — business logic untuk Employee/Department/Position CRUD.

TSK-013 (M1.2 Chunk A):
- list_employees(filters, pagination)
- get_employee_by_nik
- create_employee (transactional: User + Employee + UserRole atomically)
- update_employee
- soft_delete_employee
- list_departments / create_department
- list_positions / create_position

Aturan kunci (knowledge.md):
- sec.1: NIK = login identifier (bukan email)
- sec.3: 4 dept utama (Teknologi, Operation, Sales & Marketing, Finance & Tax)
- sec.4: 3 tipe karyawan (A internal, B outsource-IDEA, C outsource-eksternal)
- sec.11: lifecycle PROBATION → ACTIVE → ON_LEAVE/RESIGNED/TERMINATED/ALUMNI
- NC-SYS-001-06: soft delete (deleted_at), bukan hard delete
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.identity.models import Role, User, UserRole
from app.organization.models import (
    ContractType,
    Department,
    Employee,
    EmployeeContract,
    EmployeeStatus,
    OrgChange,
    Position,
)
from app.organization.schemas import (
    ContractCreate,
    ContractRenewRequest,
    ContractTerminateRequest,
    ContractUpdate,
    DepartmentCreate,
    DepartmentUpdate,
    EmployeeCreate,
    EmployeeFilters,
    EmployeeMutate,
    EmployeePromote,
    EmployeeUpdate,
    PositionCreate,
    PositionUpdate,
)


# ─── Exceptions ────────────────────────────────────────────────────


class EmployeeNotFoundError(Exception):
    """NIK tidak ditemukan."""


class EmployeeAlreadyExistsError(Exception):
    """NIK sudah terdaftar."""


class DepartmentNotFoundError(Exception):
    """Department tidak ditemukan."""


class PositionNotFoundError(Exception):
    """Position tidak ditemukan."""


class InvalidEmployeeStateError(Exception):
    """Transition lifecycle tidak valid."""


# ─── Helpers ───────────────────────────────────────────────────────


def _generate_default_password(nik: str) -> str:
    """Default password = NIK reversed (must be changed at first login).

    Contoh: ADMIN-001 → 100-NIMDA. Min 8 chars (NIK harus min 3 chars).
    Padding kalau perlu untuk lolos bcrypt min length (12 chars setelah pad).
    """
    reversed_nik = nik[::-1]
    if len(reversed_nik) < 8:
        reversed_nik = (reversed_nik + "ide123!@").upper()[:12]
    return reversed_nik


def _employee_to_list_item_dict(emp: Employee) -> dict:
    """Convert Employee ORM → dict cocok untuk EmployeeListItem schema."""
    return {
        "nik": emp.user.nik if emp.user else "",
        "full_name": emp.full_name,
        "email": emp.user.email if emp.user else None,
        "photo_url": emp.photo_url,
        "employee_type": emp.employee_type,
        "status": emp.status,
        "department_name": emp.department.name if emp.department else None,
        "position_name": emp.position.name if emp.position else None,
        "supervisor_name": None,  # filled below
        "joined_date": emp.joined_date,
    }


# ─── Department ────────────────────────────────────────────────────


async def list_departments(session: AsyncSession) -> list[Department]:
    """List semua dept aktif, include employee count via subquery."""
    stmt = select(Department).where(Department.deleted_at.is_(None)).order_by(Department.code)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_department(session: AsyncSession, dept_id: UUID) -> Department:
    """Lookup dept by UUID, raise kalau tidak ada."""
    stmt = select(Department).where(Department.id == dept_id, Department.deleted_at.is_(None))
    result = await session.execute(stmt)
    dept = result.scalar_one_or_none()
    if not dept:
        raise DepartmentNotFoundError(f"Department {dept_id} not found")
    return dept


async def create_department(session: AsyncSession, data: DepartmentCreate) -> Department:
    """Create dept baru — Executive only (enforced di router level)."""
    dept = Department(**data.model_dump())
    session.add(dept)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        if "departments_code_key" in str(e):
            raise EmployeeAlreadyExistsError(f"Department code '{data.code}' sudah ada") from e
        raise
    await session.refresh(dept)
    return dept


async def update_department(
    session: AsyncSession, dept_id: UUID, data: DepartmentUpdate
) -> Department:
    """Patch dept — partial update."""
    dept = await get_department(session, dept_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(dept, field, value)
    await session.commit()
    await session.refresh(dept)
    return dept


async def count_employees_in_department(session: AsyncSession, dept_id: UUID) -> int:
    """Hitung jumlah karyawan aktif di dept (excluding soft-deleted)."""
    stmt = select(func.count(Employee.id)).where(
        Employee.department_id == dept_id,
        Employee.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())


# ─── Position ──────────────────────────────────────────────────────


async def list_positions(
    session: AsyncSession, department_id: UUID | None = None
) -> list[Position]:
    """List positions, optional filter by dept."""
    stmt = select(Position).options(selectinload(Position.department))
    if department_id is not None:
        stmt = stmt.where(Position.department_id == department_id)
    stmt = stmt.order_by(Position.level, Position.code)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_position(session: AsyncSession, position_id: UUID) -> Position:
    stmt = (
        select(Position)
        .where(Position.id == position_id)
        .options(selectinload(Position.department))
    )
    result = await session.execute(stmt)
    pos = result.scalar_one_or_none()
    if not pos:
        raise PositionNotFoundError(f"Position {position_id} not found")
    return pos


async def create_position(session: AsyncSession, data: PositionCreate) -> Position:
    # Verify dept exists
    await get_department(session, data.department_id)
    pos = Position(**data.model_dump())
    session.add(pos)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        if "positions_code_key" in str(e):
            raise EmployeeAlreadyExistsError(f"Position code '{data.code}' sudah ada") from e
        raise
    await session.refresh(pos, ["department"])
    return pos


async def update_position(
    session: AsyncSession, position_id: UUID, data: PositionUpdate
) -> Position:
    pos = await get_position(session, position_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(pos, field, value)
    await session.commit()
    await session.refresh(pos)
    return pos


# ─── Employee ──────────────────────────────────────────────────────


async def get_employee_by_nik(session: AsyncSession, nik: str) -> Employee:
    """Lookup employee by NIK (via User), with department/position/user eagerly loaded."""
    stmt = (
        select(Employee)
        .join(User, Employee.user_id == User.id)
        .where(User.nik == nik, Employee.deleted_at.is_(None), User.deleted_at.is_(None))
        .options(
            selectinload(Employee.user),
            selectinload(Employee.department),
            selectinload(Employee.position),
        )
    )
    result = await session.execute(stmt)
    emp = result.scalar_one_or_none()
    if not emp:
        raise EmployeeNotFoundError(f"Employee NIK '{nik}' not found")
    return emp


async def get_employee_by_id(session: AsyncSession, employee_id: UUID) -> Employee:
    """Lookup employee by employees.id (UUID)."""
    stmt = (
        select(Employee)
        .where(Employee.id == employee_id, Employee.deleted_at.is_(None))
        .options(
            selectinload(Employee.user),
            selectinload(Employee.department),
            selectinload(Employee.position),
        )
    )
    result = await session.execute(stmt)
    emp = result.scalar_one_or_none()
    if not emp:
        raise EmployeeNotFoundError(f"Employee {employee_id} not found")
    return emp


async def list_employees(
    session: AsyncSession,
    filters: EmployeeFilters,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Employee], int]:
    """List employees dengan filter + search + pagination.

    Returns: (employees, total_count)
    """
    page = max(page, 1)
    page_size = max(min(page_size, 200), 1)

    base = (
        select(Employee)
        .join(User, Employee.user_id == User.id)
        .where(Employee.deleted_at.is_(None), User.deleted_at.is_(None))
    )

    # Apply filters
    if filters.q:
        q = f"%{filters.q.lower()}%"
        base = base.where(
            or_(
                func.lower(User.nik).like(q),
                func.lower(Employee.full_name).like(q),
                func.lower(func.coalesce(User.email, "")).like(q),
            )
        )
    if filters.department_id is not None:
        base = base.where(Employee.department_id == filters.department_id)
    if filters.position_id is not None:
        base = base.where(Employee.position_id == filters.position_id)
    if filters.employee_type is not None:
        base = base.where(Employee.employee_type == filters.employee_type)
    if filters.status is not None:
        base = base.where(Employee.status == filters.status)
    if filters.supervisor_id is not None:
        base = base.where(Employee.supervisor_id == filters.supervisor_id)

    # Count total (sebelum pagination)
    count_stmt = select(func.count()).select_from(base.subquery())
    total_result = await session.execute(count_stmt)
    total = int(total_result.scalar_one())

    # Apply pagination + eager loading
    stmt = (
        base.options(
            selectinload(Employee.user),
            selectinload(Employee.department),
            selectinload(Employee.position),
        )
        .order_by(Employee.full_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    employees = list(result.scalars().all())
    return employees, total


async def create_employee(
    session: AsyncSession,
    data: EmployeeCreate,
    created_by_user_id: UUID,
) -> Employee:
    """Create employee + linked User + role assignment atomically.

    Steps:
    1. Validate NIK belum dipakai
    2. Validate dept_id + position_id exists (kalau diberikan)
    3. Create User (login record) dengan NIK + hashed password
    4. Create Employee (master record) linked ke User
    5. Assign roles (kalau role_codes diberikan)
    6. Commit atomically — rollback semua kalau gagal
    """
    # 1. Check NIK uniqueness
    existing = await session.execute(select(User).where(User.nik == data.nik))
    if existing.scalar_one_or_none():
        raise EmployeeAlreadyExistsError(f"NIK '{data.nik}' sudah terdaftar")

    # 2. Validate FKs
    if data.department_id is not None:
        await get_department(session, data.department_id)
    if data.position_id is not None:
        await get_position(session, data.position_id)
    if data.supervisor_id is not None:
        await get_employee_by_id(session, data.supervisor_id)

    # 3. Create User
    password = data.initial_password or _generate_default_password(data.nik)
    user = User(
        nik=data.nik,
        password_hash=hash_password(password),
        email=data.email,
        is_active=True,
    )
    session.add(user)
    await session.flush()  # generate user.id sebelum FK assignment

    # 4. Create Employee
    employee_dict = data.model_dump(
        exclude={"nik", "email", "initial_password", "role_codes"}
    )
    employee = Employee(user_id=user.id, **employee_dict)
    session.add(employee)
    await session.flush()

    # 5. Assign roles (kalau ada)
    if data.role_codes:
        roles_result = await session.execute(
            select(Role).where(Role.code.in_(data.role_codes))
        )
        roles = list(roles_result.scalars().all())
        for role in roles:
            user_role = UserRole(
                user_id=user.id,
                role_id=role.id,
                assigned_by_user_id=created_by_user_id,
            )
            session.add(user_role)

    # 6. Commit
    await session.commit()
    await session.refresh(
        employee,
        attribute_names=["user", "department", "position"],
    )
    return employee


async def update_employee(
    session: AsyncSession,
    nik: str,
    data: EmployeeUpdate,
) -> Employee:
    """Patch employee — partial update."""
    emp = await get_employee_by_nik(session, nik)

    # Validate FKs kalau di-set
    if data.department_id is not None:
        await get_department(session, data.department_id)
    if data.position_id is not None:
        await get_position(session, data.position_id)
    if data.supervisor_id is not None:
        if data.supervisor_id == emp.id:
            raise InvalidEmployeeStateError("Supervisor tidak boleh diri sendiri")
        await get_employee_by_id(session, data.supervisor_id)

    # Apply changes
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(emp, field, value)

    await session.commit()
    await session.refresh(emp, attribute_names=["user", "department", "position"])
    return emp


async def soft_delete_employee(session: AsyncSession, nik: str) -> Employee:
    """Soft delete — set deleted_at + status = ALUMNI.

    Per NC-SYS-001-06: financial-linked records tidak boleh hard delete.
    """
    from datetime import datetime as dt
    from datetime import timezone as tz

    emp = await get_employee_by_nik(session, nik)
    emp.deleted_at = dt.now(tz.utc)
    emp.status = EmployeeStatus.ALUMNI
    emp.user.is_active = False  # disable login
    await session.commit()
    await session.refresh(emp, attribute_names=["user"])
    return emp


# ─── Promote / Mutate (with OrgChange audit) ───────────────────────


async def promote_employee(
    session: AsyncSession,
    nik: str,
    data: EmployeePromote,
    initiated_by_user_id: UUID,
) -> tuple[Employee, OrgChange]:
    """Promote employee — change to higher-level position + audit OrgChange.

    Per US-OP-012: harus mencatat before/after snapshot + reason.
    """
    emp = await get_employee_by_nik(session, nik)
    new_position = await get_position(session, data.new_position_id)

    # Validate: new position level harus < current level (lower number = higher rank)
    if emp.position and new_position.level >= emp.position.level:
        raise InvalidEmployeeStateError(
            f"Promote butuh position dengan level < current ({emp.position.level}). "
            f"Position {new_position.code} = level {new_position.level}"
        )

    before = {
        "position_id": str(emp.position_id) if emp.position_id else None,
        "position_name": emp.position.name if emp.position else None,
        "position_level": emp.position.level if emp.position else None,
    }
    emp.position_id = new_position.id
    after = {
        "position_id": str(new_position.id),
        "position_name": new_position.name,
        "position_level": new_position.level,
    }

    org_change = OrgChange(
        employee_id=emp.id,
        change_type="PROMOTION",
        effective_date=data.effective_date,
        before_snapshot=before,
        after_snapshot=after,
        reason=data.reason,
        initiated_by_user_id=initiated_by_user_id,
    )
    session.add(org_change)
    await session.commit()
    await session.refresh(emp, attribute_names=["user", "department", "position"])
    await session.refresh(org_change)
    return emp, org_change


async def mutate_employee(
    session: AsyncSession,
    nik: str,
    data: EmployeeMutate,
    initiated_by_user_id: UUID,
) -> tuple[Employee, OrgChange]:
    """Mutate employee — lateral move (change dept/position/supervisor).

    Per US-OP-013: audit trail wajib.
    """
    emp = await get_employee_by_nik(session, nik)

    # Validate FKs kalau di-set
    if data.new_department_id is not None:
        await get_department(session, data.new_department_id)
    if data.new_position_id is not None:
        await get_position(session, data.new_position_id)
    if data.new_supervisor_id is not None:
        if data.new_supervisor_id == emp.id:
            raise InvalidEmployeeStateError("Supervisor tidak boleh diri sendiri")
        await get_employee_by_id(session, data.new_supervisor_id)

    before = {
        "department_id": str(emp.department_id) if emp.department_id else None,
        "position_id": str(emp.position_id) if emp.position_id else None,
        "supervisor_id": str(emp.supervisor_id) if emp.supervisor_id else None,
    }
    if data.new_department_id is not None:
        emp.department_id = data.new_department_id
    if data.new_position_id is not None:
        emp.position_id = data.new_position_id
    if data.new_supervisor_id is not None:
        emp.supervisor_id = data.new_supervisor_id
    after = {
        "department_id": str(emp.department_id) if emp.department_id else None,
        "position_id": str(emp.position_id) if emp.position_id else None,
        "supervisor_id": str(emp.supervisor_id) if emp.supervisor_id else None,
    }

    org_change = OrgChange(
        employee_id=emp.id,
        change_type="MUTATION",
        effective_date=data.effective_date,
        before_snapshot=before,
        after_snapshot=after,
        reason=data.reason,
        initiated_by_user_id=initiated_by_user_id,
    )
    session.add(org_change)
    await session.commit()
    await session.refresh(emp, attribute_names=["user", "department", "position"])
    await session.refresh(org_change)
    return emp, org_change


async def list_org_changes(
    session: AsyncSession, employee_id: UUID, limit: int = 50
) -> list[OrgChange]:
    """List org change history untuk seorang employee, terbaru di atas."""
    stmt = (
        select(OrgChange)
        .where(OrgChange.employee_id == employee_id)
        .order_by(OrgChange.effective_date.desc(), OrgChange.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_all_org_changes(
    session: AsyncSession,
    change_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[OrgChange], int]:
    """TSK-197/198 — global list of org changes untuk admin history page.

    Returns: (items, total).
    """
    base = select(OrgChange)
    if change_type:
        base = base.where(OrgChange.change_type == change_type)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    items_stmt = (
        base.order_by(
            OrgChange.effective_date.desc(), OrgChange.created_at.desc()
        )
        .offset(offset)
        .limit(limit)
    )
    items = list((await session.execute(items_stmt)).scalars().all())
    return items, total


# ─── Helpers untuk service consumers ───────────────────────────────


def calc_total_pages(total: int, page_size: int) -> int:
    """Total pages dari total + page_size."""
    if total == 0:
        return 0
    return math.ceil(total / page_size)


# ─── Org Chart tree builder (TSK-014) ──────────────────────────────


async def build_org_chart(
    session: AsyncSession, department_id: UUID | None = None
) -> tuple[list[dict], int, str | None]:
    """Build nested org chart tree dari employee.supervisor_id.

    Returns: (roots, total_count, dept_name)
    - roots: list of dict yang siap di-serialize ke OrgChartNode
    - root = employee tanpa supervisor (top of hierarchy)
    - children built recursively via supervisor_id lookup

    Args:
        session: AsyncSession
        department_id: filter ke dept tertentu (None = all dept)
    """
    # Fetch semua employee (single query, eager load) + filter optional
    stmt = (
        select(Employee)
        .where(Employee.deleted_at.is_(None))
        .options(
            selectinload(Employee.user),
            selectinload(Employee.department),
            selectinload(Employee.position),
        )
    )
    if department_id is not None:
        stmt = stmt.where(Employee.department_id == department_id)

    result = await session.execute(stmt)
    employees = list(result.scalars().all())

    if not employees:
        return [], 0, None

    # Build node lookup: id → dict
    nodes: dict[UUID, dict] = {}
    for emp in employees:
        nodes[emp.id] = {
            "id": emp.id,
            "nik": emp.user.nik if emp.user else "",
            "full_name": emp.full_name,
            "photo_url": emp.photo_url,
            "position_name": emp.position.name if emp.position else None,
            "position_level": emp.position.level if emp.position else None,
            "department_name": emp.department.name if emp.department else None,
            "employee_type": emp.employee_type,
            "status": emp.status,
            "direct_reports_count": 0,
            "children": [],
            "_supervisor_id": emp.supervisor_id,  # internal, dihapus sebelum return
        }

    # Wire children → parent
    roots: list[dict] = []
    for emp_id, node in nodes.items():
        sup_id = node["_supervisor_id"]
        if sup_id is not None and sup_id in nodes:
            parent = nodes[sup_id]
            parent["children"].append(node)
            parent["direct_reports_count"] += 1
        else:
            # No supervisor (atau supervisor di luar dept filter) → root
            roots.append(node)

    # Sort children by position level (lower = higher rank, di-atas)
    def _sort_recursive(node: dict) -> None:
        node["children"].sort(
            key=lambda n: (n.get("position_level") or 99, n["full_name"])
        )
        for child in node["children"]:
            _sort_recursive(child)

    for root in roots:
        _sort_recursive(root)
    roots.sort(key=lambda n: (n.get("position_level") or 99, n["full_name"]))

    # Cleanup internal field
    def _cleanup(node: dict) -> None:
        node.pop("_supervisor_id", None)
        for child in node["children"]:
            _cleanup(child)

    for root in roots:
        _cleanup(root)

    # Resolve dept name
    dept_name = None
    if department_id is not None:
        dept = await get_department(session, department_id)
        dept_name = dept.name

    return roots, len(employees), dept_name


# ─── EmployeeContract (TSK-018) ────────────────────────────────────


class ContractNotFoundError(Exception):
    pass


class InvalidContractStateError(Exception):
    pass


def derive_contract_status(contract: EmployeeContract, today: date | None = None) -> str:
    """Compute status string dari contract.

    Returns:
        ACTIVE — masih jauh dari expiry
        EXPIRING_SOON_30 — sisa 8-30 hari
        EXPIRING_SOON_7 — sisa 0-7 hari (critical alert)
        EXPIRED — end_date sudah lewat tapi masih is_active=true
        ENDED — is_active=false (terminated atau renewed)
    """
    today = today or date.today()
    if not contract.is_active:
        return "ENDED"
    if contract.end_date is None:
        return "ACTIVE"  # PKWTT — no expiry
    days_left = (contract.end_date - today).days
    if days_left < 0:
        return "EXPIRED"
    if days_left <= 7:
        return "EXPIRING_SOON_7"
    if days_left <= 30:
        return "EXPIRING_SOON_30"
    return "ACTIVE"


def days_until_expiry(contract: EmployeeContract, today: date | None = None) -> int | None:
    today = today or date.today()
    if contract.end_date is None:
        return None
    return (contract.end_date - today).days


async def get_contract(session: AsyncSession, contract_id: UUID) -> EmployeeContract:
    stmt = select(EmployeeContract).where(EmployeeContract.id == contract_id)
    result = await session.execute(stmt)
    contract = result.scalar_one_or_none()
    if contract is None:
        raise ContractNotFoundError(f"Contract {contract_id} not found")
    return contract


async def list_contracts(
    session: AsyncSession,
    employee_id: UUID | None = None,
    contract_type: ContractType | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[EmployeeContract], int]:
    page = max(page, 1)
    page_size = max(min(page_size, 200), 1)

    base = select(EmployeeContract)
    if employee_id is not None:
        base = base.where(EmployeeContract.employee_id == employee_id)
    if contract_type is not None:
        base = base.where(EmployeeContract.contract_type == contract_type)
    if is_active is not None:
        base = base.where(EmployeeContract.is_active == is_active)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    stmt = (
        base.order_by(EmployeeContract.start_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def create_contract(
    session: AsyncSession, data: ContractCreate
) -> EmployeeContract:
    """Create contract baru untuk employee.

    Validate:
    - Employee exists + active
    - PKWT wajib punya end_date, PKWTT tidak (open-ended)
    - Tidak ada contract active overlap untuk employee
    """
    # Validate employee
    emp_result = await session.execute(
        select(Employee).where(
            Employee.id == data.employee_id, Employee.deleted_at.is_(None)
        )
    )
    emp = emp_result.scalar_one_or_none()
    if emp is None:
        raise InvalidContractStateError(f"Employee {data.employee_id} not found / sudah deleted")

    # Type-specific validation
    if data.contract_type == ContractType.PKWT and data.end_date is None:
        raise InvalidContractStateError("PKWT wajib punya end_date")
    if data.end_date is not None and data.end_date <= data.start_date:
        raise InvalidContractStateError("end_date harus setelah start_date")

    # Check overlap dengan contract active existing
    overlap_stmt = select(EmployeeContract).where(
        EmployeeContract.employee_id == data.employee_id,
        EmployeeContract.is_active.is_(True),
    )
    existing = await session.execute(overlap_stmt)
    for prev in existing.scalars().all():
        # Overlap kalau salah satu kondisi:
        # - new.start_date di dalam (prev.start_date, prev.end_date or infinity)
        # - prev.start_date di dalam (new.start_date, new.end_date or infinity)
        prev_end = prev.end_date or date(9999, 12, 31)
        new_end = data.end_date or date(9999, 12, 31)
        if not (new_end < prev.start_date or data.start_date > prev_end):
            raise InvalidContractStateError(
                f"Overlap dengan contract aktif existing (id={prev.id}, "
                f"period {prev.start_date} - {prev.end_date or 'open'}). "
                "Terminate dulu contract lama atau pakai renew endpoint."
            )

    contract = EmployeeContract(
        employee_id=data.employee_id,
        contract_type=data.contract_type,
        start_date=data.start_date,
        end_date=data.end_date,
        salary=data.salary,
        document_url=data.document_url,
        is_active=True,
    )
    session.add(contract)
    await session.commit()
    await session.refresh(contract)
    return contract


async def update_contract(
    session: AsyncSession, contract_id: UUID, data: ContractUpdate
) -> EmployeeContract:
    contract = await get_contract(session, contract_id)
    update_data = data.model_dump(exclude_unset=True)
    if "end_date" in update_data and update_data["end_date"] is not None:
        if update_data["end_date"] <= contract.start_date:
            raise InvalidContractStateError("end_date harus setelah start_date")
    for field, value in update_data.items():
        setattr(contract, field, value)
    await session.commit()
    await session.refresh(contract)
    return contract


async def renew_contract(
    session: AsyncSession,
    contract_id: UUID,
    data: ContractRenewRequest,
) -> tuple[EmployeeContract, EmployeeContract]:
    """End existing contract + create new one. Returns (old, new)."""
    old_contract = await get_contract(session, contract_id)

    if not old_contract.is_active:
        raise InvalidContractStateError(
            "Contract sudah tidak aktif — tidak bisa di-renew. Buat contract baru saja."
        )

    # New contract validation
    if data.new_contract_type == ContractType.PKWT and data.new_end_date is None:
        raise InvalidContractStateError("New PKWT wajib punya new_end_date")
    if data.new_end_date is not None and data.new_end_date <= data.new_start_date:
        raise InvalidContractStateError("new_end_date harus setelah new_start_date")

    # End old contract
    old_contract.is_active = False
    # Optionally adjust old contract end_date kalau new starts earlier
    if old_contract.end_date is None or data.new_start_date <= old_contract.end_date:
        # Make sure old contract ends 1 day before new starts (kalau new starts during old)
        old_contract.end_date = data.new_start_date - timedelta(days=1)

    # Create new contract
    new_contract = EmployeeContract(
        employee_id=old_contract.employee_id,
        contract_type=data.new_contract_type,
        start_date=data.new_start_date,
        end_date=data.new_end_date,
        salary=data.new_salary if data.new_salary is not None else old_contract.salary,
        is_active=True,
    )
    session.add(new_contract)
    await session.commit()
    await session.refresh(old_contract)
    await session.refresh(new_contract)
    return old_contract, new_contract


async def terminate_contract(
    session: AsyncSession,
    contract_id: UUID,
    data: ContractTerminateRequest,
) -> EmployeeContract:
    """End contract earlier than original end_date."""
    contract = await get_contract(session, contract_id)
    if not contract.is_active:
        raise InvalidContractStateError("Contract sudah tidak aktif")
    if data.termination_date < contract.start_date:
        raise InvalidContractStateError("termination_date tidak boleh sebelum start_date")
    contract.end_date = data.termination_date
    contract.is_active = False
    await session.commit()
    await session.refresh(contract)
    return contract


async def get_expiring_contracts(
    session: AsyncSession, days_ahead: int = 30
) -> list[EmployeeContract]:
    """Contracts yang expire dalam X hari ke depan (PKWT only) atau sudah expired tapi masih active."""
    today = date.today()
    deadline = today + timedelta(days=days_ahead)

    # All active PKWT contracts dengan end_date <= deadline
    stmt = (
        select(EmployeeContract)
        .where(
            EmployeeContract.is_active.is_(True),
            EmployeeContract.contract_type == ContractType.PKWT,
            EmployeeContract.end_date.is_not(None),
            EmployeeContract.end_date <= deadline,
        )
        .order_by(EmployeeContract.end_date.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
