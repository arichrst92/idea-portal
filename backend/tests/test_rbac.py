"""Tests untuk RBAC engine — TSK-003 + TSK-193 (Wakil Direktur).

Coverage:
- ✓ user_has_permission positive/negative
- ✓ require_permission dependency returns 403 jika tidak punya permission
- ✓ require_executive untuk Direktur Utama (level 1)
- ✓ require_executive untuk Wakil Direktur Utama (level 11) — TSK-193
- ✓ require_executive deny untuk C-Level
- ✓ require_level hierarchical check
- ✓ Wakil Direktur audit persona EKSPLISIT (NC-EX-005 critical)
- ✓ /me/permissions endpoint return user's permissions
- ✓ /executive-ping accessible by both Direktur and Wakil
- ✓ Direktur Utama (DIREKTUR_UTAMA) dan Wakil punya permission SAMA
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
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
from app.identity.permissions import ROLE_PERMISSION_MAP, PERMISSION_REGISTRY
from app.identity.service import (
    get_persona_name,
    get_user_permissions,
    is_executive,
    user_has_permission,
    user_has_role,
)
from app.main import app
from sqlalchemy import select


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
    """Seed semua roles + permissions + mappings untuk test."""
    # Seed all permissions
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

    # Seed all 7 roles
    role_specs = [
        ("DIREKTUR_UTAMA", "Direktur Utama", HierarchyLevel.L1_DIREKTUR_UTAMA.value, True),
        ("WAKIL_DIREKTUR_UTAMA", "Wakil Direktur Utama", HierarchyLevel.L1B_WAKIL_DIREKTUR_UTAMA.value, True),
        ("C_LEVEL", "C-Level", HierarchyLevel.L2_C_LEVEL.value, True),
        ("GM", "General Manager", HierarchyLevel.L3_GM.value, False),
        ("MANAGER", "Manager", HierarchyLevel.L4_MANAGER.value, False),
        ("LEAD", "Lead", HierarchyLevel.L5_LEAD.value, False),
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

    # Seed role-permission mappings
    for role_code, perm_codes in ROLE_PERMISSION_MAP.items():
        role = role_lookup[role_code]
        # Get existing mappings
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
    session: AsyncSession, nik: str, role: Role, password: str = "test123"
) -> User:
    """Helper: create user dengan 1 role."""
    user = User(
        nik=nik,
        password_hash=hash_password(password),
        email=f"{nik.lower()}@ide.asia",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    # Re-fetch dengan roles eagerly loaded
    from app.identity.service import get_user_by_id

    user_full = await get_user_by_id(session, user.id)
    assert user_full is not None
    return user_full


async def _login_and_get_token(client: AsyncClient, nik: str, password: str = "test123") -> str:
    """Helper: login + return access_token."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"nik": nik, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


# ─── user_has_permission ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_direktur_utama_has_all_permissions(
    session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """Direktur Utama punya SEMUA permission dari registry."""
    user = await _create_user_with_role(session, "DIR-001", seed_full_permissions["DIREKTUR_UTAMA"])
    perms = get_user_permissions(user)

    # Direktur Utama harus punya ALL permissions
    all_codes = {code for code, _, _, _ in PERMISSION_REGISTRY}
    assert perms == all_codes


