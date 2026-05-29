"""Finance/Invoice business logic — TSK-022C."""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.finance.models import Invoice, InvoiceStatus
from app.finance.schemas import InvoiceCreate, InvoiceUpdate


# ─── Exceptions ────────────────────────────────────────────────────


class InvoiceNotFoundError(Exception):
    pass


class DuplicateInvoiceError(Exception):
    pass


# ─── CRUD ──────────────────────────────────────────────────────────


async def list_invoices(
    session: AsyncSession,
    project_id: UUID | None = None,
    status_filter: InvoiceStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Invoice], int]:
    base = select(Invoice).where(Invoice.deleted_at.is_(None))
    if project_id is not None:
        base = base.where(Invoice.project_id == project_id)
    if status_filter is not None:
        base = base.where(Invoice.status == status_filter)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    stmt = (
        base.order_by(Invoice.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_invoice(session: AsyncSession, invoice_id: UUID) -> Invoice:
    stmt = select(Invoice).where(
        Invoice.id == invoice_id, Invoice.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    inv = result.scalar_one_or_none()
    if inv is None:
        raise InvoiceNotFoundError(f"Invoice {invoice_id} not found")
    return inv


def _compute_tax_and_total(amount: Decimal, tax_pct: Decimal) -> tuple[Decimal, Decimal]:
    tax_amount = (amount * tax_pct / Decimal("100")).quantize(Decimal("0.01"))
    total = amount + tax_amount
    return tax_amount, total


async def create_invoice(session: AsyncSession, data: InvoiceCreate) -> Invoice:
    tax_amount, total = _compute_tax_and_total(data.amount, data.tax_pct)

    inv = Invoice(
        invoice_no=data.invoice_no,
        project_id=data.project_id,
        trigger_phase_id=data.trigger_phase_id,
        client_id=data.client_id,
        client_name_snapshot=data.client_name_snapshot,
        termin_pct=data.termin_pct,
        amount=data.amount,
        currency=data.currency,
        tax_pct=data.tax_pct,
        tax_amount=tax_amount,
        total_amount=total,
        issue_date=data.issue_date,
        due_date=data.due_date,
        notes=data.notes,
        status=InvoiceStatus.PENDING,
        paid_amount=Decimal("0"),
    )
    session.add(inv)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        if "invoices_invoice_no_key" in str(e):
            raise DuplicateInvoiceError(f"Invoice no '{data.invoice_no}' sudah ada") from e
        raise
    await session.refresh(inv)
    return inv


async def update_invoice(
    session: AsyncSession, invoice_id: UUID, data: InvoiceUpdate
) -> Invoice:
    inv = await get_invoice(session, invoice_id)
    payload = data.model_dump(exclude_unset=True)

    if "paid_amount" in payload and payload["paid_amount"] is not None:
        new_paid = Decimal(str(payload["paid_amount"]))
        if new_paid > Decimal(str(inv.total_amount)):
            raise ValueError("paid_amount tidak boleh melebihi total_amount")
        inv.paid_amount = new_paid
        # Auto status transition
        if new_paid >= Decimal(str(inv.total_amount)):
            inv.status = InvoiceStatus.PAID
            if inv.paid_at is None:
                inv.paid_at = date.today()
        elif new_paid > Decimal("0"):
            inv.status = InvoiceStatus.PARTIAL

    if "status" in payload and payload["status"] is not None:
        inv.status = payload["status"]
    if "paid_at" in payload:
        inv.paid_at = payload["paid_at"]
    if "due_date" in payload:
        inv.due_date = payload["due_date"]
    if "notes" in payload:
        inv.notes = payload["notes"]

    await session.commit()
    await session.refresh(inv)
    return inv


async def soft_delete_invoice(session: AsyncSession, invoice_id: UUID) -> None:
    from datetime import UTC, datetime

    inv = await get_invoice(session, invoice_id)
    inv.deleted_at = datetime.now(UTC)
    await session.commit()


# ─── Phase trigger hook (called from project/service.complete_phase) ─


async def trigger_invoices_on_phase_complete(
    session: AsyncSession, phase_id: UUID
) -> list[Invoice]:
    """Cari invoice yang trigger by phase ini & belum di-notify Finance."""
    stmt = select(Invoice).where(
        Invoice.trigger_phase_id == phase_id,
        Invoice.notified_finance_at.is_(None),
        Invoice.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    invoices = list(result.scalars().all())
    today = date.today()
    for inv in invoices:
        inv.notified_finance_at = today
        if inv.issue_date is None:
            inv.issue_date = today
        if inv.status == InvoiceStatus.PENDING:
            inv.status = InvoiceStatus.SENT
    if invoices:
        await session.commit()
        for inv in invoices:
            await session.refresh(inv)
    return invoices


# ─── Helpers ───────────────────────────────────────────────────────


def calc_total_pages(total: int, page_size: int) -> int:
    if total == 0:
        return 0
    return math.ceil(total / page_size)


def compute_aging_bucket(due_date: date | None, paid: bool) -> tuple[int | None, str | None]:
    """Returns (days_overdue, aging_bucket). Aging bucket:
    CURRENT (not overdue), 1-30, 31-60, 61-90, 90+."""
    if paid:
        return None, "PAID"
    if due_date is None:
        return None, None
    delta = (date.today() - due_date).days
    if delta <= 0:
        return 0, "CURRENT"
    if delta <= 30:
        return delta, "1-30"
    if delta <= 60:
        return delta, "31-60"
    if delta <= 90:
        return delta, "61-90"
    return delta, "90+"
