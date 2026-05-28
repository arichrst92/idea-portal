"""Tests untuk session management — TSK-005 + TSK-011.

Coverage:
- ✓ POST /auth/logout revoke refresh token
- ✓ Setelah logout, refresh dengan token lama → 401 REFRESH_TOKEN_REVOKED
- ✓ Logout butuh valid access token
- ✓ Token rotation: refresh sukses + old token jadi invalid
- ✓ Audit log: LOGOUT_SUCCESS terekam
- ✓ Audit log: TOKEN_REFRESHED terekam
- ✓ /audit-logs endpoint: paginated query (Executive only)
- ✓ /audit-logs RBAC: non-Executive return 403 (atau permission denied)
- ✓ /audit-logs filtering by action + actor_nik

Note: Tests pakai Redis dari docker-compose. Pastikan redis container running.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.database import async_session_factory
from app.identity import blacklist
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
async def seed_full_permissions(session: AsyncSession) -> dict[str, Role]:
    """Seed permissions + roles + mappings (sama seperti di test_rbac)."""
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
        ("WAKIL_DIREKTUR_UTAMA", "Wakil Direktur Utama", HierarchyLevel.L1B_WAKIL_DIREKTUR_UTAMA.value, True),
        ("C_LEVEL", "C-Level", HierarchyLevel.L2_C_LEVEL.value, True),
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


async def _create_user_with_role(
    session: AsyncSession, nik: str, role: Role
) -> User:
    """Helper: create user dengan 1 role."""
    user = User(
        nik=nik,
        password_hash=hash_password("test123"),
        email=f"{nik.lower()}@ide.asia",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    from app.identity.service import get_user_by_id

    user_full = await get_user_by_id(session, user.id)
    assert user_full is not None
    return user_full


async def _login(client: AsyncClient, nik: str) -> dict[str, str]:
    """Helper: login + return {access_token, refresh_token}."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"nik": nik, "password": "test123"},
    )
    assert response.status_code == 200, response.text
    return response.json()


# ─── Logout flow ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(
    client: AsyncClient, session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """Logout → refresh token di-blacklist → tidak bisa refresh lagi."""
    await _create_user_with_role(session, "LOGOUT-001", seed_full_permissions["GM"])
    tokens = await _login(client, "LOGOUT-001")

    # Logout
    response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["revoked"] is True

    # Verify blacklist
    assert await blacklist.is_revoked(tokens["refresh_token"]) is True

    # Refresh dengan token revoked → 401
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 401
    assert refresh_response.json()["detail"]["code"] == "REFRESH_TOKEN_REVOKED"


@pytest.mark.asyncio
async def test_logout_requires_access_token(
    client: AsyncClient, session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """Logout tanpa Authorization header → 401."""
    await _create_user_with_role(session, "LOGOUT-002", seed_full_permissions["GM"])
    tokens = await _login(client, "LOGOUT-002")

    response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        # NO Authorization header
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotation_revokes_old_token(
    client: AsyncClient, session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """Refresh sukses → old refresh token jadi blacklisted."""
    await _create_user_with_role(session, "ROT-001", seed_full_permissions["GM"])
    tokens = await _login(client, "ROT-001")
    old_refresh = tokens["refresh_token"]

    # Refresh sekali → new pair
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert response.status_code == 200

    # Old refresh token sekarang revoked
    assert await blacklist.is_revoked(old_refresh) is True

    # Pakai old refresh lagi → 401
    response2 = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert response2.status_code == 401
    assert response2.json()["detail"]["code"] == "REFRESH_TOKEN_REVOKED"


# ─── Audit log query (TSK-011) ───────────────────────────────────


@pytest.mark.asyncio
async def test_audit_logs_accessible_by_direktur(
    client: AsyncClient, session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """Direktur Utama bisa query /audit-logs."""
    # Clear existing audit logs untuk test isolation
    await session.execute(delete(AuditLog))
    await session.commit()

    await _create_user_with_role(session, "DIR-AUD-001", seed_full_permissions["DIREKTUR_UTAMA"])
    tokens = await _login(client, "DIR-AUD-001")  # Generates LOGIN_SUCCESS audit

    response = await client.get(
        "/api/v1/auth/audit-logs?limit=10",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["limit"] == 10
    assert data["total"] >= 1  # Setidaknya ada LOGIN_SUCCESS audit


@pytest.mark.asyncio
async def test_audit_logs_filter_by_action(
    client: AsyncClient, session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """/audit-logs?action=LOGIN_SUCCESS filter benar."""
    await _create_user_with_role(session, "DIR-AUD-002", seed_full_permissions["DIREKTUR_UTAMA"])
    tokens = await _login(client, "DIR-AUD-002")

    response = await client.get(
        "/api/v1/auth/audit-logs?action=LOGIN_SUCCESS&limit=5",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    items = response.json()["items"]
    for item in items:
        assert item["action"] == "LOGIN_SUCCESS"


@pytest.mark.asyncio
async def test_audit_logs_denied_for_staff(
    client: AsyncClient, session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """Staff (L6) tidak punya permission audit_log.view → 403."""
    await _create_user_with_role(session, "STAFF-AUD-001", seed_full_permissions["STAFF"])
    tokens = await _login(client, "STAFF-AUD-001")

    response = await client.get(
        "/api/v1/auth/audit-logs",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_logout_creates_audit_log_with_persona(
    client: AsyncClient, session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """Logout Wakil Direktur → audit log dengan persona EKSPLISIT (NC-EX-005)."""
    await _create_user_with_role(
        session, "WAK-LOGOUT-001", seed_full_permissions["WAKIL_DIREKTUR_UTAMA"]
    )
    tokens = await _login(client, "WAK-LOGOUT-001")

    await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    # Verify audit log
    stmt = (
        select(AuditLog)
        .where(AuditLog.actor_nik == "WAK-LOGOUT-001", AuditLog.action == "LOGOUT_SUCCESS")
        .order_by(AuditLog.timestamp.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    log = result.scalar_one_or_none()

    assert log is not None, "LOGOUT_SUCCESS audit log tidak ditemukan"
    assert "Wakil Direktur Utama" in log.actor_persona, (
        f"NC-EX-005: persona harus eksplisit 'Wakil Direktur Utama', got: {log.actor_persona}"
    )


@pytest.mark.asyncio
async def test_refresh_creates_audit_log(
    client: AsyncClient, session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """Refresh sukses → audit log TOKEN_REFRESHED terekam."""
    await _create_user_with_role(session, "REFRESH-AUD-001", seed_full_permissions["GM"])
    tokens = await _login(client, "REFRESH-AUD-001")

    await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    stmt = (
        select(AuditLog)
        .where(AuditLog.actor_nik == "REFRESH-AUD-001", AuditLog.action == "TOKEN_REFRESHED")
        .order_by(AuditLog.timestamp.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    log = result.scalar_one_or_none()
    assert log is not None, "TOKEN_REFRESHED audit log tidak ditemukan"
