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
    BeritaAcaraOut,
    ClientComplaintCreate,
    ClientComplaintOut,
    ClientComplaintUpdate,
    ClientCreate,
    ClientOut,
    PlacementCreate,
    ClientKpiCreate,
    ClientKpiOut,
    ClientKpiSubmit,
    PlacementAmendmentOut,
    PlacementListResponse,
    PlacementOut,
    PlacementRenewRequest,
    PlacementUpdate,
    PublicKpiContext,
    SpoCreate,
    SpoOut,
    TimesheetApprove,
    TimesheetCreate,
    TimesheetItemOut,
    TimesheetItemUpsert,
    TimesheetOut,
    TimesheetReject,
)
from app.outsource.service import (
    BANotFoundError,
    BAStateError,
    ClientNotFoundError,
    ComplaintNotFoundError,
    DuplicateClientCodeError,
    DuplicateTimesheetError,
    KpiNotFoundError,
    KpiStateError,
    PlacementAmendmentError,
    PlacementNotFoundError,
    SpoNotFoundError,
    SpoStateError,
    TimesheetNotFoundError,
    TimesheetStateError,
)
from app.core.storage import get_presigned_url
from app.outsource.models import Timesheet, TimesheetItem  # noqa: F401

router = APIRouter(tags=["outsource"], prefix="/outsource")


# ─── Helpers ───────────────────────────────────────────────────────


async def _lookup_employee(session, employee_id: UUID | None):
    if employee_id is None:
        return None, None
    from app.identity.models import User as _User
    r = await session.execute(
        select(_User.nik, Employee.full_name)
        .join(_User, Employee.user_id == _User.id)
        .where(Employee.id == employee_id)
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


# ─── Timesheet endpoints (TSK-103+104) ────────────────────────────


MONTHS_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


async def _ts_to_out(session, ts, include_items: bool = False) -> TimesheetOut:
    # Lookup placement details
    from app.identity.models import User as _User2
    pl_stmt = select(
        _User2.nik.label("emp_nik"),
        Employee.full_name.label("emp_name"),
        ClientModel.code.label("cli_code"),
        ClientModel.name.label("cli_name"),
        OutsourcePlacement.role_at_client.label("role"),
    ).select_from(OutsourcePlacement).join(
        Employee, OutsourcePlacement.employee_id == Employee.id,
    ).join(
        _User2, Employee.user_id == _User2.id,
    ).join(
        ClientModel, OutsourcePlacement.client_id == ClientModel.id,
    ).where(OutsourcePlacement.id == ts.placement_id)
    pl_row = (await session.execute(pl_stmt)).one_or_none()

    items_out = []
    present_count = 0
    absent_count = 0
    if include_items:
        items = await service.get_timesheet_items(session, ts.id)
        items_out = [
            TimesheetItemOut(
                id=i.id, timesheet_id=i.timesheet_id,
                work_date=i.work_date, is_present=i.is_present, notes=i.notes,
            ) for i in items
        ]
        present_count = sum(1 for i in items if i.is_present)
        absent_count = sum(1 for i in items if not i.is_present)

    return TimesheetOut(
        id=ts.id, placement_id=ts.placement_id,
        year=ts.year, month=ts.month,
        workdays_count=ts.workdays_count, status=ts.status,
        submitted_at=ts.submitted_at, approved_at=ts.approved_at,
        created_at=ts.created_at, updated_at=ts.updated_at,
        period_label=f"{MONTHS_ID[ts.month - 1]} {ts.year}",
        placement_employee_nik=pl_row.emp_nik if pl_row else None,
        placement_employee_name=pl_row.emp_name if pl_row else None,
        placement_client_code=pl_row.cli_code if pl_row else None,
        placement_client_name=pl_row.cli_name if pl_row else None,
        placement_role=pl_row.role if pl_row else None,
        items=items_out,
        present_count=present_count,
        absent_count=absent_count,
    )


@router.get("/timesheets", response_model=list[TimesheetOut])
async def list_timesheets_endpoint(
    session: DBSession,
    placement_id: UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
    year: int | None = None,
    month: int | None = None,
    _user=Depends(require_permission("employee.view")),
) -> list[TimesheetOut]:
    items = await service.list_timesheets(
        session, placement_id=placement_id, status_filter=status_filter,
        year=year, month=month,
    )
    return [await _ts_to_out(session, ts) for ts in items]


@router.get("/timesheets/{ts_id}", response_model=TimesheetOut)
async def get_timesheet_endpoint(
    ts_id: UUID, session: DBSession,
    _user=Depends(require_permission("employee.view")),
) -> TimesheetOut:
    try:
        ts = await service.get_timesheet(session, ts_id)
    except TimesheetNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    return await _ts_to_out(session, ts, include_items=True)


@router.post(
    "/timesheets", response_model=TimesheetOut, status_code=status.HTTP_201_CREATED,
)
async def create_timesheet_endpoint(
    request: Request, data: TimesheetCreate, session: DBSession,
    user=Depends(require_permission("employee.edit")),
) -> TimesheetOut:
    try:
        ts = await service.create_timesheet(session, data.placement_id, data.year, data.month)
    except DuplicateTimesheetError as e:
        raise HTTPException(status_code=409, detail={"code": "DUPLICATE", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="TIMESHEET_CREATED",
        resource_type="timesheet", resource_id=str(ts.id),
        ip_address=request.client.host if request.client else None,
        after_state={"placement_id": str(data.placement_id), "year": data.year, "month": data.month},
    )
    return await _ts_to_out(session, ts, include_items=True)


@router.post(
    "/timesheets/{ts_id}/items", response_model=TimesheetItemOut,
)
async def upsert_item_endpoint(
    request: Request, ts_id: UUID, data: TimesheetItemUpsert, session: DBSession,
    user=Depends(require_permission("employee.edit")),
) -> TimesheetItemOut:
    try:
        item = await service.upsert_item(
            session, ts_id, data.work_date, data.is_present, data.notes,
        )
    except TimesheetNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except TimesheetStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="TIMESHEET_ITEM_UPSERT",
        resource_type="timesheet_item", resource_id=str(item.id),
        ip_address=request.client.host if request.client else None,
        after_state={"work_date": str(data.work_date), "is_present": data.is_present},
    )
    return TimesheetItemOut(
        id=item.id, timesheet_id=item.timesheet_id,
        work_date=item.work_date, is_present=item.is_present, notes=item.notes,
    )


@router.delete(
    "/timesheets/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_item_endpoint(
    request: Request, item_id: UUID, session: DBSession,
    user=Depends(require_permission("employee.edit")),
) -> None:
    try:
        await service.delete_item(session, item_id)
    except TimesheetStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="TIMESHEET_ITEM_DELETED",
        resource_type="timesheet_item", resource_id=str(item_id),
        ip_address=request.client.host if request.client else None,
    )


