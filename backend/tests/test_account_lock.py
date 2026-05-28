"""Tests untuk TSK-006 Account Lock refinement.

Coverage:
- ✓ Lockout response include locked_until + remaining_seconds
- ✓ Admin unlock endpoint berfungsi
- ✓ Unlock memerlukan permission user.edit (GM+)
- ✓ Unlock invalid NIK → 404
- ✓ Unlock audit log dengan persona
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.database import async_session_factory
from app.identity.models import (
    AuditLog,
    HierarchyLevel,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.identity.permissions import PERMISSION_REGISTRY, ROLE_PERMISSION_MAP
from app.main import app


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def seed_full(session: AsyncSession) -> dict[str, Role]:
    perm_lookup: dict[str, Permission] = {}
    for code, resource, action, description in PERMISSION_REGISTRY:
        existing = await session.execute(select(Permission).where(Permission.code == code))
        p = existing.scalar_one_or_none()
        if p is None:
            p = Permission(
                code=code, resource=resource.value, action=action.value, description=description
            )
            session.add(p)
        perm_lookup[code] = p
    await session.flush()

    role_specs = [
        ("DIREKTUR_UTAMA", "Direktur Utama", HierarchyLevel.L1_DIREKTUR_UTAMA.value, True),
        ("GM", "General Manager", HierarchyLevel.L3_GM.value, False),
        ("STAFF", "Staff", HierarchyLevel.L6_STAFF.value, False),
    ]
    role_lookup: dict[str, Role] = {}
    for code, name, level, is_exec in role_specs:
        existing = await session.execute(select(Role).where(Role.code == code))
        r = existing.scalar_one_or_none()
        if r is None:
            r = Role(code=code, name=name, level=level, is_executive=is_exec)
            session.add(r)
        role_lookup[code] = r
    await session.flush()

    for role_code, perm_codes in ROLE_PERMISSION_MAP.items():
        role = role_lookup.get(role_code)
        if role is None:
            continue
        existing = await session.execute(
            select(RolePermission.permission_id).where(RolePermission.role_id == role.id)
        )
        existing_ids = {row[0] for row in existing.all()}
        for pc in perm_codes:
            p = perm_lookup.get(pc)
            if p is None or p.id in existing_ids:
                continue
            session.add(RolePermission(role_id=role.id, permission_id=p.id))

    await session.commit()
    for r in role_lookup.values():
        await session.refresh(r)
    return role_lookup


async def _create_user(
    session: AsyncSession, nik: str, role: Role, locked: bool = False
) -> User:
    user = User(
        nik=nik,
        password_hash=hash_password("test123"),
        email=f"{nik.lower()}@ide.asia",
        is_active=True,
        is_locked=locked,
        failed_login_attempts=5 if locked else 0,
        locked_until=(datetime.now(UTC) + timedelta(minutes=30)) if locked else None,
    )
    session.add(user)
    await session.flush()
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    from app.identity.service import get_user_by_id

    full = await get_user_by_id(session, user.id)
    assert full is not None
    return full


async def _login(client: AsyncClient, nik: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"nik": nik, "password": "test123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ─── Lock response shape ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_locked_returns_remaining_seconds(
    client: AsyncClient, session: AsyncSession, seed_full: dict[str, Role]
) -> None:
    """Login dengan account yang sudah locked → response berisi remaining_seconds + locked_until."""
    await _create_user(session, "LOCK-TEST-001", seed_full["STAFF"], locked=True)

    response = await client.post(
        "/api/v1/auth/login",
        json={"nik": "LOCK-TEST-001", "password": "test123"},
    )
    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "ACCOUNT_LOCKED"
    assert "locked_until" in detail
    assert "remaining_seconds" in detail
    assert detail["remaining_seconds"] > 0
    assert detail["remaining_seconds"] <= 30 * 60  # max 30 min


# ─── Admin unlock endpoint ───────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_unlock_user_account(
    client: AsyncClient, session: AsyncSession, seed_full: dict[str, Role]
) -> None:
    """Admin (GM dengan user.edit permission) bisa unlock account."""
    # Setup: GM admin + locked user
    await _create_user(session, "GM-ADMIN-001", seed_full["GM"])
    locked_user = await _create_user(session, "LOCK-VICTIM-001", seed_full["STAFF"], locked=True)

    token = await _login(client, "GM-ADMIN-001")

    response = await client.post(
        f"/api/v1/admin/users/{locked_user.nik}/unlock",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["success"] is True
    assert data["was_locked"] is True

    # Verify DB state — user no longer locked
    await session.refresh(locked_user)
    assert locked_user.is_locked is False
    assert locked_user.failed_login_attempts == 0
    assert locked_user.locked_until is None


@pytest.mark.asyncio
async def test_unlock_creates_audit_log_with_persona(
    client: AsyncClient, session: AsyncSession, seed_full: dict[str, Role]
) -> None:
    """Audit log USER_UNLOCKED dengan persona explicit (NC-EX-005)."""
    await _create_user(session, "DIR-UNLOCK-001", seed_full["DIREKTUR_UTAMA"])
    await _create_user(session, "VICTIM-002", seed_full["STAFF"], locked=True)
    token = await _login(client, "DIR-UNLOCK-001")

    await client.post(
        f"/api/v1/admin/users/VICTIM-002/unlock",
        headers={"Authorization": f"Bearer {token}"},
    )

    stmt = (
        select(AuditLog)
        .where(AuditLog.actor_nik == "DIR-UNLOCK-001", AuditLog.action == "USER_UNLOCKED")
        .order_by(AuditLog.timestamp.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    log = result.scalar_one_or_none()
    assert log is not None
    assert "Direktur Utama" in log.actor_persona
    assert log.resource_id == "VICTIM-002"
    assert log.before_state == {"is_locked": True, "failed_login_attempts": 5}
    assert log.after_state == {"is_locked": False, "failed_login_attempts": 0}


@pytest.mark.asyncio
async def test_unlock_invalid_nik_returns_404(
    client: AsyncClient, session: AsyncSession, seed_full: dict[str, Role]
) -> None:
    """Unlock NIK tidak ada → 404."""
    await _create_user(session, "GM-ADMIN-003", seed_full["GM"])
    token = await _login(client, "GM-ADMIN-003")

    response = await client.post(
        "/api/v1/admin/users/NONEXISTENT-NIK-999/unlock",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "USER_NOT_FOUND"


@pytest.mark.asyncio
async def test_unlock_denied_for_staff(
    client: AsyncClient, session: AsyncSession, seed_full: dict[str, Role]
) -> None:
    """Staff tidak punya permission user.edit → 403."""
    await _create_user(session, "STAFF-UNLOCK-001", seed_full["STAFF"])
    await _create_user(session, "VICTIM-003", seed_full["STAFF"], locked=True)

    token = await _login(client, "STAFF-UNLOCK-001")

    response = await client.post(
        "/api/v1/admin/users/VICTIM-003/unlock",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"
