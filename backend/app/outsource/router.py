"""Outsource router — TSK-100.

Endpoints di /api/v1:
- GET    /outsource/placements              — list with filters
- POST   /outsource/placements              — create
- GET    /outsource/placements/{id}         — detail
- PATCH  /outsource/placements/{id}         — update
- DELETE /outsource/placements/{id}         — soft delete

- GET    /outsource/clients                 — list clients (master)
- POST   /outsource/clients                 — create client
- GET    /outsource/clients/{id}            — detail
"""

from __future__ import annotations

from datetime import date as _date, timedelta as _timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.core.audit import audit_log
from app.core.deps import DBSession, require_permission
from app.organization.models import Employee
from app.outsource import service
from app.outsource.models import Client as ClientModel, OutsourcePlacement
from app.outsource.schemas import (
    ClientCreate,
    ClientOut,
    PlacementCreate,
    PlacementListResponse,
    PlacementOut,
    PlacementUpdate,
)
from app.outsource.service import (
    ClientNotFoundError,
    DuplicateClientCodeError,
    PlacementNotFoundError,
)

router = APIRouter(tags=["outsource"], prefix="/outsource")


# ─── Helpers ───────────────────────────────────────────────────────


async def _lookup_employee(session, employee_id: UUID | None):
    if employee_id is None:
        return None, None
    r = await session.execute(
        select(Employee.nik, Employee.full_name).where(Employee.id == employee_id)
    )
    row = r.one_or_none()
    return (row[0], row[1]) if row else (None, None)


async def _lookup_client(session, client_id: UUID | None):
    if client_id is None:
        return None, None
    r = await session.execute(
        select(ClientModel.code, ClientModel.name).where(ClientModel.id == client_id)
    )
    row = r.one_or_none()
    return (row[0], row[1]) if row else (None, None)


async def _placement_to_out(session, p: OutsourcePlacement) -> PlacementOut:
    emp_nik, emp_name = await _lookup_employee(session, p.employee_id)
    cli_code, cli_name = await _lookup_client(session, p.client_id)
    monthly = service.compute_monthly_billing(p)
    duration = service.duration_days(p)
    days_end = service.days_until_end(p)
    return PlacementOut(
        id=p.id, employee_id=p.employee_id, client_id=p.client_id,
        role_at_client=p.role_at_client, start_date=p.start_date, end_date=p.end_date,
        billing_type=p.billing_type, billing_rate=p.billing_rate,
        is_active=p.is_active, created_at=p.created_at, updated_at=p.updated_at,
        employee_nik=emp_nik, employee_name=emp_name,
        client_code=cli_code, client_name=cli_name,
        monthly_billing_estimate=monthly, duration_days=duration,
        days_until_end=days_end,
    )


async def _client_to_out(session, c: ClientModel) -> ClientOut:
    total = await service.count_placements_for_client(session, c.id)
    active = await service.count_placements_for_client(session, c.id, active_only=True)
    return ClientOut(
        id=c.id, code=c.code, name=c.name,
        pic_name=c.pic_name, pic_email=c.pic_email, pic_phone=c.pic_phone,
        address=c.address, is_active=c.is_active, created_at=c.created_at,
        placement_count=total, active_placement_count=active,
    )


# ─── Placement endpoints ──────────────────────────────────────────


@router.get("/placements", response_model=PlacementListResponse)
async def list_placements_endpoint(
    session: DBSession,
    client_id: UUID | None = None,
    employee_id: UUID | None = None,
    is_active: bool | None = None,
    _user=Depends(require_permission("employee.view")),
) -> PlacementListResponse:
    placements = await service.list_placements(
        session, client_id=client_id, employee_id=employee_id, is_active=is_active,
    )
    today = _date.today()
    h30 = today + _timedelta(days=30)
    active_count = sum(1 for p in placements if p.is_active)
    expiring_30d = sum(
        1 for p in placements
        if p.is_active and p.end_date and today <= p.end_date <= h30
    )
    items = [await _placement_to_out(session, p) for p in placements]
    return PlacementListResponse(
        items=items, total=len(items),
        active_count=active_count, expiring_30d=expiring_30d,
    )


@router.get("/placements/{placement_id}", response_model=PlacementOut)
async def get_placement_endpoint(
    placement_id: UUID, session: DBSession,
    _user=Depends(require_permission("employee.view")),
) -> PlacementOut:
    try:
        p = await service.get_placement(session, placement_id)
    except PlacementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    return await _placement_to_out(session, p)


@router.post(
    "/placements", response_model=PlacementOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_placement_endpoint(
    request: Request, data: PlacementCreate, session: DBSession,
    user=Depends(require_permission("employee.edit")),
) -> PlacementOut:
    p = await service.create_placement(session, data)
    await audit_log(
        session=session, actor=user, action="PLACEMENT_CREATED",
        resource_type="outsource_placement", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "employee_id": str(p.employee_id),
            "client_id": str(p.client_id),
            "role": p.role_at_client,
            "billing_type": p.billing_type.value if hasattr(p.billing_type, "value") else str(p.billing_type),
            "rate": float(p.billing_rate),
        },
    )
    return await _placement_to_out(session, p)


@router.patch("/placements/{placement_id}", response_model=PlacementOut)
async def update_placement_endpoint(
    request: Request, placement_id: UUID, data: PlacementUpdate, session: DBSession,
    user=Depends(require_permission("employee.edit")),
) -> PlacementOut:
    try:
        p = await service.update_placement(session, placement_id, data)
    except PlacementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="PLACEMENT_UPDATED",
        resource_type="outsource_placement", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
        after_state=data.model_dump(exclude_unset=True, mode="json"),
    )
    return await _placement_to_out(session, p)


@router.delete("/placements/{placement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_placement_endpoint(
    request: Request, placement_id: UUID, session: DBSession,
    user=Depends(require_permission("employee.edit")),
) -> None:
    try:
        await service.soft_delete_placement(session, placement_id)
    except PlacementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="PLACEMENT_DELETED",
        resource_type="outsource_placement", resource_id=str(placement_id),
        ip_address=request.client.host if request.client else None,
    )


# ─── Client endpoints ─────────────────────────────────────────────


@router.get("/clients", response_model=list[ClientOut])
async def list_clients_endpoint(
    session: DBSession,
    is_active: bool | None = None,
    _user=Depends(require_permission("employee.view")),
) -> list[ClientOut]:
    clients = await service.list_clients(session, is_active=is_active)
    return [await _client_to_out(session, c) for c in clients]


@router.get("/clients/{client_id}", response_model=ClientOut)
async def get_client_endpoint(
    client_id: UUID, session: DBSession,
    _user=Depends(require_permission("employee.view")),
) -> ClientOut:
    try:
        c = await service.get_client(session, client_id)
    except ClientNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    return await _client_to_out(session, c)


@router.post(
    "/clients", response_model=ClientOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_client_endpoint(
    request: Request, data: ClientCreate, session: DBSession,
    user=Depends(require_permission("employee.edit")),
) -> ClientOut:
    try:
        c = await service.create_client(session, data)
    except DuplicateClientCodeError as e:
        raise HTTPException(status_code=409, detail={"code": "DUPLICATE_CODE", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="CLIENT_CREATED",
        resource_type="client", resource_id=str(c.id),
        ip_address=request.client.host if request.client else None,
        after_state={"code": c.code, "name": c.name},
    )
    return await _client_to_out(session, c)