@router.post("/timesheets/{ts_id}/submit", response_model=TimesheetOut)
async def submit_timesheet_endpoint(
    request: Request, ts_id: UUID, session: DBSession,
    user=Depends(require_permission("employee.edit")),
) -> TimesheetOut:
    try:
        ts = await service.submit_timesheet(session, ts_id)
    except TimesheetNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except TimesheetStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="TIMESHEET_SUBMITTED",
        resource_type="timesheet", resource_id=str(ts.id),
        ip_address=request.client.host if request.client else None,
        after_state={"workdays_count": ts.workdays_count},
    )
    return await _ts_to_out(session, ts, include_items=True)


@router.post("/timesheets/{ts_id}/approve", response_model=TimesheetOut)
async def approve_timesheet_endpoint(
    request: Request, ts_id: UUID, data: TimesheetApprove, session: DBSession,
    user=Depends(require_permission("employee.edit")),
) -> TimesheetOut:
    try:
        ts = await service.approve_timesheet(session, ts_id)
    except TimesheetNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except TimesheetStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="TIMESHEET_APPROVED",
        resource_type="timesheet", resource_id=str(ts.id),
        ip_address=request.client.host if request.client else None,
        after_state={"notes": data.notes, "workdays_count": ts.workdays_count},
    )
    return await _ts_to_out(session, ts, include_items=True)


