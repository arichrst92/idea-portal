"""Finance domain router — TSK-022C.

Endpoints di /api/v1/finance:
- GET    /finance/invoices                    — list with filter & pagination
- POST   /finance/invoices                    — create invoice
- GET    /finance/invoices/{id}               — detail
- PATCH  /finance/invoices/{id}               — update (status, paid_amount, dll)
- DELETE /finance/invoices/{id}               — soft delete

Catatan: Invoice bisa standalone (ad-hoc) atau di-link ke project (CLIENT type).
Trigger auto-notify Finance terjadi saat Phase di project di-mark complete
(lihat app/project/service.complete_phase yang call
app/finance/service.trigger_invoices_on_phase_complete).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: F401

from app.core.deps import DBSession, require_permission
from app.finance import service
from app.finance.models import InvoiceStatus
from app.finance.schemas import (
    InvoiceCreate,
    InvoiceListResponse,
    InvoiceOut,
    InvoiceUpdate,
)
from app.finance.service import (
    DuplicateInvoiceError,
    InvoiceNotFoundError,
)
from app.core.audit import audit_log

router = APIRouter(tags=["finance"], prefix="/finance")


# ─── Helpers ───────────────────────────────────────────────────────


async def _to_out(session, inv) -> InvoiceOut:
    project_code = None
    project_name = None
    if inv.project_id:
        from app.project.models import Project

        r = await session.execute(
            select(Project.code, Project.name).where(Project.id == inv.project_id)
        )
        row = r.one_or_none()
        if row:
            project_code, project_name = row

    paid_full = Decimal(str(inv.paid_amount)) >= Decimal(str(inv.total_amount))
    days_overdue, aging = service.compute_aging_bucket(inv.due_date, paid_full)

    return InvoiceOut(
        id=inv.id,
        invoice_no=inv.invoice_no,
        project_id=inv.project_id,
        trigger_phase_id=inv.trigger_phase_id,
        client_id=inv.client_id,
        client_name_snapshot=inv.client_name_snapshot,
        termin_pct=inv.termin_pct,
        amount=inv.amount,
        currency=inv.currency,
        tax_pct=inv.tax_pct,
        tax_amount=inv.tax_amount,
        total_amount=inv.total_amount,
        issue_date=inv.issue_date,
        due_date=inv.due_date,
        notified_finance_at=inv.notified_finance_at,
        status=inv.status,
        paid_amount=inv.paid_amount,
        paid_at=inv.paid_at,
        notes=inv.notes,
        created_at=inv.created_at,
        project_code=project_code,
        project_name=project_name,
        days_overdue=days_overdue,
        aging_bucket=aging,
    )


# ─── Endpoints ─────────────────────────────────────────────────────


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices_endpoint(
    session: DBSession,
    project_id: UUID | None = None,
    status_filter: InvoiceStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _user=Depends(require_permission("invoice.view")),
) -> InvoiceListResponse:
    items, total = await service.list_invoices(
        session, project_id=project_id, status_filter=status_filter,
        page=page, page_size=page_size,
    )
    return InvoiceListResponse(
        items=[await _to_out(session, inv) for inv in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=service.calc_total_pages(total, page_size),
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
async def get_invoice_endpoint(
    invoice_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("invoice.view")),
) -> InvoiceOut:
    try:
        inv = await service.get_invoice(session, invoice_id)
    except InvoiceNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    return await _to_out(session, inv)


@router.post("/invoices", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
async def create_invoice_endpoint(
    request: Request,
    data: InvoiceCreate,
    session: DBSession,
    user=Depends(require_permission("invoice.create")),
) -> InvoiceOut:
    try:
        inv = await service.create_invoice(session, data)
    except DuplicateInvoiceError as e:
        raise HTTPException(status_code=409, detail={"code": "DUPLICATE_INVOICE_NO", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="INVOICE_CREATED",
        resource_type="invoice",
        resource_id=str(inv.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "invoice_no": inv.invoice_no,
            "amount": float(inv.amount),
            "project_id": str(inv.project_id) if inv.project_id else None,
        },
    )
    return await _to_out(session, inv)


@router.patch("/invoices/{invoice_id}", response_model=InvoiceOut)
async def update_invoice_endpoint(
    request: Request,
    invoice_id: UUID,
    data: InvoiceUpdate,
    session: DBSession,
    user=Depends(require_permission("invoice.create")),
) -> InvoiceOut:
    try:
        inv = await service.update_invoice(session, invoice_id, data)
    except InvoiceNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID", "message": str(e)}) from e

    await audit_log(
        session=session,
        actor=user,
        action="INVOICE_UPDATED",
        resource_type="invoice",
        resource_id=str(inv.id),
        ip_address=request.client.host if request.client else None,
        after_state=data.model_dump(exclude_unset=True, mode="json"),
    )
    return await _to_out(session, inv)


@router.delete("/invoices/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice_endpoint(
    request: Request,
    invoice_id: UUID,
    session: DBSession,
    user=Depends(require_permission("invoice.create")),
) -> None:
    try:
        await service.soft_delete_invoice(session, invoice_id)
    except InvoiceNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    await audit_log(
        session=session,
        actor=user,
        action="INVOICE_DELETED",
        resource_type="invoice",
        resource_id=str(invoice_id),
        ip_address=request.client.host if request.client else None,
    )
