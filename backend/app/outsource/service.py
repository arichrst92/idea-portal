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