@router.post("/timesheets/{ts_id}/reject", response_model=TimesheetOut)
async def reject_timesheet_endpoint(
    request: Request, ts_id: UUID, data: TimesheetReject, session: DBSession,
    user=Depends(require_permission("employee.edit")),
) -> TimesheetOut:
    try:
        ts = await service.reject_timesheet(session, ts_id)
    except TimesheetNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except TimesheetStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="TIMESHEET_REJECTED",
        resource_type="timesheet", resource_id=str(ts.id),
        ip_address=request.client.host if request.client else None,
        after_state={"rejection_reason": data.rejection_reason},
    )
    return await _ts_to_out(session, ts, include_items=True)


# ─── Berita Acara endpoints (TSK-105) ─────────────────────────────


async def _ba_to_out(session, ba, include_download_url: bool = False) -> BeritaAcaraOut:
    # Fetch timesheet → placement → employee → client untuk derived fields
    ts = await session.get(Timesheet, ba.timesheet_id)
    period_label = None
    employee_name = None
    client_name = None
    if ts:
        period_label = f"{MONTHS_ID[ts.month - 1]} {ts.year}"
        placement = await session.get(OutsourcePlacement, ts.placement_id)
        if placement:
            employee = await session.get(Employee, placement.employee_id)
            client = await session.get(ClientModel, placement.client_id)
            if employee:
                employee_name = employee.full_name
            if client:
                client_name = client.name

    download_url = None
    if include_download_url and ba.pdf_url:
        try:
            download_url = get_presigned_url(ba.pdf_url, expires_in_seconds=3600)
        except Exception:
            download_url = None

    return BeritaAcaraOut(
        id=ba.id, timesheet_id=ba.timesheet_id, ba_no=ba.ba_no,
        pdf_url=ba.pdf_url, signed_by_ide=ba.signed_by_ide,
        signed_by_client=ba.signed_by_client, client_signed_at=ba.client_signed_at,
        created_at=ba.created_at,
        timesheet_period_label=period_label,
        employee_name=employee_name, client_name=client_name,
        download_url=download_url,
    )


@router.post(
    "/timesheets/{ts_id}/generate-ba",
    response_model=BeritaAcaraOut,
    status_code=status.HTTP_201_CREATED,
)
async def generate_ba_endpoint(
    request: Request, ts_id: UUID, session: DBSession,
    user=Depends(require_permission("employee.edit")),
) -> BeritaAcaraOut:
    """Generate BA PDF from approved timesheet. Idempotent (max 1 BA per ts)."""
    try:
        ba = await service.generate_ba(session, ts_id)
    except TimesheetNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except BAStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail={"code": "PDF_GEN_FAILED", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="BA_GENERATED",
        resource_type="berita_acara", resource_id=str(ba.id),
        ip_address=request.client.host if request.client else None,
        after_state={"ba_no": ba.ba_no, "timesheet_id": str(ts_id)},
    )
    return await _ba_to_out(session, ba, include_download_url=True)


@router.get(
    "/timesheets/{ts_id}/ba",
    response_model=BeritaAcaraOut,
)
async def get_ba_for_timesheet_endpoint(
    ts_id: UUID, session: DBSession,
    _user=Depends(require_permission("employee.view")),
) -> BeritaAcaraOut:
    """Get BA for a timesheet (if generated)."""
    ba = await service.get_ba_by_timesheet(session, ts_id)
    if ba is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_GENERATED", "message": "BA belum di-generate"})
    return await _ba_to_out(session, ba, include_download_url=True)


@router.get(
    "/ba/{ba_id}/download-url",
)
async def get_ba_download_url_endpoint(
    ba_id: UUID, session: DBSession,
    expires_in: int = 3600,
    _user=Depends(require_permission("employee.view")),
) -> dict:
    """Presigned URL untuk download BA PDF."""
    try:
        ba = await service.get_ba(session, ba_id)
    except BANotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    if not ba.pdf_url:
        raise HTTPException(status_code=400, detail={"code": "NO_PDF", "message": "PDF belum di-generate"})
    url = get_presigned_url(ba.pdf_url, expires_in_seconds=expires_in)
    return {"url": url, "expires_in_seconds": expires_in}


