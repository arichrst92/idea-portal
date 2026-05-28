"""Organization domain — FastAPI endpoints.

TSK-013 (M1.2):
- /api/v1/employees           — list, create, detail, patch, soft-delete
- /api/v1/employees/{nik}/promote   — promotion flow (US-OP-012)
- /api/v1/employees/{nik}/mutate    — mutation flow (US-OP-013)
- /api/v1/employees/{nik}/history   — org change history
- /api/v1/departments         — list, create, patch
- /api/v1/positions           — list, create, patch

RBAC enforcement:
- employee.view  — semua authenticated user bisa lihat (filter by dept by GM+)
- employee.create / employee.edit — Executive + GM
- department.* + position.* — Executive only
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.audit import audit_log
from app.core.deps import (
    CurrentUser,
    DBSession,
    require_executive,
    require_permission,
)
from app.organization import service
from app.organization.schemas import (
    BulkImportResult,
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    EmployeeCreate,
    EmployeeFilters,
    EmployeeListItem,
    EmployeeListResponse,
    EmployeeMutate,
    EmployeeOut,
    EmployeePromote,
    EmployeeUpdate,
    OrgChangeOut,
    OrgChartResponse,
    PositionCreate,
    PositionOut,
    PositionUpdate,
)
from app.organization.service import (
    DepartmentNotFoundError,
    EmployeeAlreadyExistsError,
    EmployeeNotFoundError,
    InvalidEmployeeStateError,
    PositionNotFoundError,
)

router = APIRouter(tags=["organization"])


# ─── Helpers ───────────────────────────────────────────────────────


def _employee_to_out(emp) -> EmployeeOut:
    """Build EmployeeOut dari Employee ORM dengan derived fields."""
    return EmployeeOut(
        id=emp.id,
        nik=emp.user.nik,
        email=emp.user.email,
        full_name=emp.full_name,
        photo_url=emp.photo_url,
        date_of_birth=emp.date_of_birth,
        gender=emp.gender,
        phone_number=emp.phone_number,
        address=emp.address,
        emergency_contact=emp.emergency_contact,
        employee_type=emp.employee_type,
        status=emp.status,
        department_id=emp.department_id,
        position_id=emp.position_id,
        supervisor_id=emp.supervisor_id,
        joined_date=emp.joined_date,
        probation_end_date=emp.probation_end_date,
        last_working_day=emp.last_working_day,
        bank_name=emp.bank_name,
        bank_account=emp.bank_account,
        npwp=emp.npwp,
        department_name=emp.department.name if emp.department else None,
        position_name=emp.position.name if emp.position else None,
        supervisor_name=None,
        created_at=emp.created_at,
        updated_at=emp.updated_at,
    )


def _employee_to_list_item(emp) -> EmployeeListItem:
    """Build EmployeeListItem dari Employee ORM."""
    return EmployeeListItem(
        nik=emp.user.nik if emp.user else "",
        full_name=emp.full_name,
        email=emp.user.email if emp.user else None,
        photo_url=emp.photo_url,
        employee_type=emp.employee_type,
        status=emp.status,
        department_name=emp.department.name if emp.department else None,
        position_name=emp.position.name if emp.position else None,
        supervisor_name=None,
        joined_date=emp.joined_date,
    )


# ─── Employees ─────────────────────────────────────────────────────


@router.get("/employees", response_model=EmployeeListResponse)
async def list_employees_endpoint(
    session: DBSession,
    _user= Depends(require_permission("employee.view")),
    q: str | None = Query(None, description="Search by NIK / full_name / email"),
    department_id: UUID | None = Query(None),
    position_id: UUID | None = Query(None),
    employee_type: str | None = Query(None, description="A / B / C"),
    status_filter: str | None = Query(None, alias="status"),
    supervisor_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> EmployeeListResponse:
    """List employees dengan filter + search + pagination."""
    from app.organization.models import EmployeeStatus, EmployeeType

    filters = EmployeeFilters(
        q=q,
        department_id=department_id,
        position_id=position_id,
        employee_type=EmployeeType(employee_type) if employee_type else None,
        status=EmployeeStatus(status_filter) if status_filter else None,
        supervisor_id=supervisor_id,
    )

    employees, total = await service.list_employees(session, filters, page, page_size)
    items = [_employee_to_list_item(e) for e in employees]
    total_pages = service.calc_total_pages(total, page_size)

    return EmployeeListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/employees", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
async def create_employee_endpoint(
    request: Request,
    data: EmployeeCreate,
    session: DBSession,
    user= Depends(require_permission("employee.create")),
) -> EmployeeOut:
    """Create employee + linked User. Default password = NIK reversed."""
    try:
        emp = await service.create_employee(
            session=session,
            data=data,
            created_by_user_id=user.id,
        )
    except EmployeeAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_NIK", "message": str(e)},
        ) from e
    except (DepartmentNotFoundError, PositionNotFoundError, EmployeeNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_FK", "message": str(e)},
        ) from e

    await audit_log(
        session=session,
        actor=user,
        action="EMPLOYEE_CREATED",
        resource_type="employee",
        resource_id=str(emp.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        after_state={"nik": emp.user.nik, "full_name": emp.full_name},
    )
    return _employee_to_out(emp)


@router.get("/employees/{nik}", response_model=EmployeeOut)
async def get_employee_endpoint(
    nik: str,
    session: DBSession,
    _user= Depends(require_permission("employee.view")),
) -> EmployeeOut:
    """Get employee detail by NIK."""
    try:
        emp = await service.get_employee_by_nik(session, nik)
    except EmployeeNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "EMPLOYEE_NOT_FOUND", "message": str(e)},
        ) from e
    return _employee_to_out(emp)


@router.patch("/employees/{nik}", response_model=EmployeeOut)
async def update_employee_endpoint(
    request: Request,
    nik: str,
    data: EmployeeUpdate,
    session: DBSession,
    user= Depends(require_permission("employee.edit")),
) -> EmployeeOut:
    """Patch employee."""
    try:
        old_emp = await service.get_employee_by_nik(session, nik)
        before = {
            "full_name": old_emp.full_name,
            "status": old_emp.status,
            "department_id": str(old_emp.department_id) if old_emp.department_id else None,
            "position_id": str(old_emp.position_id) if old_emp.position_id else None,
        }
        emp = await service.update_employee(session, nik, data)
    except EmployeeNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "EMPLOYEE_NOT_FOUND", "message": str(e)},
        ) from e
    except (DepartmentNotFoundError, PositionNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_FK", "message": str(e)},
        ) from e
    except InvalidEmployeeStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_STATE", "message": str(e)},
        ) from e

    after = {
        "full_name": emp.full_name,
        "status": emp.status,
        "department_id": str(emp.department_id) if emp.department_id else None,
        "position_id": str(emp.position_id) if emp.position_id else None,
    }
    await audit_log(
        session=session,
        actor=user,
        action="EMPLOYEE_UPDATED",
        resource_type="employee",
        resource_id=str(emp.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        before_state=before,
        after_state=after,
    )
    return _employee_to_out(emp)


@router.delete("/employees/{nik}", response_model=EmployeeOut)
async def delete_employee_endpoint(
    request: Request,
    nik: str,
    session: DBSession,
    user= Depends(require_permission("employee.delete")),
) -> EmployeeOut:
    """Soft delete employee — status → ALUMNI, user.is_active = false."""
    try:
        emp = await service.soft_delete_employee(session, nik)
    except EmployeeNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "EMPLOYEE_NOT_FOUND", "message": str(e)},
        ) from e

    await audit_log(
        session=session,
        actor=user,
        action="EMPLOYEE_SOFT_DELETED",
        resource_type="employee",
        resource_id=str(emp.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        after_state={"status": emp.status, "deleted_at": str(emp.deleted_at)},
    )
    return _employee_to_out(emp)


# ─── Promote / Mutate ──────────────────────────────────────────────


@router.post("/employees/{nik}/promote", response_model=OrgChangeOut)
async def promote_employee_endpoint(
    request: Request,
    nik: str,
    data: EmployeePromote,
    session: DBSession,
    user= Depends(require_permission("employee.edit")),
) -> OrgChangeOut:
    """Promote employee — new position must be higher rank."""
    try:
        emp, org_change = await service.promote_employee(
            session=session,
            nik=nik,
            data=data,
            initiated_by_user_id=user.id,
        )
    except EmployeeNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "EMPLOYEE_NOT_FOUND", "message": str(e)}) from e
    except PositionNotFoundError as e:
        raise HTTPException(status_code=400, detail={"code": "POSITION_NOT_FOUND", "message": str(e)}) from e
    except InvalidEmployeeStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_PROMOTION", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="EMPLOYEE_PROMOTED",
        resource_type="employee",
        resource_id=str(emp.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        before_state=org_change.before_snapshot,
        after_state=org_change.after_snapshot,
        notes=f"Promoted via OrgChange {org_change.id}: {data.reason}",
    )
    return OrgChangeOut.model_validate(org_change)


@router.post("/employees/{nik}/mutate", response_model=OrgChangeOut)
async def mutate_employee_endpoint(
    request: Request,
    nik: str,
    data: EmployeeMutate,
    session: DBSession,
    user= Depends(require_permission("employee.edit")),
) -> OrgChangeOut:
    """Mutate employee — lateral move."""
    try:
        emp, org_change = await service.mutate_employee(
            session=session,
            nik=nik,
            data=data,
            initiated_by_user_id=user.id,
        )
    except EmployeeNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "EMPLOYEE_NOT_FOUND", "message": str(e)}) from e
    except (DepartmentNotFoundError, PositionNotFoundError) as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_FK", "message": str(e)}) from e
    except InvalidEmployeeStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_MUTATION", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="EMPLOYEE_MUTATED",
        resource_type="employee",
        resource_id=str(emp.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        before_state=org_change.before_snapshot,
        after_state=org_change.after_snapshot,
        notes=f"Mutated via OrgChange {org_change.id}: {data.reason}",
    )
    return OrgChangeOut.model_validate(org_change)


@router.get("/employees/{nik}/history", response_model=list[OrgChangeOut])
async def employee_history_endpoint(
    nik: str,
    session: DBSession,
    _user= Depends(require_permission("employee.view")),
    limit: int = Query(50, ge=1, le=200),
) -> list[OrgChangeOut]:
    """List org change history untuk employee."""
    try:
        emp = await service.get_employee_by_nik(session, nik)
    except EmployeeNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "EMPLOYEE_NOT_FOUND", "message": str(e)}) from e

    changes = await service.list_org_changes(session, emp.id, limit=limit)
    return [OrgChangeOut.model_validate(c) for c in changes]


# ─── Departments ───────────────────────────────────────────────────


@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments_endpoint(
    session: DBSession,
    _user= Depends(require_permission("employee.view")),
) -> list[DepartmentOut]:
    """List semua dept aktif."""
    depts = await service.list_departments(session)
    out: list[DepartmentOut] = []
    for d in depts:
        count = await service.count_employees_in_department(session, d.id)
        out.append(
            DepartmentOut(
                id=d.id,
                code=d.code,
                name=d.name,
                description=d.description,
                head_user_id=d.head_user_id,
                created_at=d.created_at,
                employee_count=count,
            )
        )
    return out


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department_endpoint(
    request: Request,
    data: DepartmentCreate,
    session: DBSession,
    user= Depends(require_executive()),
) -> DepartmentOut:
    """Create dept — Executive only."""
    try:
        dept = await service.create_department(session, data)
    except EmployeeAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_CODE", "message": str(e)},
        ) from e

    await audit_log(
        session=session,
        actor=user,
        action="DEPARTMENT_CREATED",
        resource_type="department",
        resource_id=str(dept.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        after_state={"code": dept.code, "name": dept.name},
    )
    return DepartmentOut.model_validate(dept)


@router.patch("/departments/{dept_id}", response_model=DepartmentOut)
async def update_department_endpoint(
    request: Request,
    dept_id: UUID,
    data: DepartmentUpdate,
    session: DBSession,
    user= Depends(require_executive()),
) -> DepartmentOut:
    """Patch dept — Executive only."""
    try:
        dept = await service.update_department(session, dept_id, data)
    except DepartmentNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "DEPT_NOT_FOUND", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="DEPARTMENT_UPDATED",
        resource_type="department",
        resource_id=str(dept.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        after_state=data.model_dump(exclude_unset=True),
    )
    return DepartmentOut.model_validate(dept)


# ─── Positions ─────────────────────────────────────────────────────


@router.get("/positions", response_model=list[PositionOut])
async def list_positions_endpoint(
    session: DBSession,
    _user= Depends(require_permission("employee.view")),
    department_id: UUID | None = Query(None),
) -> list[PositionOut]:
    """List positions, optional filter by dept."""
    positions = await service.list_positions(session, department_id=department_id)
    return [
        PositionOut(
            id=p.id,
            code=p.code,
            name=p.name,
            department_id=p.department_id,
            level=p.level,
            salary_range_min=p.salary_range_min,
            salary_range_max=p.salary_range_max,
            created_at=p.created_at,
            department_name=p.department.name if p.department else None,
        )
        for p in positions
    ]


@router.post("/positions", response_model=PositionOut, status_code=status.HTTP_201_CREATED)
async def create_position_endpoint(
    request: Request,
    data: PositionCreate,
    session: DBSession,
    user= Depends(require_executive()),
) -> PositionOut:
    """Create position — Executive only."""
    try:
        pos = await service.create_position(session, data)
    except DepartmentNotFoundError as e:
        raise HTTPException(status_code=400, detail={"code": "DEPT_NOT_FOUND", "message": str(e)}) from e
    except EmployeeAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail={"code": "DUPLICATE_CODE", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="POSITION_CREATED",
        resource_type="position",
        resource_id=str(pos.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        after_state={"code": pos.code, "name": pos.name, "level": pos.level},
    )
    return PositionOut(
        id=pos.id,
        code=pos.code,
        name=pos.name,
        department_id=pos.department_id,
        level=pos.level,
        salary_range_min=pos.salary_range_min,
        salary_range_max=pos.salary_range_max,
        created_at=pos.created_at,
        department_name=pos.department.name if pos.department else None,
    )


@router.patch("/positions/{position_id}", response_model=PositionOut)
async def update_position_endpoint(
    request: Request,
    position_id: UUID,
    data: PositionUpdate,
    session: DBSession,
    user= Depends(require_executive()),
) -> PositionOut:
    """Patch position — Executive only."""
    try:
        pos = await service.update_position(session, position_id, data)
    except PositionNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "POSITION_NOT_FOUND", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="POSITION_UPDATED",
        resource_type="position",
        resource_id=str(pos.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        after_state=data.model_dump(exclude_unset=True),
    )
    return PositionOut(
        id=pos.id,
        code=pos.code,
        name=pos.name,
        department_id=pos.department_id,
        level=pos.level,
        salary_range_min=pos.salary_range_min,
        salary_range_max=pos.salary_range_max,
        created_at=pos.created_at,
        department_name=pos.department.name if pos.department else None,
    )


# ─── Org Chart (TSK-014) ───────────────────────────────────────────


@router.get("/org-chart", response_model=OrgChartResponse)
async def org_chart_endpoint(
    session: DBSession,
    _user= Depends(require_permission("employee.view")),
    department_id: UUID | None = Query(
        None, description="Filter ke dept tertentu. None = all dept."
    ),
) -> OrgChartResponse:
    """Build org chart tree.

    Tree dibangun dari Employee.supervisor_id relationship. Root = employee
    tanpa supervisor (top hierarchy seperti CEO/Direktur Utama). Children
    di-sort by position level (lower number = higher rank → di atas).
    """
    roots, total, dept_name = await service.build_org_chart(session, department_id)
    return OrgChartResponse(
        roots=roots,
        total_employees=total,
        department_id=department_id,
        department_name=dept_name,
    )
