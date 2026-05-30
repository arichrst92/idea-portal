"""Outsource placement business logic — TSK-100."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.outsource.models import BillingType, Client, OutsourcePlacement
from app.outsource.schemas import (
    ClientCreate,
    PlacementCreate,
    PlacementUpdate,
)


class PlacementNotFoundError(Exception):
    pass


class ClientNotFoundError(Exception):
    pass


class DuplicateClientCodeError(Exception):
    pass


# ─── Placement ──────────────────────────────────────────────────────


async def list_placements(
    session: AsyncSession,
    client_id: UUID | None = None,
    employee_id: UUID | None = None,
    is_active: bool | None = None,
) -> list[OutsourcePlacement]:
    stmt = select(OutsourcePlacement).where(
        OutsourcePlacement.deleted_at.is_(None)
    )
    if client_id is not None:
        stmt = stmt.where(OutsourcePlacement.client_id == client_id)
    if employee_id is not None:
        stmt = stmt.where(OutsourcePlacement.employee_id == employee_id)
    if is_active is not None:
        stmt = stmt.where(OutsourcePlacement.is_active == is_active)
    stmt = stmt.order_by(OutsourcePlacement.start_date.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_placement(session: AsyncSession, placement_id: UUID) -> OutsourcePlacement:
    stmt = select(OutsourcePlacement).where(
        OutsourcePlacement.id == placement_id,
        OutsourcePlacement.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    p = result.scalar_one_or_none()
    if p is None:
        raise PlacementNotFoundError(f"Placement {placement_id} not found")
    return p


async def create_placement(
    session: AsyncSession, data: PlacementCreate
) -> OutsourcePlacement:
    p = OutsourcePlacement(
        employee_id=data.employee_id,
        client_id=data.client_id,
        role_at_client=data.role_at_client,
        start_date=data.start_date,
        end_date=data.end_date,
        billing_type=data.billing_type,
        billing_rate=data.billing_rate,
        is_active=True,
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


async def update_placement(
    session: AsyncSession, placement_id: UUID, data: PlacementUpdate
) -> OutsourcePlacement:
    p = await get_placement(session, placement_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    await session.commit()
    await session.refresh(p)
    return p


async def soft_delete_placement(session: AsyncSession, placement_id: UUID) -> None:
    p = await get_placement(session, placement_id)
    p.deleted_at = datetime.now(UTC)
    await session.commit()


def compute_monthly_billing(p: OutsourcePlacement) -> Decimal:
    """Estimasi billing per bulan.

    FLAT_MONTHLY: pakai rate as-is.
    PER_DAY: rate × 22 work days (estimate).
    """
    rate = Decimal(str(p.billing_rate))
    if p.billing_type == BillingType.FLAT_MONTHLY:
        return rate
    elif p.billing_type == BillingType.PER_WORKDAY:
        return rate * Decimal("22")
    return Decimal("0")


# ─── Client ─────────────────────────────────────────────────────────


async def list_clients(
    session: AsyncSession, is_active: bool | None = None
) -> list[Client]:
    stmt = select(Client).where(Client.deleted_at.is_(None))
    if is_active is not None:
        stmt = stmt.where(Client.is_active == is_active)
    stmt = stmt.order_by(Client.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_client(session: AsyncSession, client_id: UUID) -> Client:
    stmt = select(Client).where(
        Client.id == client_id, Client.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    c = result.scalar_one_or_none()
    if c is None:
        raise ClientNotFoundError(f"Client {client_id} not found")
    return c


async def create_client(
    session: AsyncSession, data: ClientCreate
) -> Client:
    c = Client(
        code=data.code,
        name=data.name,
        pic_name=data.pic_name,
        pic_email=data.pic_email,
        pic_phone=data.pic_phone,
        address=data.address,
        is_active=True,
    )
    session.add(c)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        if "clients_code_key" in str(e):
            raise DuplicateClientCodeError(f"Client code '{data.code}' sudah ada") from e
        raise
    await session.refresh(c)
    return c


async def count_placements_for_client(
    session: AsyncSession, client_id: UUID, active_only: bool = False
) -> int:
    stmt = select(func.count(OutsourcePlacement.id)).where(
        OutsourcePlacement.client_id == client_id,
        OutsourcePlacement.deleted_at.is_(None),
    )
    if active_only:
        stmt = stmt.where(OutsourcePlacement.is_active.is_(True))
    return int((await session.execute(stmt)).scalar_one())


def days_until_end(p: OutsourcePlacement) -> int | None:
    if p.end_date is None:
        return None
    return (p.end_date - date.today()).days


def duration_days(p: OutsourcePlacement) -> int:
    end = p.end_date or date.today()
    return (end - p.start_date).days


# ─── Timesheet (TSK-103+104) ───────────────────────────────────────


from app.outsource.models import Timesheet, TimesheetItem  # noqa: E402


class TimesheetNotFoundError(Exception):
    pass


class TimesheetStateError(Exception):
    pass


class DuplicateTimesheetError(Exception):
    pass


async def list_timesheets(
    session: AsyncSession,
    placement_id: UUID | None = None,
    status_filter: str | None = None,
    year: int | None = None,
    month: int | None = None,
) -> list[Timesheet]:
    stmt = select(Timesheet)
    if placement_id is not None:
        stmt = stmt.where(Timesheet.placement_id == placement_id)
    if status_filter is not None:
        stmt = stmt.where(Timesheet.status == status_filter)
    if year is not None:
        stmt = stmt.where(Timesheet.year == year)
    if month is not None:
        stmt = stmt.where(Timesheet.month == month)
    stmt = stmt.order_by(Timesheet.year.desc(), Timesheet.month.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_timesheet(session: AsyncSession, ts_id: UUID) -> Timesheet:
    stmt = select(Timesheet).where(Timesheet.id == ts_id)
    result = await session.execute(stmt)
    ts = result.scalar_one_or_none()
    if ts is None:
        raise TimesheetNotFoundError(f"Timesheet {ts_id} not found")
    return ts


async def get_timesheet_items(
    session: AsyncSession, ts_id: UUID
) -> list[TimesheetItem]:
    stmt = (
        select(TimesheetItem)
        .where(TimesheetItem.timesheet_id == ts_id)
        .order_by(TimesheetItem.work_date)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_timesheet(
    session: AsyncSession, placement_id: UUID, year: int, month: int
) -> Timesheet:
    """Check uniqueness placement+year+month."""
    existing_stmt = select(Timesheet).where(
        Timesheet.placement_id == placement_id,
        Timesheet.year == year,
        Timesheet.month == month,
    )
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()
    if existing is not None:
        raise DuplicateTimesheetError(
            f"Timesheet untuk placement+{year}-{month:02d} sudah ada"
        )

    ts = Timesheet(
        placement_id=placement_id,
        year=year, month=month,
        workdays_count=0, status="DRAFT",
    )
    session.add(ts)
    await session.commit()
    await session.refresh(ts)
    return ts


async def upsert_item(
    session: AsyncSession,
    ts_id: UUID,
    work_date: date,
    is_present: bool,
    notes: str | None,
) -> TimesheetItem:
    ts = await get_timesheet(session, ts_id)
    if ts.status not in ("DRAFT", "REJECTED"):
        raise TimesheetStateError(
            f"Tidak bisa edit items kalau status {ts.status}"
        )
    # Upsert
    stmt = select(TimesheetItem).where(
        TimesheetItem.timesheet_id == ts_id,
        TimesheetItem.work_date == work_date,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is None:
        item = TimesheetItem(
            timesheet_id=ts_id, work_date=work_date,
            is_present=is_present, notes=notes,
        )
        session.add(item)
    else:
        existing.is_present = is_present
        existing.notes = notes
        item = existing

    # Recompute workdays_count
    cnt_stmt = select(func.count(TimesheetItem.id)).where(
        TimesheetItem.timesheet_id == ts_id,
        TimesheetItem.is_present.is_(True),
    )
    # Need to commit changes first then recount
    await session.flush()
    cnt = int((await session.execute(cnt_stmt)).scalar_one())
    ts.workdays_count = cnt

    await session.commit()
    await session.refresh(item)
    return item


async def delete_item(
    session: AsyncSession, item_id: UUID
) -> None:
    stmt = select(TimesheetItem).where(TimesheetItem.id == item_id)
    item = (await session.execute(stmt)).scalar_one_or_none()
    if item is None:
        return
    ts = await get_timesheet(session, item.timesheet_id)
    if ts.status not in ("DRAFT", "REJECTED"):
        raise TimesheetStateError(
            f"Tidak bisa hapus item kalau status {ts.status}"
        )
    await session.delete(item)
    # Recount
    cnt_stmt = select(func.count(TimesheetItem.id)).where(
        TimesheetItem.timesheet_id == ts.id,
        TimesheetItem.is_present.is_(True),
    )
    await session.flush()
    ts.workdays_count = int((await session.execute(cnt_stmt)).scalar_one())
    await session.commit()


async def submit_timesheet(session: AsyncSession, ts_id: UUID) -> Timesheet:
    """DRAFT/REJECTED → SUBMITTED."""
    ts = await get_timesheet(session, ts_id)
    if ts.status not in ("DRAFT", "REJECTED"):
        raise TimesheetStateError(
            f"Hanya DRAFT/REJECTED bisa submit, current: {ts.status}"
        )
    ts.status = "SUBMITTED"
    ts.submitted_at = date.today()
    await session.commit()
    await session.refresh(ts)
    return ts


async def approve_timesheet(session: AsyncSession, ts_id: UUID) -> Timesheet:
    """SUBMITTED → APPROVED."""
    ts = await get_timesheet(session, ts_id)
    if ts.status != "SUBMITTED":
        raise TimesheetStateError(
            f"Hanya SUBMITTED bisa approve, current: {ts.status}"
        )
    ts.status = "APPROVED"
    ts.approved_at = date.today()
    await session.commit()
    await session.refresh(ts)
    return ts


async def reject_timesheet(session: AsyncSession, ts_id: UUID) -> Timesheet:
    """SUBMITTED → REJECTED (back to employee)."""
    ts = await get_timesheet(session, ts_id)
    if ts.status != "SUBMITTED":
        raise TimesheetStateError(
            f"Hanya SUBMITTED bisa reject, current: {ts.status}"
        )
    ts.status = "REJECTED"
    ts.submitted_at = None  # Reset supaya bisa re-submit
    await session.commit()
    await session.refresh(ts)
    return ts


# ─── Berita Acara (TSK-105) ────────────────────────────────────────


from app.outsource.models import BeritaAcara  # noqa: E402


class BAStateError(Exception):
    pass


class BANotFoundError(Exception):
    pass


async def get_ba_by_timesheet(
    session: AsyncSession, ts_id: UUID
) -> BeritaAcara | None:
    stmt = select(BeritaAcara).where(BeritaAcara.timesheet_id == ts_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_ba(session: AsyncSession, ba_id: UUID) -> BeritaAcara:
    stmt = select(BeritaAcara).where(BeritaAcara.id == ba_id)
    ba = (await session.execute(stmt)).scalar_one_or_none()
    if ba is None:
        raise BANotFoundError(f"BA {ba_id} not found")
    return ba


async def _next_ba_number(session: AsyncSession) -> str:
    """Generate BA number: BA-{YYYY}-{counter}."""
    year = date.today().year
    cnt_stmt = select(func.count(BeritaAcara.id))
    cnt = int((await session.execute(cnt_stmt)).scalar_one())
    return f"BA-{year}-{cnt + 1:04d}"


async def generate_ba(
    session: AsyncSession, ts_id: UUID
) -> BeritaAcara:
    """Generate BA PDF dari approved timesheet.

    Rules:
    - Timesheet harus status APPROVED.
    - Maks 1 BA per timesheet (kalau sudah ada, return existing).
    """
    from app.outsource.ba_generator import generate_ba_pdf

    ts = await get_timesheet(session, ts_id)
    if ts.status != "APPROVED":
        raise BAStateError(
            f"Hanya timesheet APPROVED bisa generate BA, current: {ts.status}"
        )

    existing = await get_ba_by_timesheet(session, ts_id)
    if existing is not None:
        return existing

    ba_no = await _next_ba_number(session)
    object_name = await generate_ba_pdf(session, ts_id, ba_no)

    ba = BeritaAcara(
        timesheet_id=ts_id,
        ba_no=ba_no,
        pdf_url=object_name,
        signed_by_ide=True,  # Auto-signed by IDE saat generate
        signed_by_client=False,
    )
    session.add(ba)
    await session.commit()
    await session.refresh(ba)
    return ba


async def regenerate_ba_pdf(
    session: AsyncSession, ba_id: UUID
) -> BeritaAcara:
    """Regenerate PDF (e.g. after data correction).

    BA tetap, hanya overwrite PDF di MinIO.
    """
    from app.outsource.ba_generator import generate_ba_pdf

    ba = await get_ba(session, ba_id)
    object_name = await generate_ba_pdf(session, ba.timesheet_id, ba.ba_no)
    ba.pdf_url = object_name
    await session.commit()
    await session.refresh(ba)
    return ba