@router.post("/ba/{ba_id}/regenerate", response_model=BeritaAcaraOut)
async def regenerate_ba_endpoint(
    request: Request, ba_id: UUID, session: DBSession,
    user=Depends(require_permission("employee.edit")),
) -> BeritaAcaraOut:
    """Regenerate PDF (e.g. setelah data correction)."""
    try:
        ba = await service.regenerate_ba_pdf(session, ba_id)
    except BANotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail={"code": "PDF_GEN_FAILED", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="BA_REGENERATED",
        resource_type="berita_acara", resource_id=str(ba.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _ba_to_out(session, ba, include_download_url=True)


# ─── Client Complaint endpoints (TSK-148) ─────────────────────────


async def _complaint_to_out(session, c) -> ClientComplaintOut:
    placement = await session.get(OutsourcePlacement, c.placement_id)
    emp_nik = emp_name = cli_code = cli_name = role = None
    if placement:
        e = await session.get(Employee, placement.employee_id)
        cl = await session.get(ClientModel, placement.client_id)
        if e:
            emp_nik = e.nik
            emp_name = e.full_name
        if cl:
            cli_code = cl.code
            cli_name = cl.name
        role = placement.role_at_client

    logged_nik = None
    if c.logged_by_user_id:
        from app.identity.models import User
        r = await session.execute(select(User.nik).where(User.id == c.logged_by_user_id))
        logged_nik = r.scalar_one_or_none()

    spo_cnt = await service.count_spo_for_complaint(session, c.id)

    return ClientComplaintOut(
        id=c.id, placement_id=c.placement_id,
        complaint_date=c.complaint_date, severity=c.severity,
        description=c.description, logged_by_user_id=c.logged_by_user_id,
        resolved_at=c.resolved_at, created_at=c.created_at,
        placement_employee_nik=emp_nik, placement_employee_name=emp_name,
        placement_client_code=cli_code, placement_client_name=cli_name,
        placement_role=role, logged_by_nik=logged_nik,
        spo_count=spo_cnt,
    )


@router.get("/complaints", response_model=list[ClientComplaintOut])
async def list_complaints_endpoint(
    session: DBSession,
    placement_id: UUID | None = None,
    resolved: bool | None = None,
    _user=Depends(require_permission("employee.view")),
) -> list[ClientComplaintOut]:
    complaints = await service.list_complaints(
        session, placement_id=placement_id, resolved=resolved,
    )
    return [await _complaint_to_out(session, c) for c in complaints]


@router.post(
    "/complaints", response_model=ClientComplaintOut, status_code=status.HTTP_201_CREATED,
)
async def create_complaint_endpoint(
    request: Request, data: ClientComplaintCreate, session: DBSession,
    user=Depends(require_permission("employee.edit")),
) -> ClientComplaintOut:
    c = await service.create_complaint(
        session,
        placement_id=data.placement_id,
        complaint_date=data.complaint_date,
        severity=data.severity,
        description=data.description,
        logged_by_user_id=user.id,
    )
    await audit_log(
        session=session, actor=user, action="CLIENT_COMPLAINT_LOGGED",
        resource_type="client_complaint", resource_id=str(c.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "placement_id": str(data.placement_id),
            "severity": data.severity,
            "complaint_date": str(data.complaint_date),
        },
    )
    return await _complaint_to_out(session, c)


@router.post("/complaints/{comp_id}/resolve", response_model=ClientComplaintOut)
async def resolve_complaint_endpoint(
    request: Request, comp_id: UUID, session: DBSession,
    user=Depends(require_permission("employee.edit")),
) -> ClientComplaintOut:
    try:
        c = await service.resolve_complaint(session, comp_id)
    except ComplaintNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="CLIENT_COMPLAINT_RESOLVED",
        resource_type="client_complaint", resource_id=str(c.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _complaint_to_out(session, c)


# ─── SP-O endpoints (TSK-148) ─────────────────────────────────────


async def _spo_to_out(session, spo) -> SpoOut:
    placement = await session.get(OutsourcePlacement, spo.placement_id)
    emp_nik = emp_name = cli_code = cli_name = role = None
    if placement:
        e = await session.get(Employee, placement.employee_id)
        cl = await session.get(ClientModel, placement.client_id)
        if e:
            emp_nik = e.nik
            emp_name = e.full_name
        if cl:
            cli_code = cl.code
            cli_name = cl.name
        role = placement.role_at_client

    comp_sev = comp_desc = None
    if spo.triggered_by_complaint_id:
        from app.outsource.models import ClientComplaint
        comp = await session.get(ClientComplaint, spo.triggered_by_complaint_id)
        if comp:
            comp_sev = comp.severity
            comp_desc = comp.description[:200] if comp.description else None

    level_value = spo.level.value if hasattr(spo.level, "value") else str(spo.level)

    return SpoOut(
        id=spo.id, placement_id=spo.placement_id, level=level_value,
        issued_date=spo.issued_date,
        triggered_by_complaint_id=spo.triggered_by_complaint_id,
        reason=spo.reason, evaluation_end_date=spo.evaluation_end_date,
        triggers_replacement=spo.triggers_replacement,
        created_at=spo.created_at,
        placement_employee_nik=emp_nik, placement_employee_name=emp_name,
        placement_client_code=cli_code, placement_client_name=cli_name,
        placement_role=role,
        complaint_severity=comp_sev, complaint_description=comp_desc,
    )


@router.get("/spo", response_model=list[SpoOut])
async def list_spo_endpoint(
    session: DBSession,
    placement_id: UUID | None = None,
    complaint_id: UUID | None = None,
    _user=Depends(require_permission("employee.view")),
) -> list[SpoOut]:
    spos = await service.list_spos(
        session, placement_id=placement_id, complaint_id=complaint_id,
    )
    return [await _spo_to_out(session, s) for s in spos]


@router.post("/spo", response_model=SpoOut, status_code=status.HTTP_201_CREATED)
async def create_spo_endpoint(
    request: Request, data: SpoCreate, session: DBSession,
    user=Depends(require_permission("employee.edit")),
) -> SpoOut:
    """Auto-assign level: SP-O1 → SP-O2 → SP-O3.
    SP-O3 triggers replacement flag. After SP-O3, must replace karyawan
    sebelum SP-O baru bisa di-issue."""
    try:
        spo = await service.create_spo(
            session,
            placement_id=data.placement_id,
            triggered_by_complaint_id=data.triggered_by_complaint_id,
            issued_date=data.issued_date,
            reason=data.reason,
        )
    except SpoStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    level_value = spo.level.value if hasattr(spo.level, "value") else str(spo.level)
    await audit_log(
        session=session, actor=user, action="SPO_ISSUED",
        resource_type="warning_letter_outsource", resource_id=str(spo.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "level": level_value,
            "placement_id": str(spo.placement_id),
            "triggers_replacement": spo.triggers_replacement,
        },
    )
    return await _spo_to_out(session, spo)


# ─── Contract Alerts (TSK-106) ────────────────────────────────────


@router.get("/placements-expiring")
async def placements_expiring_endpoint(
    session: DBSession,
    days: int = 30,
    _user=Depends(require_permission("employee.view")),
) -> dict:
    """Active placements ending within N days. Used for sidebar badge + alerts.

    Returns:
      {
        h7_count: int,    # expiring in <=7 days
        h30_count: int,   # expiring in <=30 days (includes h7)
        items: [{ placement_id, employee_nik, name, client_code, end_date,
                  days_until_end, severity }]
      }
    """
    placements = await service.list_expiring_placements(session, days_window=days)
    today = _date.today()

    h7_count = 0
    h30_count = 0
    items = []
    for p in placements:
        days_left = (p.end_date - today).days if p.end_date else 0
        emp_nik, emp_name = await _lookup_employee(session, p.employee_id)
        cli_code, _ = await _lookup_client(session, p.client_id)
        severity = "h7" if days_left <= 7 else "h30"
        if severity == "h7":
            h7_count += 1
        h30_count += 1
        items.append({
            "placement_id": str(p.id),
            "employee_nik": emp_nik,
            "employee_name": emp_name,
            "client_code": cli_code,
            "role": p.role_at_client,
            "end_date": p.end_date.isoformat() if p.end_date else None,
            "days_until_end": days_left,
            "severity": severity,
        })
    return {
        "h7_count": h7_count,
        "h30_count": h30_count,
        "items": items,
    }


# ─── Placement Amendment / Renewal (TSK-107) ──────────────────────


async def _amendment_to_out(session, a) -> PlacementAmendmentOut:
    nik = None
    if a.created_by_user_id:
        from app.identity.models import User
        r = await session.execute(select(User.nik).where(User.id == a.created_by_user_id))
        nik = r.scalar_one_or_none()

    download_url = None
    if a.document_url:
        try:
            download_url = get_presigned_url(a.document_url, expires_in_seconds=3600)
        except Exception:
            download_url = None

    return PlacementAmendmentOut(
        id=a.id, placement_id=a.placement_id, amendment_no=a.amendment_no,
        effective_date=a.effective_date,
        old_end_date=a.old_end_date, old_billing_rate=a.old_billing_rate,
        new_end_date=a.new_end_date, new_billing_rate=a.new_billing_rate,
        document_url=a.document_url, notes=a.notes,
        created_by_user_id=a.created_by_user_id, created_at=a.created_at,
        created_by_nik=nik, download_url=download_url,
    )


@router.post("/placements/{placement_id}/renew", response_model=PlacementAmendmentOut)
async def renew_placement_endpoint(
    request: Request, placement_id: UUID, data: PlacementRenewRequest,
    session: DBSession,
    user=Depends(require_permission("employee.edit")),
) -> PlacementAmendmentOut:
    """Snapshot current rate/end_date + apply new values. Returns amendment record."""
    try:
        _, amendment = await service.renew_placement(
            session, placement_id,
            effective_date=data.effective_date,
            new_end_date=data.new_end_date,
            new_billing_rate=data.new_billing_rate,
            document_url=data.document_url,
            notes=data.notes,
            created_by_user_id=user.id,
        )
    except PlacementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except PlacementAmendmentError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="PLACEMENT_RENEWED",
        resource_type="placement_amendment", resource_id=str(amendment.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "amendment_no": amendment.amendment_no,
            "new_end_date": str(amendment.new_end_date) if amendment.new_end_date else None,
            "new_billing_rate": float(amendment.new_billing_rate) if amendment.new_billing_rate else None,
        },
    )
    return await _amendment_to_out(session, amendment)


@router.get("/placements/{placement_id}/amendments", response_model=list[PlacementAmendmentOut])
async def list_amendments_endpoint(
    placement_id: UUID, session: DBSession,
    _user=Depends(require_permission("employee.view")),
) -> list[PlacementAmendmentOut]:
    items = await service.list_amendments(session, placement_id)
    return [await _amendment_to_out(session, a) for a in items]


# ─── Client KPI Assessment (TSK-108) ──────────────────────────────


async def _kpi_to_out(session, kpi, include_token: bool = False) -> ClientKpiOut:
    placement = await session.get(OutsourcePlacement, kpi.placement_id)
    emp_nik = emp_name = cli_code = cli_name = role = None
    if placement:
        e = await session.get(Employee, placement.employee_id)
        cl = await session.get(ClientModel, placement.client_id)
        if e:
            emp_nik = e.nik
            emp_name = e.full_name
        if cl:
            cli_code = cl.code
            cli_name = cl.name
        role = placement.role_at_client

    return ClientKpiOut(
        id=kpi.id, placement_id=kpi.placement_id,
        assessment_period=kpi.assessment_period,
        token=kpi.token if include_token else None,
        token_expires_at=kpi.token_expires_at,
        score_quality=kpi.score_quality,
        score_communication=kpi.score_communication,
        score_attendance=kpi.score_attendance,
        score_professionalism=kpi.score_professionalism,
        score_initiative=kpi.score_initiative,
        overall_score=kpi.overall_score,
        feedback=kpi.feedback,
        sent_at=kpi.sent_at, submitted_at=kpi.submitted_at,
        created_at=kpi.created_at,
        placement_employee_nik=emp_nik, placement_employee_name=emp_name,
        placement_client_code=cli_code, placement_client_name=cli_name,
        placement_role=role,
        is_expired=service.is_kpi_expired(kpi),
    )


@router.get("/kpi", response_model=list[ClientKpiOut])
async def list_kpi_endpoint(
    session: DBSession,
    placement_id: UUID | None = None,
    client_id: UUID | None = None,
    submitted: bool | None = None,
    _user=Depends(require_permission("employee.view")),
) -> list[ClientKpiOut]:
    items = await service.list_kpi_assessments(
        session, placement_id=placement_id, client_id=client_id, submitted=submitted,
    )
    return [await _kpi_to_out(session, k, include_token=True) for k in items]


@router.post("/kpi", response_model=ClientKpiOut, status_code=status.HTTP_201_CREATED)
async def create_kpi_endpoint(
    request: Request, data: ClientKpiCreate, session: DBSession,
    user=Depends(require_permission("employee.edit")),
) -> ClientKpiOut:
    """Operation creates KPI request → token URL untuk dikirim ke client PIC."""
    try:
        kpi = await service.create_kpi_request(
            session,
            placement_id=data.placement_id,
            assessment_period=data.assessment_period,
            expires_in_days=data.expires_in_days,
            created_by_user_id=user.id,
        )
    except PlacementNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="CLIENT_KPI_REQUESTED",
        resource_type="client_kpi_assessment", resource_id=str(kpi.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "placement_id": str(data.placement_id),
            "assessment_period": data.assessment_period,
            "expires_at": str(kpi.token_expires_at),
        },
    )
    return await _kpi_to_out(session, kpi, include_token=True)


# ─── Public KPI endpoints (NO AUTH) ───────────────────────────────


public_router = APIRouter(tags=["public-client-kpi"], prefix="/public/client-kpi")


@public_router.get("/{token}", response_model=PublicKpiContext)
async def public_kpi_context_endpoint(
    token: str, session: DBSession,
) -> PublicKpiContext:
    """Get KPI context (employee + client) untuk display sebelum submit."""
    try:
        kpi = await service.get_kpi_by_token(session, token)
    except KpiNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "INVALID_TOKEN", "message": str(e)}) from e

    placement = await session.get(OutsourcePlacement, kpi.placement_id)
    emp_name = cli_name = role = None
    if placement:
        e = await session.get(Employee, placement.employee_id)
        cl = await session.get(ClientModel, placement.client_id)
        if e:
            emp_name = e.full_name
        if cl:
            cli_name = cl.name
        role = placement.role_at_client

    return PublicKpiContext(
        assessment_period=kpi.assessment_period,
        employee_name=emp_name,
        client_name=cli_name,
        role=role,
        expires_at=kpi.token_expires_at,
        is_submitted=kpi.submitted_at is not None,
    )


