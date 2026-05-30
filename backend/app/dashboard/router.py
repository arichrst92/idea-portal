"""Dashboard router — TSK-025.

Endpoints di /api/v1:
- /dashboard/overview         — aggregate stats dari semua domain
- /dashboard/employee-stats   — distribusi karyawan
- /dashboard/recent-activity  — recent audit logs untuk timeline widget
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assessment.models import Assessment, AssessmentPeriod, WarningLetter
from app.core.deps import CurrentUser, DBSession, require_permission
from app.hiring.models import JobApplication, JobOpening
from app.identity.models import AuditLog
from app.onboarding.models import OnboardingAssignment
from app.organization.models import Department, Employee, EmployeeContract, EmployeeStatus
from app.payroll.models import (
    LeaveRequest,
    ProcurementRequest,
    Reimbursement,
)
from app.project.models import Project, ProjectStatus
from app.sales.models import Lead, LeadStage, SalesCommission
from app.separation.models import EmployeeSeparation, SeparationStatus

router = APIRouter(tags=["dashboard"], prefix="/dashboard")


# ─── EBITDA endpoint (TSK-151) ─────────────────────────────────────


@router.get("/ebitda")
async def ebitda_endpoint(
    session: DBSession,
    months: int = 12,
    _user=Depends(require_permission("financial_report.view")),
) -> dict[str, Any]:
    """EBITDA per bulan untuk N bulan terakhir.

    Sources:
    - Revenue: Invoice.total_amount yang status PAID (paid_at di bulan tsb)
               + Invoice yang issue_date di bulan tsb (accrual basis).
    - Cost:
      * Payroll: PayrollSlip.gross_income per period
      * Reimbursement: Reimbursement.amount status TRANSFERRED
      * Procurement: ProcurementRequest.actual_amount status DELIVERED
      * Outsource billing (revenue stream terpisah): OutsourcePlacement
        FLAT_MONTHLY rate atau PER_WORKDAY × 22

    EBITDA = Revenue - OpEx (sebelum interest/tax/depreciation/amortization).
    Implementation: D&A diasumsikan 0 untuk MVP.
    """
    from collections import defaultdict
    from datetime import date as _date

    from app.finance.models import Invoice, InvoiceStatus
    from app.payroll.models import PayrollPeriod, PayrollSlip
    from app.payroll.models import Reimbursement, ProcurementRequest
    from app.outsource.models import OutsourcePlacement, BillingType

    today = _date.today()
    # Window: most recent N months
    window = []
    for i in range(months):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        window.append((y, m))
    window.reverse()

    # Build per-month buckets
    rev_invoice: dict[tuple[int, int], float] = defaultdict(float)
    rev_outsource: dict[tuple[int, int], float] = defaultdict(float)
    cost_payroll: dict[tuple[int, int], float] = defaultdict(float)
    cost_reimb: dict[tuple[int, int], float] = defaultdict(float)
    cost_proc: dict[tuple[int, int], float] = defaultdict(float)

    # Revenue from Invoice — accrual basis (issue_date)
    inv_stmt = select(Invoice).where(
        Invoice.deleted_at.is_(None),
        Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.PARTIAL, InvoiceStatus.PAID]),
        Invoice.issue_date.is_not(None),
    )
    for inv in (await session.execute(inv_stmt)).scalars().all():
        key = (inv.issue_date.year, inv.issue_date.month)
        if key in [(y, m) for y, m in window]:
            rev_invoice[key] += float(inv.total_amount)

    # Outsource billing — monthly recurring for active placements
    placement_stmt = select(OutsourcePlacement).where(
        OutsourcePlacement.deleted_at.is_(None),
    )
    placements = list((await session.execute(placement_stmt)).scalars().all())
    for y, m in window:
        first_of_month = _date(y, m, 1)
        # Determine next month start
        if m == 12:
            next_month_start = _date(y + 1, 1, 1)
        else:
            next_month_start = _date(y, m + 1, 1)
        for p in placements:
            if p.start_date <= next_month_start and (p.end_date is None or p.end_date >= first_of_month):
                rate = float(p.billing_rate)
                if p.billing_type == BillingType.FLAT_MONTHLY:
                    rev_outsource[(y, m)] += rate
                elif p.billing_type == BillingType.PER_WORKDAY:
                    rev_outsource[(y, m)] += rate * 22

    # Cost — Payroll
    slip_stmt = (
        select(PayrollSlip, PayrollPeriod)
        .join(PayrollPeriod, PayrollSlip.period_id == PayrollPeriod.id)
    )
    for slip, period in (await session.execute(slip_stmt)).all():
        key = (period.year, period.month)
        if key in [(y, m) for y, m in window]:
            cost_payroll[key] += float(slip.gross_income)

    # Cost — Reimbursement (TRANSFERRED)
    reimb_stmt = select(Reimbursement).where(
        Reimbursement.status == "TRANSFERRED",
        Reimbursement.transferred_at.is_not(None),
    )
    for r in (await session.execute(reimb_stmt)).scalars().all():
        if r.transferred_at:
            key = (r.transferred_at.year, r.transferred_at.month)
            if key in [(y, m) for y, m in window]:
                cost_reimb[key] += float(r.amount)

    # Cost — Procurement (DELIVERED)
    proc_stmt = select(ProcurementRequest).where(
        ProcurementRequest.status == "DELIVERED",
        ProcurementRequest.actual_delivery_date.is_not(None),
    )
    for p in (await session.execute(proc_stmt)).scalars().all():
        if p.actual_delivery_date and p.actual_amount:
            key = (p.actual_delivery_date.year, p.actual_delivery_date.month)
            if key in [(y, m) for y, m in window]:
                cost_proc[key] += float(p.actual_amount)

    months_data = []
    total_revenue = 0.0
    total_cost = 0.0
    total_ebitda = 0.0
    for y, m in window:
        key = (y, m)
        rev = rev_invoice[key] + rev_outsource[key]
        cost = cost_payroll[key] + cost_reimb[key] + cost_proc[key]
        ebitda = rev - cost
        margin = (ebitda / rev * 100) if rev > 0 else 0
        months_data.append({
            "year": y,
            "month": m,
            "label": f"{['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'][m-1]} {y}",
            "revenue": rev,
            "revenue_invoice": rev_invoice[key],
            "revenue_outsource": rev_outsource[key],
            "cost": cost,
            "cost_payroll": cost_payroll[key],
            "cost_reimb": cost_reimb[key],
            "cost_proc": cost_proc[key],
            "ebitda": ebitda,
            "margin_pct": round(margin, 2),
        })
        total_revenue += rev
        total_cost += cost
        total_ebitda += ebitda

    avg_margin = (total_ebitda / total_revenue * 100) if total_revenue > 0 else 0

    return {
        "months": months_data,
        "summary": {
            "total_revenue": total_revenue,
            "total_cost": total_cost,
            "total_ebitda": total_ebitda,
            "avg_margin_pct": round(avg_margin, 2),
            "period_count": len(months_data),
        },
    }


# ─── Overview endpoint ─────────────────────────────────────────────


@router.get("/overview")
async def overview_endpoint(
    session: DBSession,
    _user=Depends(require_permission("employee.view")),
) -> dict[str, Any]:
    """Aggregate stats dari 8 domain — untuk Executive Dashboard."""

    today = date.today()
    year_start = date(today.year, 1, 1)

    # ─── EMPLOYEES ──────────────────────────────────────────────
    emp_total = await session.scalar(
        select(func.count(Employee.id)).where(Employee.deleted_at.is_(None))
    )
    emp_by_status_stmt = (
        select(Employee.status, func.count(Employee.id))
        .where(Employee.deleted_at.is_(None))
        .group_by(Employee.status)
    )
    emp_by_status_rows = (await session.execute(emp_by_status_stmt)).all()
    emp_status = {
        (row[0].value if hasattr(row[0], "value") else str(row[0])): row[1]
        for row in emp_by_status_rows
    }

    emp_by_type_stmt = (
        select(Employee.employee_type, func.count(Employee.id))
        .where(Employee.deleted_at.is_(None))
        .group_by(Employee.employee_type)
    )
    emp_type_rows = (await session.execute(emp_by_type_stmt)).all()
    emp_type = {
        (row[0].value if hasattr(row[0], "value") else str(row[0])): row[1]
        for row in emp_type_rows
    }

    # Headcount by dept
    dept_headcount_stmt = (
        select(Department.code, Department.name, func.count(Employee.id))
        .outerjoin(Employee, (Employee.department_id == Department.id) & (Employee.deleted_at.is_(None)))
        .where(Department.deleted_at.is_(None))
        .group_by(Department.code, Department.name)
        .order_by(func.count(Employee.id).desc())
    )
    dept_rows = (await session.execute(dept_headcount_stmt)).all()
    headcount_by_dept = [
        {"code": r[0], "name": r[1], "count": r[2]} for r in dept_rows
    ]

    # ─── CONTRACTS ──────────────────────────────────────────────
    contracts_expiring_30 = await session.scalar(
        select(func.count(EmployeeContract.id)).where(
            EmployeeContract.is_active.is_(True),
            EmployeeContract.end_date.is_not(None),
            EmployeeContract.end_date >= today,
            EmployeeContract.end_date <= today + timedelta(days=30),
        )
    )
    contracts_expired = await session.scalar(
        select(func.count(EmployeeContract.id)).where(
            EmployeeContract.is_active.is_(True),
            EmployeeContract.end_date.is_not(None),
            EmployeeContract.end_date < today,
        )
    )

    # ─── HIRING ─────────────────────────────────────────────────
    openings_open = await session.scalar(
        select(func.count(JobOpening.id)).where(
            JobOpening.deleted_at.is_(None), JobOpening.status == "OPEN"
        )
    )
    openings_pending = await session.scalar(
        select(func.count(JobOpening.id)).where(
            JobOpening.deleted_at.is_(None),
            JobOpening.status == "PENDING_APPROVAL",
        )
    )
    applications_active = await session.scalar(
        select(func.count(JobApplication.id)).where(
            JobApplication.stage.notin_(["HIRED", "REJECTED", "WITHDRAWN"])
        )
    )

    # ─── ONBOARDING ─────────────────────────────────────────────
    onboarding_active = await session.scalar(
        select(func.count(OnboardingAssignment.id)).where(
            OnboardingAssignment.status == "IN_PROGRESS"
        )
    )

    # ─── SEPARATION ─────────────────────────────────────────────
    separation_pending = await session.scalar(
        select(func.count(EmployeeSeparation.id)).where(
            EmployeeSeparation.status.in_(
                [
                    SeparationStatus.PENDING_APPROVAL_L1,
                    SeparationStatus.PENDING_APPROVAL_L2,
                    SeparationStatus.APPROVED,
                ]
            )
        )
    )

    # ─── LEAVE ──────────────────────────────────────────────────
    leave_pending = await session.scalar(
        select(func.count(LeaveRequest.id)).where(
            LeaveRequest.status.in_(["PENDING_L1", "PENDING_L2"])
        )
    )

    # ─── PROJECTS ───────────────────────────────────────────────
    projects_active = await session.scalar(
        select(func.count(Project.id)).where(
            Project.deleted_at.is_(None), Project.status == ProjectStatus.ACTIVE
        )
    )
    projects_total = await session.scalar(
        select(func.count(Project.id)).where(Project.deleted_at.is_(None))
    )
    project_contract_value = await session.scalar(
        select(func.sum(Project.contract_value)).where(
            Project.deleted_at.is_(None),
            Project.status.in_([ProjectStatus.ACTIVE, ProjectStatus.COMPLETED]),
        )
    )

    # ─── FINANCE (Reimb + Procurement) ──────────────────────────
    reimb_pending = await session.scalar(
        select(func.count(Reimbursement.id)).where(
            Reimbursement.status.in_(["PENDING_L1", "PENDING_L2"])
        )
    )
    reimb_approved_to_transfer = await session.scalar(
        select(func.count(Reimbursement.id)).where(Reimbursement.status == "APPROVED")
    )
    reimb_total_amount = await session.scalar(
        select(func.sum(Reimbursement.amount)).where(
            Reimbursement.status.in_(["PENDING_L1", "PENDING_L2", "APPROVED"])
        )
    )
    proc_pending = await session.scalar(
        select(func.count(ProcurementRequest.id)).where(
            ProcurementRequest.status.in_(["PENDING_L1", "PENDING_L2"])
        )
    )

    # ─── SALES ──────────────────────────────────────────────────
    pipeline_value = await session.scalar(
        select(func.sum(Lead.estimated_value)).where(
            Lead.deleted_at.is_(None),
            Lead.stage.notin_([LeadStage.CLOSED_WON, LeadStage.CLOSED_LOST]),
        )
    )
    closed_won_ytd = await session.scalar(
        select(func.sum(Lead.estimated_value)).where(
            Lead.deleted_at.is_(None),
            Lead.stage == LeadStage.CLOSED_WON,
            Lead.closed_at.is_not(None),
            Lead.closed_at >= year_start,
        )
    )
    leads_total = await session.scalar(
        select(func.count(Lead.id)).where(Lead.deleted_at.is_(None))
    )
    commissions_pending_amount = await session.scalar(
        select(func.sum(SalesCommission.commission_amount)).where(
            SalesCommission.status == "PENDING"
        )
    )

    # ─── PERFORMANCE ────────────────────────────────────────────
    sp_count = await session.scalar(
        select(func.count(WarningLetter.id)).where(WarningLetter.deleted_at.is_(None))
    )
    # Latest period
    latest_period_stmt = (
        select(AssessmentPeriod)
        .order_by(AssessmentPeriod.year.desc(), AssessmentPeriod.month.desc())
        .limit(1)
    )
    latest_period = (await session.execute(latest_period_stmt)).scalar_one_or_none()
    perf_distribution = {"GREEN": 0, "YELLOW": 0, "ORANGE": 0, "RED": 0}
    if latest_period is not None:
        assess_stmt = select(Assessment.final_score).where(
            Assessment.period_id == latest_period.id, Assessment.final_score.is_not(None)
        )
        scores = (await session.execute(assess_stmt)).scalars().all()
        for s in scores:
            if s >= Decimal("70"):
                perf_distribution["GREEN"] += 1
            elif s >= Decimal("60"):
                perf_distribution["YELLOW"] += 1
            elif s >= Decimal("50"):
                perf_distribution["ORANGE"] += 1
            else:
                perf_distribution["RED"] += 1

    return {
        "as_of": today.isoformat(),
        "employees": {
            "total": emp_total or 0,
            "by_status": {k: v for k, v in emp_status.items()},
            "by_type": {k: v for k, v in emp_type.items()},
            "by_department": headcount_by_dept,
        },
        "contracts": {
            "expiring_30d": contracts_expiring_30 or 0,
            "expired_unrenewed": contracts_expired or 0,
        },
        "hiring": {
            "openings_open": openings_open or 0,
            "openings_pending_approval": openings_pending or 0,
            "applications_active": applications_active or 0,
        },
        "onboarding": {
            "active_assignments": onboarding_active or 0,
        },
        "separation": {
            "pending_or_approved": separation_pending or 0,
        },
        "leave": {
            "pending_approval": leave_pending or 0,
        },
        "projects": {
            "active": projects_active or 0,
            "total": projects_total or 0,
            "total_contract_value": float(project_contract_value or 0),
        },
        "finance": {
            "reimb_pending": reimb_pending or 0,
            "reimb_ready_to_transfer": reimb_approved_to_transfer or 0,
            "reimb_total_amount": float(reimb_total_amount or 0),
            "proc_pending": proc_pending or 0,
        },
        "sales": {
            "pipeline_value": float(pipeline_value or 0),
            "closed_won_ytd": float(closed_won_ytd or 0),
            "total_leads": leads_total or 0,
            "commissions_pending_amount": float(commissions_pending_amount or 0),
        },
        "performance": {
            "warning_letters_total": sp_count or 0,
            "latest_period": (
                {
                    "year": latest_period.year,
                    "month": latest_period.month,
                    "distribution": perf_distribution,
                    "total_assessed": sum(perf_distribution.values()),
                }
                if latest_period
                else None
            ),
        },
    }


# ─── Recent activity (audit log) ───────────────────────────────────


@router.get("/recent-activity")
async def recent_activity_endpoint(
    session: DBSession,
    _user=Depends(require_permission("audit_log.view")),
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Recent audit log entries untuk timeline widget."""
    stmt = (
        select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
    )
    result = await session.execute(stmt)
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "timestamp": log.timestamp.isoformat(),
            "actor_nik": log.actor_nik,
            "actor_persona": log.actor_persona,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
        }
        for log in logs
    ]
