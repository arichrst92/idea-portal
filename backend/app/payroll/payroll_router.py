"""Payroll router — TSK-046.

Endpoints di /api/v1/payroll:

  /payroll/configs                      — list, upsert (per employee)
  /payroll/configs/{employee_id}        — get active config
  /payroll/configs/{config_id}          — update

  /payroll/periods                      — list, create
  /payroll/periods/{id}                 — get
  /payroll/periods/{id}/generate-slips  — auto-create slips for all active employees
  /payroll/periods/{id}/lock            — final lock

  /payroll/slips                        — list (filter by period/employee)
  /payroll/slips/{id}                   — get with full components
  /payroll/slips/{id}/components        — add variable component (komisi, bonus)
  /payroll/slips/{id}/pph21             — set PPh21 manual
  /payroll/components/{id}              — delete component (kalau period unlocked)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.core.audit import audit_log
from app.core.deps import DBSession, require_permission
from app.organization.models import Employee
from app.payroll import payroll_service as service
from app.payroll.models import PayrollPeriod, PayrollSlip
from app.payroll.payroll_schemas import (
    GenerateSlipsResponse,
    PayrollComponentCreate,
    PayrollComponentOut,
    PayrollConfigCreate,
    PayrollConfigOut,
    PayrollConfigUpdate,
    PayrollPeriodCreate,
    PayrollPeriodOut,
    PayrollSlipOut,
    SetPph21Request,
)
from app.payroll.payroll_service import (
    ConfigNotFoundError,
    DuplicatePeriodError,
    DuplicateSlipError,
    PeriodLockedError,
    PeriodNotFoundError,
    SlipNotFoundError,
)
from app.payroll.pdf_generator import generate_slip_pdf
from app.core.storage import get_presigned_url

router = APIRouter(tags=["payroll"], prefix="/payroll")


# ─── Helpers ───────────────────────────────────────────────────────


MONTHS_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


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
    if row is None:
        return None, None
    return row[0], row[1]


async def _config_to_out(session, c) -> PayrollConfigOut:
    nik, name = await _lookup_employee(session, c.employee_id)
    return PayrollConfigOut(
        id=c.id, employee_id=c.employee_id,
        basic_salary=c.basic_salary, fixed_allowance=c.fixed_allowance,
        bpjs_kesehatan_pct=c.bpjs_kesehatan_pct,
        bpjs_ketenagakerjaan_pct=c.bpjs_ketenagakerjaan_pct,
        effective_date=c.effective_date,
        created_at=c.created_at, updated_at=c.updated_at,
        employee_nik=nik, employee_name=name,
    )


async def _period_to_out(session, p: PayrollPeriod) -> PayrollPeriodOut:
    # Count slips + totals
    from sqlalchemy import func as sa_func

    r = await session.execute(
        select(
            sa_func.count(PayrollSlip.id),
            sa_func.coalesce(sa_func.sum(PayrollSlip.gross_income), 0),
            sa_func.coalesce(sa_func.sum(PayrollSlip.take_home_pay), 0),
        ).where(PayrollSlip.period_id == p.id)
    )
    cnt, gross, take_home = r.one()
    return PayrollPeriodOut(
        id=p.id, year=p.year, month=p.month, pay_date=p.pay_date,
        status=p.status, locked_at=p.locked_at,
        created_at=p.created_at, updated_at=p.updated_at,
        slip_count=int(cnt or 0),
        total_gross=gross,
        total_take_home=take_home,
    )


async def _slip_to_out(session, s: PayrollSlip, include_components: bool = False) -> PayrollSlipOut:
    nik, name = await _lookup_employee(session, s.employee_id)
    # Period label
    pr = await session.get(PayrollPeriod, s.period_id)
    label = f"{MONTHS_ID[pr.month - 1]} {pr.year}" if pr else None
    comps_out = []
    if include_components:
        comps = await service.list_components(session, s.id)
        comps_out = [
            PayrollComponentOut(
                id=c.id, slip_id=c.slip_id, code=c.code, name=c.name,
                component_type=c.component_type, is_variable=c.is_variable,
                amount=c.amount, source_reference=c.source_reference,
                created_at=c.created_at,
            ) for c in comps
        ]
    return PayrollSlipOut(
        id=s.id, employee_id=s.employee_id, period_id=s.period_id,
        slip_no=s.slip_no, gross_income=s.gross_income,
        total_deductions=s.total_deductions, take_home_pay=s.take_home_pay,
        pdf_url=s.pdf_url, published_at=s.published_at,
        created_at=s.created_at, updated_at=s.updated_at,
        employee_nik=nik, employee_name=name, period_label=label,
        components=comps_out,
    )


# ─── PayrollConfig endpoints ──────────────────────────────────────


@router.get("/configs", response_model=list[PayrollConfigOut])
async def list_configs_endpoint(
    session: DBSession,
    employee_id: UUID | None = None,
    _user=Depends(require_permission("payroll.view")),
) -> list[PayrollConfigOut]:
    configs = await service.list_configs(session, employee_id=employee_id)
    return [await _config_to_out(session, c) for c in configs]


@router.get("/configs/active/{employee_id}", response_model=PayrollConfigOut)
async def get_active_config_endpoint(
    employee_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("payroll.view")),
) -> PayrollConfigOut:
    c = await service.get_active_config(session, employee_id)
    if c is None:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Active config tidak ditemukan"}
        )
    return await _config_to_out(session, c)


@router.post("/configs", response_model=PayrollConfigOut, status_code=status.HTTP_201_CREATED)
async def upsert_config_endpoint(
    request: Request,
    data: PayrollConfigCreate,
    session: DBSession,
    user=Depends(require_permission("payroll.create")),
) -> PayrollConfigOut:
    c = await service.upsert_config(session, data)
    await audit_log(
        session=session, actor=user, action="PAYROLL_CONFIG_UPSERT",
        resource_type="payroll_config", resource_id=str(c.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "employee_id": str(c.employee_id),
            "basic_salary": float(c.basic_salary),
            "effective_date": str(c.effective_date),
        },
    )
    return await _config_to_out(session, c)


@router.patch("/configs/{config_id}", response_model=PayrollConfigOut)
async def update_config_endpoint(
    request: Request,
    config_id: UUID,
    data: PayrollConfigUpdate,
    session: DBSession,
    user=Depends(require_permission("payroll.create")),
) -> PayrollConfigOut:
    try:
        c = await service.update_config(session, config_id, data)
    except ConfigNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="PAYROLL_CONFIG_UPDATED",
        resource_type="payroll_config", resource_id=str(c.id),
        ip_address=request.client.host if request.client else None,
        after_state=data.model_dump(exclude_unset=True, mode="json"),
    )
    return await _config_to_out(session, c)


# ─── PayrollPeriod endpoints ──────────────────────────────────────


@router.get("/periods", response_model=list[PayrollPeriodOut])
async def list_periods_endpoint(
    session: DBSession,
    _user=Depends(require_permission("payroll.view")),
) -> list[PayrollPeriodOut]:
    periods = await service.list_periods(session)
    return [await _period_to_out(session, p) for p in periods]


@router.get("/periods/{period_id}", response_model=PayrollPeriodOut)
async def get_period_endpoint(
    period_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("payroll.view")),
) -> PayrollPeriodOut:
    try:
        p = await service.get_period(session, period_id)
    except PeriodNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    return await _period_to_out(session, p)


@router.post("/periods", response_model=PayrollPeriodOut, status_code=status.HTTP_201_CREATED)
async def create_period_endpoint(
    request: Request,
    data: PayrollPeriodCreate,
    session: DBSession,
    user=Depends(require_permission("payroll.create")),
) -> PayrollPeriodOut:
    try:
        p = await service.create_period(session, data)
    except DuplicatePeriodError as e:
        raise HTTPException(status_code=409, detail={"code": "DUPLICATE_PERIOD", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="PAYROLL_PERIOD_CREATED",
        resource_type="payroll_period", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
        after_state={"year": p.year, "month": p.month, "pay_date": str(p.pay_date)},
    )
    return await _period_to_out(session, p)


@router.post(
    "/periods/{period_id}/generate-slips",
    response_model=GenerateSlipsResponse,
)
async def generate_slips_endpoint(
    request: Request,
    period_id: UUID,
    session: DBSession,
    user=Depends(require_permission("payroll.create")),
) -> GenerateSlipsResponse:
    try:
        result = await service.generate_slips_for_period(session, period_id)
    except PeriodNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except PeriodLockedError as e:
        raise HTTPException(status_code=400, detail={"code": "LOCKED", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="PAYROLL_SLIPS_GENERATED",
        resource_type="payroll_period", resource_id=str(period_id),
        ip_address=request.client.host if request.client else None,
        after_state={"generated": result.generated, "skipped": result.skipped},
    )
    return result


@router.post("/periods/{period_id}/lock", response_model=PayrollPeriodOut)
async def lock_period_endpoint(
    request: Request,
    period_id: UUID,
    session: DBSession,
    user=Depends(require_permission("payroll.approve")),
) -> PayrollPeriodOut:
    try:
        p = await service.lock_period(session, period_id)
    except PeriodNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="PAYROLL_PERIOD_LOCKED",
        resource_type="payroll_period", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _period_to_out(session, p)


# ─── Slip endpoints ──────────────────────────────────────────────


@router.get("/slips", response_model=list[PayrollSlipOut])
async def list_slips_endpoint(
    session: DBSession,
    period_id: UUID | None = None,
    employee_id: UUID | None = None,
    _user=Depends(require_permission("payroll.view")),
) -> list[PayrollSlipOut]:
    slips = await service.list_slips(session, period_id=period_id, employee_id=employee_id)
    return [await _slip_to_out(session, s) for s in slips]


@router.get("/slips/{slip_id}", response_model=PayrollSlipOut)
async def get_slip_endpoint(
    slip_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("payroll.view")),
) -> PayrollSlipOut:
    try:
        s = await service.get_slip(session, slip_id)
    except SlipNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    return await _slip_to_out(session, s, include_components=True)


@router.post(
    "/slips/{slip_id}/components",
    response_model=PayrollComponentOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_component_endpoint(
    request: Request,
    slip_id: UUID,
    data: PayrollComponentCreate,
    session: DBSession,
    user=Depends(require_permission("payroll.create")),
) -> PayrollComponentOut:
    try:
        c = await service.add_component(session, slip_id, data)
    except SlipNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except PeriodLockedError as e:
        raise HTTPException(status_code=400, detail={"code": "LOCKED", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="PAYROLL_COMPONENT_ADDED",
        resource_type="payroll_component", resource_id=str(c.id),
        ip_address=request.client.host if request.client else None,
        after_state={"code": c.code, "type": c.component_type, "amount": float(c.amount)},
    )
    return PayrollComponentOut(
        id=c.id, slip_id=c.slip_id, code=c.code, name=c.name,
        component_type=c.component_type, is_variable=c.is_variable,
        amount=c.amount, source_reference=c.source_reference,
        created_at=c.created_at,
    )


@router.post("/slips/{slip_id}/pph21", response_model=PayrollSlipOut)
async def set_pph21_endpoint(
    request: Request,
    slip_id: UUID,
    data: SetPph21Request,
    session: DBSession,
    user=Depends(require_permission("payroll.create")),
) -> PayrollSlipOut:
    try:
        s = await service.set_pph21(session, slip_id, data.pph21_amount)
    except SlipNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except PeriodLockedError as e:
        raise HTTPException(status_code=400, detail={"code": "LOCKED", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="PAYROLL_PPH21_SET",
        resource_type="payroll_slip", resource_id=str(s.id),
        ip_address=request.client.host if request.client else None,
        after_state={"pph21_amount": float(data.pph21_amount)},
    )
    return await _slip_to_out(session, s, include_components=True)


@router.post("/slips/{slip_id}/generate-pdf", response_model=PayrollSlipOut)
async def generate_pdf_endpoint(
    request: Request,
    slip_id: UUID,
    session: DBSession,
    user=Depends(require_permission("payroll.create")),
) -> PayrollSlipOut:
    """Generate PDF, upload ke MinIO, set slip.pdf_url."""
    try:
        s = await service.get_slip(session, slip_id)
    except SlipNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e

    try:
        object_name = await generate_slip_pdf(session, s)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail={"code": "PDF_GEN_FAILED", "message": str(e)}
        ) from e

    s.pdf_url = object_name
    await session.commit()
    await session.refresh(s)

    await audit_log(
        session=session, actor=user, action="PAYROLL_SLIP_PDF_GENERATED",
        resource_type="payroll_slip", resource_id=str(s.id),
        ip_address=request.client.host if request.client else None,
        after_state={"pdf_url": object_name},
    )
    return await _slip_to_out(session, s, include_components=True)


@router.get("/slips/{slip_id}/pdf-url")
async def get_pdf_url_endpoint(
    slip_id: UUID,
    session: DBSession,
    expires_in: int = 3600,
    _user=Depends(require_permission("payroll.view")),
) -> dict:
    """Presigned URL untuk download PDF slip."""
    try:
        s = await service.get_slip(session, slip_id)
    except SlipNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e

    if not s.pdf_url:
        raise HTTPException(
            status_code=400,
            detail={"code": "PDF_NOT_GENERATED", "message": "PDF belum di-generate. Call POST /generate-pdf dulu."},
        )

    url = get_presigned_url(s.pdf_url, expires_in_seconds=expires_in)
    return {"url": url, "expires_in_seconds": expires_in}


@router.delete("/components/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_component_endpoint(
    request: Request,
    component_id: UUID,
    session: DBSession,
    user=Depends(require_permission("payroll.create")),
) -> None:
    try:
        await service.delete_component(session, component_id)
    except SlipNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except PeriodLockedError as e:
        raise HTTPException(status_code=400, detail={"code": "LOCKED", "message": str(e)}) from e
    await audit_log(
        session=session, actor=user, action="PAYROLL_COMPONENT_DELETED",
        resource_type="payroll_component", resource_id=str(component_id),
        ip_address=request.client.host if request.client else None,
    )
