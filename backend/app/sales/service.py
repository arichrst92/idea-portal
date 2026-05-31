"""Sales business logic — TSK-024.

Lead lifecycle (knowledge.md sec.7):
PROSPECT → QUALIFIED → PROPOSAL → NEGOTIATION → CLOSED_WON / CLOSED_LOST

Commission rule:
- CLOSED_WON dengan is_direktur_driven=False → auto-create SalesCommission
  for assigned_to_user_id, status=PENDING
- CLOSED_WON dengan is_direktur_driven=True → no commission

Proposal:
- Versioning manual via proposal_no + version (mis. PROP-001 v1.0, v1.1, v2.0)
- total_value = sum(items.subtotal)
- status: DRAFT → SENT → ACCEPTED / REJECTED / REVISED
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.sales.models import (
    Lead,
    LeadActivity,
    LeadStage,
    Proposal,
    ProposalItem,
    SalesActionItem,
    SalesCommission,
    SalesTarget,
)
from app.sales.schemas import (
    ActivityCreate,
    LeadCreate,
    LeadStageTransition,
    LeadUpdate,
    ProposalCreate,
    TargetCreate,
)


# ─── Exceptions ────────────────────────────────────────────────────


class LeadNotFoundError(Exception):
    pass


class ProposalNotFoundError(Exception):
    pass


class InvalidStageTransitionError(Exception):
    pass


class InvalidStateError(Exception):
    pass


class DuplicateProposalError(Exception):
    pass


# ─── Stage transition rules ────────────────────────────────────────


_STAGE_FLOW: dict[LeadStage, set[LeadStage]] = {
    LeadStage.PROSPECT: {LeadStage.QUALIFIED, LeadStage.CLOSED_LOST},
    LeadStage.QUALIFIED: {LeadStage.PROPOSAL, LeadStage.CLOSED_LOST},
    LeadStage.PROPOSAL: {LeadStage.NEGOTIATION, LeadStage.CLOSED_LOST, LeadStage.CLOSED_WON},
    LeadStage.NEGOTIATION: {LeadStage.CLOSED_WON, LeadStage.CLOSED_LOST, LeadStage.PROPOSAL},
    LeadStage.CLOSED_WON: set(),
    LeadStage.CLOSED_LOST: set(),
}


# ─── Lead CRUD ─────────────────────────────────────────────────────


async def get_lead(session: AsyncSession, lead_id: UUID) -> Lead:
    stmt = select(Lead).where(Lead.id == lead_id, Lead.deleted_at.is_(None))
    result = await session.execute(stmt)
    lead = result.scalar_one_or_none()
    if lead is None:
        raise LeadNotFoundError(f"Lead {lead_id} not found")
    return lead


async def list_leads(
    session: AsyncSession,
    stage: LeadStage | None = None,
    assigned_to_user_id: UUID | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Lead], int]:
    page = max(page, 1)
    page_size = max(min(page_size, 200), 1)

    base = select(Lead).where(Lead.deleted_at.is_(None))
    if stage is not None:
        base = base.where(Lead.stage == stage)
    if assigned_to_user_id is not None:
        base = base.where(Lead.assigned_to_user_id == assigned_to_user_id)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    stmt = (
        base.order_by(Lead.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def create_lead(session: AsyncSession, data: LeadCreate) -> Lead:
    lead = Lead(
        **data.model_dump(),
        stage=LeadStage.PROSPECT,
    )
    session.add(lead)
    await session.commit()
    await session.refresh(lead)
    return lead


async def update_lead(
    session: AsyncSession, lead_id: UUID, data: LeadUpdate
) -> Lead:
    lead = await get_lead(session, lead_id)
    if lead.stage in {LeadStage.CLOSED_WON, LeadStage.CLOSED_LOST}:
        raise InvalidStateError(
            f"Lead status {lead.stage} — sudah closed, tidak bisa edit (kecuali via reopen)"
        )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    await session.commit()
    await session.refresh(lead)
    return lead


async def transition_stage(
    session: AsyncSession,
    lead_id: UUID,
    data: LeadStageTransition,
) -> tuple[Lead, SalesCommission | None]:
    """Pindahkan lead stage. Returns (lead, commission_jika_dibuat).

    Auto-create SalesCommission saat:
    - new_stage == CLOSED_WON
    - lead.is_direktur_driven == False
    - lead.assigned_to_user_id != None
    - commission_pct provided
    """
    lead = await get_lead(session, lead_id)

    allowed = _STAGE_FLOW.get(lead.stage, set())
    if data.new_stage not in allowed:
        raise InvalidStageTransitionError(
            f"Tidak boleh transisi {lead.stage} → {data.new_stage}. "
            f"Allowed: {sorted(s.value for s in allowed)}"
        )

    lead.stage = data.new_stage
    if data.new_stage in {LeadStage.CLOSED_WON, LeadStage.CLOSED_LOST}:
        lead.closed_at = date.today()

    commission: SalesCommission | None = None
    if (
        data.new_stage == LeadStage.CLOSED_WON
        and not lead.is_direktur_driven
        and lead.assigned_to_user_id is not None
    ):
        if data.commission_pct is None:
            raise InvalidStateError(
                "commission_pct wajib untuk CLOSED_WON non-direktur-driven"
            )
        if lead.estimated_value is None:
            raise InvalidStateError(
                "Lead belum punya estimated_value — tidak bisa hitung commission"
            )
        commission_amount = (lead.estimated_value * data.commission_pct) / Decimal("100")
        commission = SalesCommission(
            lead_id=lead.id,
            sales_user_id=lead.assigned_to_user_id,
            commission_pct=data.commission_pct,
            commission_amount=commission_amount,
            status="PENDING",
        )
        session.add(commission)
        await session.flush()  # supaya commission.id ada

        # TSK-194: try inject ke active slip kalau ada
        # (active = period status DRAFT/REVIEWING dengan slip ke sales user)
        await _try_inject_commission_to_active_slip(session, commission)

    await session.commit()
    await session.refresh(lead)
    if commission:
        await session.refresh(commission)
    return lead, commission


async def _try_inject_commission_to_active_slip(
    session: AsyncSession, commission: "SalesCommission"
) -> bool:
    """Best-effort: kalau ada active slip (period DRAFT/REVIEWING) untuk
    sales user, langsung tambah PayrollComponent INCOME + update slip totals
    + mark commission APPLIED. Returns True kalau injected.
    """
    from app.identity.models import User
    from app.payroll.models import (
        PayrollComponent, PayrollPeriod, PayrollSlip,
    )

    # User → Employee via Employee.user_id (User tidak punya employee_id direct)
    from app.organization.models import Employee as _Emp
    emp_stmt = select(_Emp.id).where(_Emp.user_id == commission.sales_user_id)
    employee_id = (await session.execute(emp_stmt)).scalar_one_or_none()
    if employee_id is None:
        return False

    # Active period (DRAFT or REVIEWING)
    period_stmt = (
        select(PayrollPeriod)
        .where(PayrollPeriod.status.in_(["DRAFT", "REVIEWING"]))
        .order_by(PayrollPeriod.year.desc(), PayrollPeriod.month.desc())
        .limit(1)
    )
    period = (await session.execute(period_stmt)).scalar_one_or_none()
    if period is None:
        return False  # No active period, akan di-apply di next generate_slips

    # Slip untuk employee ini di period tersebut
    slip_stmt = select(PayrollSlip).where(
        PayrollSlip.employee_id == employee_id,
        PayrollSlip.period_id == period.id,
    )
    slip = (await session.execute(slip_stmt)).scalar_one_or_none()
    if slip is None:
        return False  # No slip yet, akan di-apply di next generate_slips

    # Inject component
    amount = Decimal(str(commission.commission_amount))
    component = PayrollComponent(
        slip_id=slip.id,
        code=f"SALES_COMMISSION_{str(commission.lead_id)[:8]}",
        name="Komisi Sales (Closed Won)",
        component_type="INCOME",
        is_variable=True,
        amount=amount,
        source_reference=f"sales_commission:{commission.id}",
    )
    session.add(component)
    slip.gross_income = Decimal(str(slip.gross_income)) + amount
    slip.take_home_pay = Decimal(str(slip.gross_income)) - Decimal(str(slip.total_deductions))

    commission.target_payroll_period_id = period.id
    commission.status = "APPLIED"
    return True


# ─── Lead Activity ─────────────────────────────────────────────────


async def list_activities(
    session: AsyncSession, lead_id: UUID
) -> list[LeadActivity]:
    stmt = (
        select(LeadActivity)
        .where(LeadActivity.lead_id == lead_id)
        .order_by(LeadActivity.activity_date.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_activities(session: AsyncSession, lead_id: UUID) -> int:
    stmt = select(func.count(LeadActivity.id)).where(LeadActivity.lead_id == lead_id)
    return int((await session.execute(stmt)).scalar_one())


async def log_activity(
    session: AsyncSession,
    lead_id: UUID,
    data: ActivityCreate,
    logged_by_user_id: UUID,
) -> LeadActivity:
    await get_lead(session, lead_id)  # validate
    activity = LeadActivity(
        lead_id=lead_id,
        activity_date=data.activity_date,
        activity_type=data.activity_type,
        notes=data.notes,
        logged_by_user_id=logged_by_user_id,
    )
    session.add(activity)
    await session.commit()
    await session.refresh(activity)
    return activity


# ─── Proposal CRUD ─────────────────────────────────────────────────


async def list_proposals(
    session: AsyncSession, lead_id: UUID
) -> list[Proposal]:
    stmt = (
        select(Proposal)
        .where(Proposal.lead_id == lead_id, Proposal.deleted_at.is_(None))
        .order_by(Proposal.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_proposals(session: AsyncSession, lead_id: UUID) -> int:
    stmt = select(func.count(Proposal.id)).where(
        Proposal.lead_id == lead_id, Proposal.deleted_at.is_(None)
    )
    return int((await session.execute(stmt)).scalar_one())


async def get_proposal_items(
    session: AsyncSession, proposal_id: UUID
) -> list[ProposalItem]:
    stmt = select(ProposalItem).where(ProposalItem.proposal_id == proposal_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_proposal(
    session: AsyncSession, lead_id: UUID, data: ProposalCreate
) -> Proposal:
    await get_lead(session, lead_id)

    total = sum((i.quantity * i.unit_price for i in data.items), Decimal("0"))
    proposal = Proposal(
        lead_id=lead_id,
        proposal_no=data.proposal_no,
        version=data.version,
        total_value=total,
        pdf_url=data.pdf_url,
        status="DRAFT",
    )
    session.add(proposal)
    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        if "proposals_proposal_no_key" in str(e):
            raise DuplicateProposalError(
                f"Proposal no '{data.proposal_no}' sudah ada"
            ) from e
        raise

    for item_spec in data.items:
        item = ProposalItem(
            proposal_id=proposal.id,
            description=item_spec.description,
            quantity=item_spec.quantity,
            unit_price=item_spec.unit_price,
            subtotal=item_spec.quantity * item_spec.unit_price,
        )
        session.add(item)

    await session.commit()
    await session.refresh(proposal)
    return proposal


async def send_proposal(session: AsyncSession, proposal_id: UUID) -> Proposal:
    stmt = select(Proposal).where(
        Proposal.id == proposal_id, Proposal.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    p = result.scalar_one_or_none()
    if p is None:
        raise ProposalNotFoundError(f"Proposal {proposal_id} not found")
    if p.status != "DRAFT":
        raise InvalidStateError(f"Proposal status {p.status} — hanya DRAFT yang bisa di-send")
    p.status = "SENT"
    p.sent_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(p)
    return p


# ─── Commission ────────────────────────────────────────────────────


async def list_commissions(
    session: AsyncSession,
    sales_user_id: UUID | None = None,
    status_filter: str | None = None,
) -> list[SalesCommission]:
    stmt = select(SalesCommission)
    if sales_user_id is not None:
        stmt = stmt.where(SalesCommission.sales_user_id == sales_user_id)
    if status_filter is not None:
        stmt = stmt.where(SalesCommission.status == status_filter)
    stmt = stmt.order_by(SalesCommission.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def mark_commission_paid(
    session: AsyncSession, commission_id: UUID, payroll_period_id: UUID
) -> SalesCommission:
    stmt = select(SalesCommission).where(SalesCommission.id == commission_id)
    result = await session.execute(stmt)
    c = result.scalar_one_or_none()
    if c is None:
        raise InvalidStateError(f"Commission {commission_id} not found")
    c.status = "PAID"
    c.target_payroll_period_id = payroll_period_id
    await session.commit()
    await session.refresh(c)
    return c


# ─── Pipeline view ─────────────────────────────────────────────────


async def build_pipeline(session: AsyncSession) -> dict:
    """Group all leads by stage untuk kanban view."""
    leads, _ = await list_leads(session, page_size=500)

    buckets: dict[LeadStage, list[Lead]] = {stage: [] for stage in LeadStage}
    for lead in leads:
        buckets[lead.stage].append(lead)

    total_pipeline = sum(
        (lead.estimated_value or Decimal("0"))
        for lead in leads
        if lead.stage not in {LeadStage.CLOSED_WON, LeadStage.CLOSED_LOST}
    )

    closed_won_ytd = sum(
        (lead.estimated_value or Decimal("0"))
        for lead in leads
        if lead.stage == LeadStage.CLOSED_WON
        and lead.closed_at is not None
        and lead.closed_at.year == date.today().year
    )

    return {
        "buckets": buckets,
        "total_leads": len(leads),
        "total_pipeline_value": total_pipeline,
        "closed_won_ytd": closed_won_ytd,
    }


# ─── SalesTarget ───────────────────────────────────────────────────


async def list_targets(
    session: AsyncSession,
    year: int | None = None,
    user_id: UUID | None = None,
) -> list[SalesTarget]:
    stmt = select(SalesTarget)
    if year is not None:
        stmt = stmt.where(SalesTarget.year == year)
    if user_id is not None:
        stmt = stmt.where(SalesTarget.user_id == user_id)
    stmt = stmt.order_by(SalesTarget.year.desc(), SalesTarget.month.desc().nulls_last())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_target(
    session: AsyncSession, data: TargetCreate
) -> SalesTarget:
    target = SalesTarget(**data.model_dump())
    session.add(target)
    await session.commit()
    await session.refresh(target)
    return target


async def calculate_target_achievement(
    session: AsyncSession, target: SalesTarget
) -> Decimal:
    """Hitung total closed_won value yang match target scope."""
    stmt = select(func.sum(Lead.estimated_value)).where(
        Lead.stage == LeadStage.CLOSED_WON,
        func.extract("year", Lead.closed_at) == target.year,
    )
    if target.month:
        stmt = stmt.where(func.extract("month", Lead.closed_at) == target.month)
    if target.user_id:
        stmt = stmt.where(Lead.assigned_to_user_id == target.user_id)

    result = await session.execute(stmt)
    total = result.scalar_one_or_none()
    return Decimal(str(total)) if total is not None else Decimal("0")


# ─── Helpers ───────────────────────────────────────────────────────


def calc_total_pages(total: int, page_size: int) -> int:
    if total == 0:
        return 0
    return math.ceil(total / page_size)


def days_in_stage(lead: Lead) -> int:
    """Approximation: days since last update."""
    delta = datetime.now(UTC).date() - lead.updated_at.date()
    return delta.days
