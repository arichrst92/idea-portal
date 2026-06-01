"""Alert Rules Engine — TSK-059.

Scheduled scanner yang push notifications saat events crossing thresholds.
Idempotent via Notification.dedupe_key — re-run hari yang sama tidak duplikasi.

Rules implemented:
- contract_expiring_alerts(): EmployeeContract H-30 / H-14 / H-7 → atasan + Operation
- placement_expiring_alerts(): OutsourcePlacement H-30 / H-14 / H-7 → Operation
- kpi_deadline_alerts(): ClientKpiAssessment H-7 sebelum token expire & unsubmitted
- task_deadline_alerts(): ProjectTask H-3 (warning) atau OVERDUE → assignee
- payroll_pending_alerts(): PayrollPeriod PENDING_APPROVAL > 1 hari → approver reminder

Master entrypoint: `run_all_alert_rules(session)` — call ini dari APScheduler atau
endpoint admin trigger. Returns dict {rule: count}.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.notification.approver_chain import (
    find_l1_l2_approver_user_ids,
    get_employee_display_name,
)
from app.notification.models import NotificationType
from app.notification.templates import notify_from_template

logger = logging.getLogger(__name__)


# ─── Helper ────────────────────────────────────────────────────────


def _dedupe_key(rule: str, resource_id: UUID | str, day: date | None = None) -> str:
    """Build dedupe key untuk avoid duplicate notif same-day."""
    d = day or date.today()
    return f"{rule}:{resource_id}:{d.isoformat()}"


async def _get_user_ids_with_permission(
    session: AsyncSession, perm_code: str
) -> list[UUID]:
    """Resolve all users having a permission (for fan-out alerts)."""
    from app.identity.models import Permission, Role, RolePermission, User, UserRole

    stmt = (
        select(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(Permission.code == perm_code)
        .distinct()
    )
    return list((await session.execute(stmt)).scalars().all())


# ─── Rule: Contract Expiring (PKWT) ────────────────────────────────


async def contract_expiring_alerts(session: AsyncSession) -> int:
    """Alert atasan + Operation kalau EmployeeContract end_date dekat.

    Thresholds: H-30, H-14, H-7 sebelum end_date.
    NC: knowledge.md sec.5 — alert H-30 & H-7 wajib.
    """
    from app.organization.models import Employee, EmployeeContract

    today = date.today()
    thresholds = [(30, "H-30"), (14, "H-14"), (7, "H-7")]

    count = 0
    for days_ahead, label in thresholds:
        target_date = today + timedelta(days=days_ahead)
        stmt = (
            select(EmployeeContract)
            .where(EmployeeContract.is_active.is_(True))
            .where(EmployeeContract.end_date == target_date)
        )
        contracts = list((await session.execute(stmt)).scalars().all())

        for c in contracts:
            emp = await session.get(Employee, c.employee_id)
            if not emp:
                continue

            ctx = {
                "contract_no": str(c.id)[:8],
                "contract_id": str(c.id),
                "days_left": days_ahead,
                "employee_name": emp.full_name,
                "position": "",  # could resolve via position_id later
                "end_date": c.end_date.strftime("%d %b %Y") if c.end_date else "—",
            }

            # Notify supervisor (L1 approver)
            l1, _l2 = await find_l1_l2_approver_user_ids(session, emp.id)
            if l1:
                key = _dedupe_key(f"contract_{label.lower()}_l1", c.id)
                res = await notify_from_template(
                    session,
                    user_id=l1,
                    type=NotificationType.CONTRACT_EXPIRING,
                    context=ctx,
                    dedupe_key=key,
                )
                if res:
                    count += 1

            # Notify Operation (users dengan employee.view permission)
            ops_ids = await _get_user_ids_with_permission(session, "employee.view")
            for uid in ops_ids:
                if uid == l1:
                    continue  # already notified
                key = _dedupe_key(f"contract_{label.lower()}_ops:{uid}", c.id)
                res = await notify_from_template(
                    session,
                    user_id=uid,
                    type=NotificationType.CONTRACT_EXPIRING,
                    context=ctx,
                    dedupe_key=key,
                )
                if res:
                    count += 1

        await session.commit()

    logger.info("contract_expiring_alerts: %d notifs sent", count)
    return count


# ─── Rule: Outsource Placement Expiring ────────────────────────────


async def placement_expiring_alerts(session: AsyncSession) -> int:
    """Alert Operation kalau OutsourcePlacement end_date dekat (H-30/14/7)."""
    from app.outsource.models import OutsourcePlacement
    from app.organization.models import Employee

    today = date.today()
    thresholds = [(30, "H-30"), (14, "H-14"), (7, "H-7")]
    count = 0

    for days_ahead, label in thresholds:
        target_date = today + timedelta(days=days_ahead)
        stmt = (
            select(OutsourcePlacement)
            .where(OutsourcePlacement.is_active.is_(True))
            .where(OutsourcePlacement.deleted_at.is_(None))
            .where(OutsourcePlacement.end_date == target_date)
        )
        placements = list((await session.execute(stmt)).scalars().all())

        ops_ids = await _get_user_ids_with_permission(session, "outsource.view")

        for p in placements:
            emp = await session.get(Employee, p.employee_id)
            ctx = {
                "contract_no": f"PLACEMENT-{str(p.id)[:8]}",
                "contract_id": str(p.id),
                "days_left": days_ahead,
                "employee_name": emp.full_name if emp else "—",
                "position": p.role_at_client,
                "end_date": p.end_date.strftime("%d %b %Y") if p.end_date else "—",
            }
            for uid in ops_ids:
                key = _dedupe_key(f"placement_{label.lower()}:{uid}", p.id)
                res = await notify_from_template(
                    session,
                    user_id=uid,
                    type=NotificationType.CONTRACT_EXPIRING,
                    context=ctx,
                    dedupe_key=key,
                )
                if res:
                    count += 1

        await session.commit()

    logger.info("placement_expiring_alerts: %d notifs sent", count)
    return count


# ─── Rule: KPI Deadline ────────────────────────────────────────────


async def kpi_deadline_alerts(session: AsyncSession) -> int:
    """Alert Operation kalau ClientKpiAssessment token H-7 expire & belum submit."""
    from app.outsource.models import ClientKpiAssessment, OutsourcePlacement
    from app.organization.models import Employee

    today = date.today()
    target = today + timedelta(days=7)

    stmt = (
        select(ClientKpiAssessment)
        .where(ClientKpiAssessment.is_submitted.is_(False))
        .where(ClientKpiAssessment.token_expires_at == target)
    )
    assessments = list((await session.execute(stmt)).scalars().all())

    ops_ids = await _get_user_ids_with_permission(session, "outsource.view")
    count = 0

    for a in assessments:
        placement = await session.get(OutsourcePlacement, a.placement_id)
        if not placement:
            continue
        emp = await session.get(Employee, placement.employee_id)
        # Fetch client_name via Client model
        client_name = "—"
        try:
            from app.outsource.models import Client
            client = await session.get(Client, placement.client_id)
            if client:
                client_name = client.name
        except Exception:  # noqa: BLE001
            pass

        ctx = {
            "client_name": client_name,
            "employee_name": emp.full_name if emp else "—",
            "period": a.assessment_period,
            "days_left": 7,
            "token": a.token,
            "assessment_id": str(a.id),
        }

        for uid in ops_ids:
            key = _dedupe_key(f"kpi_h7:{uid}", a.id)
            res = await notify_from_template(
                session,
                user_id=uid,
                type=NotificationType.KPI_DEADLINE,
                context=ctx,
                dedupe_key=key,
            )
            if res:
                count += 1

    await session.commit()
    logger.info("kpi_deadline_alerts: %d notifs sent", count)
    return count


# ─── Rule: Task Deadline (H-3 + Overdue) ───────────────────────────


async def task_deadline_alerts(session: AsyncSession) -> int:
    """Alert assignee untuk task H-3 + OVERDUE."""
    from app.project.models import Project, ProjectTask
    from app.organization.models import Employee

    today = date.today()
    h3_target = today + timedelta(days=3)
    count = 0

    # H-3 — task due 3 hari lagi
    h3_stmt = (
        select(ProjectTask)
        .where(ProjectTask.deleted_at.is_(None))
        .where(ProjectTask.status.notin_(("DONE",)))
        .where(ProjectTask.due_date == h3_target)
        .where(ProjectTask.assignee_id.is_not(None))
    )
    h3_tasks = list((await session.execute(h3_stmt)).scalars().all())

    for t in h3_tasks:
        emp = await session.get(Employee, t.assignee_id)
        if not emp or not emp.user_id:
            continue
        project = await session.get(Project, t.project_id)
        ctx = {
            "task_slug": t.slug,
            "days_left": 3,
            "task_title": t.title,
            "due_date": t.due_date.strftime("%d %b %Y") if t.due_date else "—",
            "project_code": project.code if project else "—",
            "project_id": str(t.project_id),
            "task_id": str(t.id),
        }
        key = _dedupe_key("task_h3", t.id)
        res = await notify_from_template(
            session,
            user_id=emp.user_id,
            type=NotificationType.TASK_DEADLINE,
            context=ctx,
            dedupe_key=key,
        )
        if res:
            count += 1

    # OVERDUE — task lewat due_date
    overdue_stmt = (
        select(ProjectTask)
        .where(ProjectTask.deleted_at.is_(None))
        .where(ProjectTask.status.notin_(("DONE",)))
        .where(ProjectTask.due_date < today)
        .where(ProjectTask.assignee_id.is_not(None))
    )
    overdue_tasks = list((await session.execute(overdue_stmt)).scalars().all())

    for t in overdue_tasks:
        emp = await session.get(Employee, t.assignee_id)
        if not emp or not emp.user_id:
            continue
        project = await session.get(Project, t.project_id)
        days_overdue = (today - t.due_date).days if t.due_date else 0
        ctx = {
            "task_slug": t.slug,
            "task_title": t.title,
            "due_date": t.due_date.strftime("%d %b %Y") if t.due_date else "—",
            "days_overdue": days_overdue,
            "project_code": project.code if project else "—",
            "project_id": str(t.project_id),
            "task_id": str(t.id),
        }
        key = _dedupe_key("task_overdue", t.id)
        res = await notify_from_template(
            session,
            user_id=emp.user_id,
            type=NotificationType.TASK_OVERDUE,
            context=ctx,
            dedupe_key=key,
        )
        if res:
            count += 1

    await session.commit()
    logger.info(
        "task_deadline_alerts: %d notifs sent (H-3 + OVERDUE)", count
    )
    return count


# ─── Rule: Payroll Pending Approval (stale) ────────────────────────


async def payroll_pending_alerts(session: AsyncSession) -> int:
    """Reminder kalau PayrollPeriod PENDING_APPROVAL > 1 hari & belum di-action."""
    from app.payroll.models import PayrollPeriod

    cutoff = datetime.now(UTC) - timedelta(days=1)
    stmt = (
        select(PayrollPeriod)
        .where(PayrollPeriod.status == "PENDING_APPROVAL")
        .where(PayrollPeriod.submitted_for_review_at.is_not(None))
        .where(PayrollPeriod.submitted_for_review_at < cutoff)
    )
    periods = list((await session.execute(stmt)).scalars().all())

    approver_ids = await _get_user_ids_with_permission(session, "payroll.approve")
    count = 0

    for p in periods:
        ctx = {
            "period": f"{p.year}-{p.month:02d}",
            "employee_count": "—",
            "total_idr": "—",
            "run_id": str(p.id),
        }
        for uid in approver_ids:
            key = _dedupe_key("payroll_pending_reminder", p.id)
            res = await notify_from_template(
                session,
                user_id=uid,
                type=NotificationType.PAYROLL_PENDING_APPROVAL,
                context=ctx,
                dedupe_key=key,
            )
            if res:
                count += 1

    await session.commit()
    logger.info("payroll_pending_alerts: %d notifs sent", count)
    return count


# ─── Master entrypoint ─────────────────────────────────────────────


async def run_all_alert_rules(session: AsyncSession) -> dict[str, int]:
    """Run every rule sequentially. Returns counts per rule.

    Designed to be called daily ~06:00 WIB. Idempotent via dedupe_key.
    """
    logger.info("Alert Rules Engine — starting scan at %s", datetime.now(UTC))
    results: dict[str, int] = {}

    for rule_name, rule_func in [
        ("contract_expiring", contract_expiring_alerts),
        ("placement_expiring", placement_expiring_alerts),
        ("kpi_deadline", kpi_deadline_alerts),
        ("task_deadline", task_deadline_alerts),
        ("payroll_pending", payroll_pending_alerts),
    ]:
        try:
            count = await rule_func(session)
            results[rule_name] = count
        except Exception as e:  # noqa: BLE001
            logger.exception("Alert rule %s failed: %s", rule_name, e)
            results[rule_name] = -1  # signal error

    logger.info("Alert Rules Engine — scan complete. Results: %s", results)
    return results