@public_router.post("/{token}/submit", response_model=PublicKpiContext)
async def public_kpi_submit_endpoint(
    token: str, data: ClientKpiSubmit, session: DBSession,
) -> PublicKpiContext:
    """Client submits ratings via token (no auth)."""
    try:
        kpi = await service.submit_kpi(
            session, token,
            scores={
                "score_quality": data.score_quality,
                "score_communication": data.score_communication,
                "score_attendance": data.score_attendance,
                "score_professionalism": data.score_professionalism,
                "score_initiative": data.score_initiative,
            },
            feedback=data.feedback,
        )
    except KpiNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "INVALID_TOKEN", "message": str(e)}) from e
    except KpiStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    placement = await session.get(OutsourcePlacement, kpi.placement_id)
    emp_name = cli_name = role = None
    if placement:
        e = await session.get(Employee, placement.employee_id)
        cl = await session.get(ClientModel, placement.client_id)
        if e:
            emp_name = e.full_name
        if cl:
            cli_name = cl.name
        role = placement.role_at_client

    return PublicKpiContext(
        assessment_period=kpi.assessment_period,
        employee_name=emp_name,
        client_name=cli_name,
        role=role,
        expires_at=kpi.token_expires_at,
        is_submitted=True,
    )


# ─── Client Dashboard (TSK-109) ───────────────────────────────────


@router.get("/clients/{client_id}/dashboard")
async def client_dashboard_endpoint(
    client_id: UUID, session: DBSession,
    _user=Depends(require_permission("employee.view")),
) -> dict:
    """Aggregate view per client: placements, contracts, KPI, billing."""
    try:
        data = await service.get_client_dashboard(session, client_id)
    except ClientNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e

    placements_out = [await _placement_to_out(session, p) for p in data["placements"]]

    return {
        "client": await _client_to_out(session, data["client"]),
        "placement_count": data["placement_count"],
        "active_count": data["active_count"],
        "expiring_30d": data["expiring_30d"],
        "kpi_count": data["kpi_count"],
        "kpi_avg_overall": data["kpi_avg_overall"],
        "monthly_billing_estimate": data["monthly_billing_estimate"],
        "placements": placements_out,
    }