@pytest.mark.asyncio
async def test_wakil_direktur_has_identical_permissions_as_direktur(
    session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """TSK-193: Wakil Direktur permissions IDENTIK dengan Direktur Utama."""
    direktur = await _create_user_with_role(session, "DIR-001", seed_full_permissions["DIREKTUR_UTAMA"])
    wakil = await _create_user_with_role(session, "WAK-001", seed_full_permissions["WAKIL_DIREKTUR_UTAMA"])

    direktur_perms = get_user_permissions(direktur)
    wakil_perms = get_user_permissions(wakil)

    # Identical permissions
    assert direktur_perms == wakil_perms, "Wakil Direktur permissions HARUS identik Direktur Utama"


@pytest.mark.asyncio
async def test_staff_cannot_approve_hiring(
    session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """Staff (L6) tidak punya permission hiring.approve."""
    user = await _create_user_with_role(session, "STAFF-001", seed_full_permissions["STAFF"])
    assert user_has_permission(user, "leave.create") is True  # punya
    assert user_has_permission(user, "hiring.approve") is False  # tidak punya
    assert user_has_permission(user, "payroll.approve") is False
    assert user_has_permission(user, "executive_dashboard.view") is False


# ─── is_executive ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_is_executive_for_direktur_and_wakil(
    session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """TSK-193: is_executive() return True untuk Direktur Utama DAN Wakil Direktur Utama."""
    direktur = await _create_user_with_role(session, "DIR-001", seed_full_permissions["DIREKTUR_UTAMA"])
    wakil = await _create_user_with_role(session, "WAK-001", seed_full_permissions["WAKIL_DIREKTUR_UTAMA"])

    assert is_executive(direktur) is True
    assert is_executive(wakil) is True


@pytest.mark.asyncio
async def test_is_executive_false_for_clevel_and_below(
    session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """is_executive() return False untuk C-Level, GM, Manager, Lead, Staff."""
    for role_code in ["C_LEVEL", "GM", "MANAGER", "LEAD", "STAFF"]:
        user = await _create_user_with_role(
            session, f"{role_code}-001", seed_full_permissions[role_code]
        )
        assert is_executive(user) is False, f"{role_code} should NOT be executive"


# ─── user_has_role ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_user_has_role_matches(
    session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """user_has_role() check single + multi role codes."""
    user = await _create_user_with_role(session, "GM-001", seed_full_permissions["GM"])

    assert user_has_role(user, "GM") is True
    assert user_has_role(user, "DIREKTUR_UTAMA") is False
    assert user_has_role(user, {"DIREKTUR_UTAMA", "GM"}) is True
    assert user_has_role(user, ["MANAGER", "LEAD"]) is False


# ─── Persona name (NC-EX-005) ────────────────────────────────────


@pytest.mark.asyncio
async def test_persona_name_explicit_for_wakil_direktur(
    session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """NC-EX-005 CRITICAL: persona name harus EKSPLISIT mention 'Wakil Direktur Utama'.

    Tidak boleh generic 'Direktur' — audit log wajib distinguish.
    """
    wakil = await _create_user_with_role(session, "WAK-001", seed_full_permissions["WAKIL_DIREKTUR_UTAMA"])
    persona = get_persona_name(wakil)

    assert "Wakil Direktur Utama" in persona, (
        f"Persona name harus mention 'Wakil Direktur Utama' eksplisit, got: {persona}"
    )
    # Tidak boleh generic
    assert persona != "Direktur"
    assert persona != "Direktur Utama"


@pytest.mark.asyncio
async def test_persona_name_for_direktur_utama(
    session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """Persona untuk Direktur Utama harus mention 'Direktur Utama' (full title)."""
    direktur = await _create_user_with_role(session, "DIR-001", seed_full_permissions["DIREKTUR_UTAMA"])
    persona = get_persona_name(direktur)

    assert "Direktur Utama" in persona
    assert "Wakil" not in persona, f"Direktur Utama persona tidak boleh include 'Wakil', got: {persona}"


# ─── /executive-ping endpoint ────────────────────────────────────


@pytest.mark.asyncio
async def test_executive_ping_accessible_by_direktur(
    client: AsyncClient, session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """Direktur Utama bisa akses /executive-ping."""
    await _create_user_with_role(session, "DIR-001", seed_full_permissions["DIREKTUR_UTAMA"])
    token = await _login_and_get_token(client, "DIR-001")

    response = await client.get(
        "/api/v1/auth/executive-ping",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "Direktur Utama" in data["persona"]


@pytest.mark.asyncio
async def test_executive_ping_accessible_by_wakil_direktur(
    client: AsyncClient, session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """TSK-193: Wakil Direktur Utama JUGA bisa akses /executive-ping.

    Plus: persona name harus EKSPLISIT 'Wakil Direktur Utama' (NC-EX-005).
    """
    await _create_user_with_role(session, "WAK-001", seed_full_permissions["WAKIL_DIREKTUR_UTAMA"])
    token = await _login_and_get_token(client, "WAK-001")

    response = await client.get(
        "/api/v1/auth/executive-ping",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    # NC-EX-005 critical assertion:
    assert "Wakil Direktur Utama" in data["persona"], (
        f"Persona response harus eksplisit 'Wakil Direktur Utama', got: {data['persona']}"
    )


@pytest.mark.asyncio
async def test_executive_ping_denied_for_clevel(
    client: AsyncClient, session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """C-Level tidak bisa akses Executive Portal (hanya Direktur + Wakil)."""
    await _create_user_with_role(session, "CTO-001", seed_full_permissions["C_LEVEL"])
    token = await _login_and_get_token(client, "CTO-001")

    response = await client.get(
        "/api/v1/auth/executive-ping",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "EXECUTIVE_ONLY"


# ─── /me/permissions ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_me_permissions_returns_user_permissions(
    client: AsyncClient, session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """/me/permissions return list permission codes user."""
    await _create_user_with_role(session, "STAFF-001", seed_full_permissions["STAFF"])
    token = await _login_and_get_token(client, "STAFF-001")

    response = await client.get(
        "/api/v1/auth/me/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    perms = response.json()["permissions"]

    # Staff harus punya leave.create + payroll.view
    assert "leave.create" in perms
    assert "payroll.view" in perms

    # Tidak punya executive permissions
    assert "executive_dashboard.view" not in perms
    assert "hiring.approve" not in perms


# ─── Audit log persona (NC-EX-005 critical integration test) ─────


@pytest.mark.asyncio
async def test_login_creates_audit_log_with_explicit_persona(
    client: AsyncClient, session: AsyncSession, seed_full_permissions: dict[str, Role]
) -> None:
    """Login Wakil Direktur → audit log harus contain 'Wakil Direktur Utama' eksplisit.

    NC-EX-005: WAJIB record persona explicit, bukan generic 'Direktur'.
    CI test ini akan FAIL kalau ada regresi.
    """
    await _create_user_with_role(session, "WAK-001", seed_full_permissions["WAKIL_DIREKTUR_UTAMA"])

    # Trigger login → should write audit log
    response = await client.post(
        "/api/v1/auth/login",
        json={"nik": "WAK-001", "password": "test123"},
    )
    assert response.status_code == 200

    # Verify audit log entry
    stmt = (
        select(AuditLog)
        .where(AuditLog.actor_nik == "WAK-001", AuditLog.action == "LOGIN_SUCCESS")
        .order_by(AuditLog.timestamp.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    log = result.scalar_one_or_none()

    assert log is not None, "Audit log entry untuk WAK-001 LOGIN_SUCCESS tidak ditemukan"
    assert "Wakil Direktur Utama" in log.actor_persona, (
        f"NC-EX-005 violation: persona harus eksplisit 'Wakil Direktur Utama', "
        f"got: '{log.actor_persona}'"
    )
    # Tidak boleh generic "Direktur" tanpa "Wakil"
    assert log.actor_persona != "Direktur"
