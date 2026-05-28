"""Audit log helper — write audit_logs entries dengan persona eksplisit.

Per NC-EX-005 (Critical): WAJIB record persona name eksplisit:
- "Rudi Atmadja (Direktur Utama)" — bukan generic "Direktur"
- "Siti Hartono (Wakil Direktur Utama)" — wajib eksplisit
- CI test akan verify ini di TSK-201 (Wakil Direktur Audit Persona Display).

Usage:
    from app.core.audit import audit_log
    await audit_log(
        session,
        actor=current_user,
        action="LOGIN_SUCCESS",
        resource_type="auth",
        resource_id=current_user.nik,
        ip_address=request.client.host,
    )
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.models import AuditLog, User
from app.identity.service import get_persona_name


async def audit_log(
    session: AsyncSession,
    *,
    actor: User | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    notes: str | None = None,
    commit: bool = False,
) -> AuditLog:
    """Insert audit log entry dengan persona eksplisit.

    Args:
        session: AsyncSession (caller controls commit/rollback)
        actor: User yang melakukan action (None untuk anonymous/system)
        action: action code (snake_case, e.g., "LOGIN_SUCCESS", "PROJECT_CLOSED_OVERRIDE")
        resource_type: tipe resource yang di-affect (e.g., "user", "project")
        resource_id: identifier resource (NIK, UUID, dst)
        ip_address: IP dari request.client.host
        user_agent: User-Agent header (optional, max 500 chars)
        before_state: snapshot data sebelum perubahan (JSONB)
        after_state: snapshot data setelah perubahan (JSONB)
        notes: catatan tambahan
        commit: kalau True, commit langsung. Default False supaya caller bisa batch.

    Returns:
        AuditLog yang sudah di-insert (belum di-flush kalau commit=False).
    """
    persona = get_persona_name(actor) if actor else "System (anonymous)"

    log = AuditLog(
        timestamp=datetime.now(UTC),
        actor_user_id=actor.id if actor else None,
        actor_nik=actor.nik if actor else None,
        actor_persona=persona,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=(user_agent[:500] if user_agent else None),
        before_state=before_state,
        after_state=after_state,
        notes=notes,
    )
    session.add(log)
    if commit:
        await session.commit()
    return log
