"""Notification template registry — TSK-058.

Single source of truth for notification copy. Each NotificationType maps to a
template with `title`, `body`, `link`, `priority`. Templates use Python format
strings (`{var}`) — keys must be passed via context.

Usage:
    from app.notification.templates import notify_from_template

    await notify_from_template(
        session,
        user_id=approver_user_id,
        type=NotificationType.LEAVE_PENDING_APPROVAL,
        context={
            "requester_name": "Budi Santoso",
            "leave_type": "Annual",
            "days": 3,
            "leave_id": str(leave.id),
        },
    )

Adding a new type:
1. Add enum value to NotificationType (models.py)
2. Add template entry below
3. Add color/icon to NOTIFICATION_TYPE_META in frontend
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.notification.models import (
    Notification,
    NotificationPriority,
    NotificationType,
)
from app.notification.service import notify

logger = logging.getLogger(__name__)


# ─── Template Registry ────────────────────────────────────────────────────
#
# Each value is a dict:
#   title     — short heading
#   body      — preview text (optional)
#   link      — frontend route (use {var} for params)
#   priority  — NotificationPriority enum
#
# Variables in {curly braces} are substituted from `context` dict passed
# to notify_from_template(). Missing keys → log warning + fall back to raw.

TemplateSpec = dict[str, Any]

NOTIFICATION_TEMPLATES: dict[NotificationType, TemplateSpec] = {
    # ─── Generic approval ─────────────────────────────────────────────────
    NotificationType.APPROVAL_PENDING: {
        "title": "Approval menunggu Anda",
        "body": "{requester_name} mengajukan {request_type}, menunggu approval Anda.",
        "link": "{link}",
        "priority": NotificationPriority.HIGH,
    },
    NotificationType.APPROVAL_APPROVED: {
        "title": "Request disetujui",
        "body": "Pengajuan {request_type} Anda telah disetujui oleh {approver_name}.",
        "link": "{link}",
        "priority": NotificationPriority.NORMAL,
    },
    NotificationType.APPROVAL_REJECTED: {
        "title": "Request ditolak",
        "body": "Pengajuan {request_type} Anda ditolak oleh {approver_name}. Alasan: {reason}",
        "link": "{link}",
        "priority": NotificationPriority.HIGH,
    },
    # ─── Payroll ──────────────────────────────────────────────────────────
    NotificationType.PAYROLL_PENDING_APPROVAL: {
        "title": "Payroll periode {period} menunggu approval",
        "body": "Run payroll {period} ({employee_count} karyawan, total Rp {total_idr}) siap di-approve.",
        "link": "/payroll/runs/{run_id}",
        "priority": NotificationPriority.HIGH,
    },
    NotificationType.PAYROLL_APPROVED: {
        "title": "Payroll {period} disetujui",
        "body": "Run payroll {period} sudah di-approve oleh {approver_name}. Siap untuk transfer.",
        "link": "/payroll/runs/{run_id}",
        "priority": NotificationPriority.NORMAL,
    },
    NotificationType.PAYROLL_PUBLISHED: {
        "title": "Slip gaji {period} tersedia",
        "body": "Slip gaji periode {period} sudah dapat diakses. Total terima: Rp {nett_idr}.",
        "link": "/payroll/slips/{slip_id}",
        "priority": NotificationPriority.NORMAL,
    },
    # ─── Leave ────────────────────────────────────────────────────────────
    NotificationType.LEAVE_PENDING_APPROVAL: {
        "title": "Cuti menunggu approval",
        "body": "{requester_name} mengajukan {leave_type} {days} hari ({date_range}).",
        "link": "/leave?id={leave_id}",
        "priority": NotificationPriority.HIGH,
    },
    NotificationType.LEAVE_APPROVED: {
        "title": "Cuti disetujui",
        "body": "Pengajuan {leave_type} {days} hari ({date_range}) Anda telah disetujui.",
        "link": "/leave?id={leave_id}",
        "priority": NotificationPriority.NORMAL,
    },
    NotificationType.LEAVE_REJECTED: {
        "title": "Cuti ditolak",
        "body": "Pengajuan {leave_type} {days} hari ditolak. Alasan: {reason}",
        "link": "/leave?id={leave_id}",
        "priority": NotificationPriority.HIGH,
    },
    # ─── Contract / Placement ─────────────────────────────────────────────
    NotificationType.CONTRACT_EXPIRING: {
        "title": "Kontrak {contract_no} expire H-{days_left}",
        "body": "{employee_name} ({position}) kontrak berakhir {end_date}. Segera proses renewal/decision.",
        "link": "/contracts?contract_id={contract_id}",
        "priority": NotificationPriority.HIGH,
    },
    NotificationType.CONTRACT_RENEWED: {
        "title": "Kontrak {employee_name} diperpanjang",
        "body": "{employee_name} sudah di-renew sampai {new_end_date} dengan tipe {new_type}.",
        "link": "/contracts?contract_id={contract_id}",
        "priority": NotificationPriority.NORMAL,
    },
    # ─── Project Task ─────────────────────────────────────────────────────
    NotificationType.TASK_DEADLINE: {
        "title": "Task {task_slug} due H-{days_left}",
        "body": "Task '{task_title}' jatuh tempo {due_date}. Project: {project_code}.",
        "link": "/projects/{project_id}?task={task_id}",
        "priority": NotificationPriority.NORMAL,
    },
    NotificationType.TASK_OVERDUE: {
        "title": "Task {task_slug} OVERDUE",
        "body": "Task '{task_title}' lewat tenggat ({due_date}). Mohon segera update.",
        "link": "/projects/{project_id}?task={task_id}",
        "priority": NotificationPriority.URGENT,
    },
    # ─── Separation ───────────────────────────────────────────────────────
    NotificationType.SEPARATION_PENDING: {
        "title": "Separation menunggu approval",
        "body": "{requester_name} mengajukan {separation_type} untuk {employee_name}, efektif {effective_date}.",
        "link": "/separations/{separation_id}",
        "priority": NotificationPriority.HIGH,
    },
    NotificationType.SEPARATION_EXECUTED: {
        "title": "Separation {employee_name} dieksekusi",
        "body": "Separation {separation_type} untuk {employee_name} sudah dieksekusi.",
        "link": "/separations/{separation_id}",
        "priority": NotificationPriority.NORMAL,
    },
    # ─── Procurement / Reimbursement ──────────────────────────────────────
    NotificationType.PROCUREMENT_PENDING: {
        "title": "{kind} menunggu approval",
        "body": "{requester_name} mengajukan {kind} Rp {amount_idr}: {purpose}",
        "link": "/finance?tab={tab}&id={request_id}",
        "priority": NotificationPriority.HIGH,
    },
    NotificationType.PROCUREMENT_APPROVED: {
        "title": "{kind} disetujui",
        "body": "Pengajuan {kind} Rp {amount_idr} telah disetujui.",
        "link": "/finance?tab={tab}&id={request_id}",
        "priority": NotificationPriority.NORMAL,
    },
    # ─── Finance / Invoice ────────────────────────────────────────────────
    NotificationType.INVOICE_TRIGGER: {
        "title": "Trigger invoice: {project_code} {phase_name}",
        "body": "Phase '{phase_name}' di project {project_code} sudah complete. Total Rp {amount_idr} siap di-invoice.",
        "link": "/finance?phase_id={phase_id}",
        "priority": NotificationPriority.HIGH,
    },
    # ─── Outsource ────────────────────────────────────────────────────────
    NotificationType.KPI_DEADLINE: {
        "title": "KPI client {client_name} belum disubmit",
        "body": "Penilaian {employee_name} periode {period} expire H-{days_left}. Token: {token}",
        "link": "/outsource?tab=kpi&id={assessment_id}",
        "priority": NotificationPriority.HIGH,
    },
    # ─── SP / SP-O ────────────────────────────────────────────────────────
    NotificationType.SP_ISSUED: {
        "title": "Surat Peringatan ({sp_level}) diterbitkan",
        "body": "SP {sp_level} diterbitkan untuk {employee_name}. Alasan: {reason}",
        "link": "/performance?tab=sp&id={sp_id}",
        "priority": NotificationPriority.URGENT,
    },
    NotificationType.SP_O_ISSUED: {
        "title": "SP-O ({sp_o_level}) diterbitkan",
        "body": "SP-O {sp_o_level} untuk {employee_name} (client {client_name}). Trigger: {trigger}",
        "link": "/outsource?tab=spo&id={sp_o_id}",
        "priority": NotificationPriority.URGENT,
    },
    # ─── Change Request ───────────────────────────────────────────────────
    NotificationType.CHANGE_REQUEST_PENDING: {
        "title": "Change Request menunggu approval",
        "body": "{requester_name} ajukan CR di {project_code}: {summary}",
        "link": "/projects/{project_id}?tab=cr&id={cr_id}",
        "priority": NotificationPriority.HIGH,
    },
    NotificationType.CHANGE_REQUEST_RESOLVED: {
        "title": "Change Request resolved",
        "body": "CR Anda di {project_code} di-resolve: {summary}",
        "link": "/projects/{project_id}?tab=cr&id={cr_id}",
        "priority": NotificationPriority.NORMAL,
    },
    # ─── System ───────────────────────────────────────────────────────────
    NotificationType.SYSTEM: {
        "title": "{title}",
        "body": "{body}",
        "link": "{link}",
        "priority": NotificationPriority.NORMAL,
    },
}


# ─── Renderer ─────────────────────────────────────────────────────────────


def _safe_format(template: str, context: dict[str, Any]) -> str:
    """Format template tolerant to missing keys (replace with empty)."""
    try:
        return template.format(**context)
    except KeyError as e:
        logger.warning(
            "notification template missing key %s in template %r, context keys: %s",
            e, template[:60], list(context.keys()),
        )
        # Provide defaults for missing keys
        from collections import defaultdict

        class _DefaultDict(defaultdict):
            def __missing__(self, key: str) -> str:
                return f"{{{key}}}"

        d = _DefaultDict(str)
        d.update(context)
        return template.format_map(d)


async def notify_from_template(
    session: AsyncSession,
    *,
    user_id: UUID,
    type: NotificationType,
    context: dict[str, Any],
    override_priority: NotificationPriority | None = None,
) -> Notification:
    """Render template + create notification.

    Variables in template ({key}) substituted from `context`.
    Missing keys logged as warning and left as `{key}` in output.

    Usage:
        await notify_from_template(
            session,
            user_id=approver.id,
            type=NotificationType.LEAVE_PENDING_APPROVAL,
            context={
                "requester_name": "Budi",
                "leave_type": "Annual",
                "days": 3,
                "date_range": "1-3 Jun 2026",
                "leave_id": str(leave.id),
            },
        )
    """
    spec = NOTIFICATION_TEMPLATES.get(type)
    if spec is None:
        logger.error("no template registered for NotificationType.%s", type.value)
        # Fall back to using context values directly
        title = context.get("title", type.value)
        body = context.get("body")
        link = context.get("link")
        priority = override_priority or NotificationPriority.NORMAL
    else:
        title = _safe_format(spec["title"], context)
        body = _safe_format(spec.get("body") or "", context) if spec.get("body") else None
        link = _safe_format(spec.get("link") or "", context) if spec.get("link") else None
        priority = override_priority or spec.get("priority", NotificationPriority.NORMAL)

    return await notify(
        session,
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        link_url=link,
        priority=priority,
        meta=context,  # preserve full context untuk debug/replay
    )


async def notify_bulk_from_template(
    session: AsyncSession,
    *,
    user_ids: list[UUID],
    type: NotificationType,
    context: dict[str, Any],
    override_priority: NotificationPriority | None = None,
) -> int:
    """Bulk fan-out of same templated message to multiple users.

    Returns count created. Same template content for all — context shared.
    """
    count = 0
    for uid in user_ids:
        await notify_from_template(
            session,
            user_id=uid,
            type=type,
            context=context,
            override_priority=override_priority,
        )
        count += 1
    return count
