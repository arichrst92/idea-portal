"""Sales router — TSK-024.

Endpoints di /api/v1:
- /leads                              — list, create
- /leads/{id}                         — get, patch
- /leads/{id}/transition              — pindah stage (auto-create commission saat WON)
- /leads/{id}/activities              — list, log
- /leads/{id}/proposals               — list, create
- /sales-pipeline                     — kanban view (all leads grouped by stage)
- /sales-proposals/{id}/send          — DRAFT → SENT
- /sales-commissions                  — list (filter by user_id, status)
- /sales-commissions/{id}/mark-paid   — link ke payroll period
- /sales-targets                      — list, create
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.core.audit import audit_log
from app.core.deps import CurrentUser, DBSession, require_permission
from app.identity.models import User
from app.organization.models import Department
from app.sales import service
from app.sales.models import LeadStage
from app.sales.schemas import (
    ActivityCreate,
    ActivityOut,
    CommissionOut,
    LeadCreate,
    LeadListItem,
    LeadOut,
    LeadStageTransition,
    LeadUpdate,
    PipelineResponse,
    PipelineStageBucket,
    ProposalCreate,
    ProposalItemOut,
    ProposalOut,
    TargetCreate,
    TargetOut,
)
from app.sales.service import (
    DuplicateProposalError,
    InvalidStageTransitionError,
    InvalidStateError,
    LeadNotFoundError,
    ProposalNotFoundError,
)

router = APIRouter(tags=["sales"])


# ─── Helpers ───────────────────────────────────────────────────────


_STAGE_LABELS: dict[LeadStage, str] = {
    LeadStage.PROSPECT: "Prospect",
    LeadStage.QUALIFIED: "Qualified",
    LeadStage.PROPOSAL: "Proposal Sent",
    LeadStage.NEGOTIATION: "Negotiation",
    LeadStage.CLOSED_WON: "Closed Won",
    LeadStage.CLOSED_LOST: "Closed Lost",
}


async def _lookup_user_nik(session, user_id: UUID | None) -> str | None:
    if user_id is None:
        return None
    r = await session.execute(select(User.nik).where(User.id == user_id))
    return r.scalar_one_or_none()


async def _build_lead_out(session, lead) -> LeadOut:
    nik = await _lookup_user_nik(session, lead.assigned_to_user_id)
    activity_count = await service.count_activities(session, lead.id)
    proposal_count = await service.count_proposals(session, lead.id)
    return LeadOut(
        id=lead.id,
        company_name=lead.company_name,
        pic_name=lead.pic_name,
        pic_email=lead.pic_email,
        pic_phone=lead.pic_phone,
        services=lead.services,
        stage=lead.stage,
        estimated_value=lead.estimated_value,
        currency=lead.currency,
        source=lead.source,
        assigned_to_user_id=lead.assigned_to_user_id,
        referred_by_user_id=lead.referred_by_user_id,
        is_direktur_driven=lead.is_direktur_driven,
        closed_at=lead.closed_at,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
        assigned_to_nik=nik,
        days_in_stage=service.days_in_stage(lead),
        activity_count=activity_count,
        proposal_count=proposal_count,
    )


async def _build_lead_list(session, lead) -> LeadListItem:
    nik = await _lookup_user_nik(session, lead.assigned_to_user_id)
    return LeadListItem(
        id=lead.id,
        company_name=lead.company_name,
        pic_name=lead.pic_name,
        stage=lead.stage,
        estimated_value=lead.estimated_value,
        currency=lead.currency,
        assigned_to_nik=nik,
        is_direktur_driven=lead.is_direktur_driven,
        days_in_stage=service.days_in_stage(lead),
        created_at=lead.created_at,
    )


# ─── Lead endpoints ───────────────────────────────────────────────


@router.get("/leads", response_model=list[LeadListItem])
async def list_leads_endpoint(
    session: DBSession,
    _user=Depends(require_permission("lead.view")),
    stage: str | None = Query(None),
    assigned_to_user_id: UUID | None = Query(None),
) -> list[LeadListItem]:
    stage_enum = LeadStage(stage) if stage else None
    leads, _total = await service.list_leads(
        session, stage=stage_enum, assigned_to_user_id=assigned_to_user_id, page_size=200
    )
    return [await _build_lead_list(session, lead) for lead in leads]


@router.post("/leads", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
async def create_lead_endpoint(
    request: Request,
    data: LeadCreate,
    session: DBSession,
    user=Depends(require_permission("lead.create")),
) -> LeadOut:
    lead = await service.create_lead(session, data)
    await audit_log(
        session=session,
        actor=user,
        action="LEAD_CREATED",
        resource_type="lead",
        resource_id=str(lead.id),
        ip_address=request.client.host if request.client else None,
        after_state={"company": lead.company_name, "estimated_value": float(lead.estimated_value or 0)},
    )
    return await _build_lead_out(session, lead)


@router.get("/leads/{lead_id}", response_model=LeadOut)
async def get_lead_endpoint(
    lead_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("lead.view")),
) -> LeadOut:
    try:
        lead = await service.get_lead(session, lead_id)
    except LeadNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    return await _build_lead_out(session, lead)


@router.patch("/leads/{lead_id}", response_model=LeadOut)
async def update_lead_endpoint(
    request: Request,
    lead_id: UUID,
    data: LeadUpdate,
    session: DBSession,
    user=Depends(require_permission("lead.edit")),
) -> LeadOut:
    try:
        lead = await service.update_lead(session, lead_id, data)
    except LeadNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="LEAD_UPDATED",
        resource_type="lead", resource_id=str(lead.id),
        ip_address=request.client.host if request.client else None,
    )
    return await _build_lead_out(session, lead)


@router.post("/leads/{lead_id}/transition", response_model=LeadOut)
async def transition_lead_endpoint(
    request: Request,
    lead_id: UUID,
    data: LeadStageTransition,
    session: DBSession,
    user=Depends(require_permission("lead.edit")),
) -> LeadOut:
    try:
        lead, commission = await service.transition_stage(session, lead_id, data)
    except LeadNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except (InvalidStageTransitionError, InvalidStateError) as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user,
        action=f"LEAD_STAGE_{data.new_stage.value}",
        resource_type="lead", resource_id=str(lead.id),
        ip_address=request.client.host if request.client else None,
        after_state={
            "new_stage": data.new_stage.value,
            "commission_created": str(commission.id) if commission else None,
        },
    )
    return await _build_lead_out(session, lead)


# ─── Activity endpoints ───────────────────────────────────────────


@router.get("/leads/{lead_id}/activities", response_model=list[ActivityOut])
async def list_activities_endpoint(
    lead_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("lead.view")),
) -> list[ActivityOut]:
    activities = await service.list_activities(session, lead_id)
    out = []
    for a in activities:
        nik = await _lookup_user_nik(session, a.logged_by_user_id)
        out.append(
            ActivityOut(
                id=a.id, lead_id=a.lead_id, activity_date=a.activity_date,
                activity_type=a.activity_type, notes=a.notes,
                logged_by_user_id=a.logged_by_user_id,
                created_at=a.created_at, logged_by_nik=nik,
            )
        )
    return out


@router.post(
    "/leads/{lead_id}/activities",
    response_model=ActivityOut,
    status_code=status.HTTP_201_CREATED,
)
async def log_activity_endpoint(
    request: Request,
    lead_id: UUID,
    data: ActivityCreate,
    session: DBSession,
    user=Depends(require_permission("lead.edit")),
) -> ActivityOut:
    try:
        activity = await service.log_activity(session, lead_id, data, user.id)
    except LeadNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="LEAD_ACTIVITY_LOGGED",
        resource_type="lead_activity", resource_id=str(activity.id),
        ip_address=request.client.host if request.client else None,
        after_state={"type": data.activity_type, "lead_id": str(lead_id)},
    )
    return ActivityOut(
        id=activity.id, lead_id=activity.lead_id, activity_date=activity.activity_date,
        activity_type=activity.activity_type, notes=activity.notes,
        logged_by_user_id=activity.logged_by_user_id,
        created_at=activity.created_at,
        logged_by_nik=await _lookup_user_nik(session, activity.logged_by_user_id),
    )


# ─── Proposal endpoints ──────────────────────────────────────────


@router.get("/leads/{lead_id}/proposals", response_model=list[ProposalOut])
async def list_proposals_endpoint(
    lead_id: UUID,
    session: DBSession,
    _user=Depends(require_permission("proposal.create")),
) -> list[ProposalOut]:
    proposals = await service.list_proposals(session, lead_id)
    out = []
    for p in proposals:
        items = await service.get_proposal_items(session, p.id)
        out.append(
            ProposalOut(
                id=p.id, lead_id=p.lead_id, proposal_no=p.proposal_no,
                version=p.version, total_value=p.total_value, pdf_url=p.pdf_url,
                status=p.status, approved_by_user_id=p.approved_by_user_id,
                sent_at=p.sent_at, created_at=p.created_at,
                items=[ProposalItemOut.model_validate(i) for i in items],
            )
        )
    return out


@router.post(
    "/leads/{lead_id}/proposals",
    response_model=ProposalOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_proposal_endpoint(
    request: Request,
    lead_id: UUID,
    data: ProposalCreate,
    session: DBSession,
    user=Depends(require_permission("proposal.create")),
) -> ProposalOut:
    try:
        p = await service.create_proposal(session, lead_id, data)
    except LeadNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except DuplicateProposalError as e:
        raise HTTPException(status_code=409, detail={"code": "DUPLICATE", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="PROPOSAL_CREATED",
        resource_type="proposal", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
        after_state={"proposal_no": p.proposal_no, "total": float(p.total_value)},
    )
    items = await service.get_proposal_items(session, p.id)
    return ProposalOut(
        id=p.id, lead_id=p.lead_id, proposal_no=p.proposal_no,
        version=p.version, total_value=p.total_value, pdf_url=p.pdf_url,
        status=p.status, approved_by_user_id=p.approved_by_user_id,
        sent_at=p.sent_at, created_at=p.created_at,
        items=[ProposalItemOut.model_validate(i) for i in items],
    )


@router.post("/sales-proposals/{proposal_id}/send", response_model=ProposalOut)
async def send_proposal_endpoint(
    request: Request,
    proposal_id: UUID,
    session: DBSession,
    user=Depends(require_permission("proposal.approve")),
) -> ProposalOut:
    try:
        p = await service.send_proposal(session, proposal_id)
    except ProposalNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)}) from e
    except InvalidStateError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)}) from e

    await audit_log(
        session=session, actor=user, action="PROPOSAL_SENT",
        resource_type="proposal", resource_id=str(p.id),
        ip_address=request.client.host if request.client else None,
    )
    items = await service.get_proposal_items(session, p.id)
    return ProposalOut(
        id=p.id, lead_id=p.lead_id, proposal_no=p.proposal_no,
        version=p.version, total_value=p.total_value, pdf_url=p.pdf_url,
        status=p.status, approved_by_user_id=p.approved_by_user_id,
        sent_at=p.sent_at, created_at=p.created_at,
        items=[ProposalItemOut.model_validate(i) for i in items],
    )


# ─── Pipeline endpoint ────────────────────────────────────────────


@router.get("/sales-pipeline", response_model=PipelineResponse)
async def pipeline_endpoint(
    session: DBSession,
    _user=Depends(require_permission("lead.view")),
) -> PipelineResponse:
    data = await service.build_pipeline(session)
    stages = []
    for stage in LeadStage:
        bucket = data["buckets"][stage]
        leads_out = [await _build_lead_list(session, lead) for lead in bucket]
        stages.append(
            PipelineStageBucket(
                stage=stage,
                label=_STAGE_LABELS[stage],
                count=len(bucket),
                total_value=sum((lead.estimated_value or Decimal("0")) for lead in bucket),
                leads=leads_out,
            )
        )
    return PipelineResponse(
        stages=stages,
        total_leads=data["total_leads"],
        total_pipeline_value=data["total_pipeline_value"],
        closed_won_value_ytd=data["closed_won_ytd"],
    )


# ─── Commission endpoints ────────────────────────────────────────


@router.get("/sales-commissions", response_model=list[CommissionOut])
async def list_commissions_endpoint(
    session: DBSession,
    _user=Depends(require_permission("lead.view")),
    sales_user_id: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
) -> list[CommissionOut]:
    commissions = await service.list_commissions(session, sales_user_id, status_filter)
    out = []
    for c in commissions:
        sales_nik = await _lookup_user_nik(session, c.sales_user_id)
        lead = await service.get_lead(session, c.lead_id)
        out.append(
            CommissionOut(
                id=c.id, lead_id=c.lead_id, sales_user_id=c.sales_user_id,
                commission_pct=c.commission_pct, commission_amount=c.commission_amount,
                target_payroll_period_id=c.target_payroll_period_id,
                status=c.status, created_at=c.created_at,
                sales_nik=sales_nik, lead_company=lead.company_name,
            )
        )
    return out


# ─── Sales Target endpoints ──────────────────────────────────────


@router.get("/sales-targets", response_model=list[TargetOut])
async def list_targets_endpoint(
    session: DBSession,
    _user=Depends(require_permission("lead.view")),
    year: int | None = Query(None),
    user_id: UUID | None = Query(None),
) -> list[TargetOut]:
    targets = await service.list_targets(session, year, user_id)
    out = []
    for t in targets:
        user_nik = await _lookup_user_nik(session, t.user_id)
        dept_name = None
        if t.department_id:
            r = await session.execute(select(Department.name).where(Department.id == t.department_id))
            dept_name = r.scalar_one_or_none()
        achieved = await service.calculate_target_achievement(session, t)
        pct = (achieved / t.target_amount * Decimal("100")) if t.target_amount > 0 else Decimal("0")
        out.append(
            TargetOut(
                id=t.id, user_id=t.user_id, department_id=t.department_id,
                year=t.year, month=t.month, target_amount=t.target_amount,
                currency=t.currency, user_nik=user_nik, department_name=dept_name,
                achieved_amount=achieved, achievement_pct=pct,
            )
        )
    return out


@router.post(
    "/sales-targets", response_model=TargetOut, status_code=status.HTTP_201_CREATED
)
async def create_target_endpoint(
    request: Request,
    data: TargetCreate,
    session: DBSession,
    user=Depends(require_permission("sales_target.configure")),
) -> TargetOut:
    target = await service.create_target(session, data)
    await audit_log(
        session=session, actor=user, action="SALES_TARGET_CREATED",
        resource_type="sales_target", resource_id=str(target.id),
        ip_address=request.client.host if request.client else None,
    )
    user_nik = await _lookup_user_nik(session, target.user_id)
    dept_name = None
    if target.department_id:
        r = await session.execute(select(Department.name).where(Department.id == target.department_id))
        dept_name = r.scalar_one_or_none()
    return TargetOut(
        id=target.id, user_id=target.user_id, department_id=target.department_id,
        year=target.year, month=target.month, target_amount=target.target_amount,
        currency=target.currency, user_nik=user_nik, department_name=dept_name,
        achieved_amount=Decimal("0"), achievement_pct=Decimal("0"),
    )
