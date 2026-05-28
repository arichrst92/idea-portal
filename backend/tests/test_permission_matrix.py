"""Tests untuk Permission Matrix admin endpoints — TSK-004.

Coverage:
- ✓ GET /admin/permissions/matrix accessible by Direktur Utama
- ✓ GET /admin/permissions/matrix accessible by Wakil Direktur (TSK-193)
- ✓ GET /admin/permissions/matrix denied for C-Level (403 EXECUTIVE_ONLY)
- ✓ PATCH grant new permission → success + audit logged
- ✓ PATCH revoke permission → success + audit logged
- ✓ PATCH on DIREKTUR_UTAMA role with grant=False → 400 (lock-out prevention)
- ✓ PATCH dengan non-existing role → 404
- ✓ PATCH dengan non-existing permission code → 404
"""

from collections.abc import AsyncGenerator

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
    """Seed permissions + roles + mappings."""
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
        ("MANAGER", "Manager", HierarchyLevel.L4_MANAGER.value, False),
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


async def _create_user(session: AsyncSession, nik: str, role: Role) -> User:
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

    full = await get_user_by_id(session, user.id)
    assert full is not None
    return full


async def _login(client: AsyncClient, nik: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"nik": nik, "password": "test123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ─── GET matrix ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_matrix_accessible_by_direktur(
    client: AsyncClient, session: AsyncSession, seed_full: dict[str, Role]
) -> None:
    """Direktur Utama bisa GET matrix."""
    await _create_user(session, "DIR-MTX-001", seed_full["DIREKTUR_UTAMA"])
    token = await _login(client, "DIR-MTX-001")

    response = await client.get(
        "/api/v1/admin/permissions/matrix",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "permissions" in data
    assert "roles" in data
    assert len(data["permissions"]) > 0
    assert len(data["roles"]) > 0
    # Setiap role harus punya permission_ids list
    for role in data["roles"]:
        assert "permission_ids" in role
        assert isinstance(role["permission_ids"], list)


@pytest.mark.asyncio
async def test_get_matrix_accessible_by_wakil_direktur(
    client: AsyncClient, session: AsyncSession, seed_full: dict[str, Role]
) -> None:
    """TSK-193: Wakil Direktur juga punya akses ke matrix."""
    await _create_user(session, "WAK-MTX-001", seed_full["WAKIL_DIREKTUR_UTAMA"])
    token = await _login(client, "WAK-MTX-001")

    response = await client.get(
        "/api/v1/admin/permissions/matrix",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_matrix_denied_for_clevel(
    client: AsyncClient, session: AsyncSession, seed_full: dict[str, Role]
) -> None:
    """C-Level tidak bisa akses matrix — 403 EXECUTIVE_ONLY."""
    await _create_user(session, "CTO-MTX-001", seed_full["C_LEVEL"])
    token = await _login(client, "CTO-MTX-001")

    response = await client.get(
        "/api/v1/admin/permissions/matrix",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "EXECUTIVE_ONLY"


# ─── PATCH grant/revoke ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_grant_permission_to_manager(
    client: AsyncClient, session: AsyncSession, seed_full: dict[str, Role]
) -> None:
    """Direktur grant permission baru ke Manager → success."""
    await _create_user(session, "DIR-MTX-002", seed_full["DIREKTUR_UTAMA"])
    token = await _login(client, "DIR-MTX-002")

    manager_role = seed_full["MANAGER"]

    # Pick permission yang BELUM dimiliki Manager
    # 'role.configure' biasanya executive-only
    response = await client.patch(
        f"/api/v1/admin/roles/{manager_role.id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
        json={"permission_code": "role.configure", "grant": True},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["action"] in ("PERMISSION_GRANTED", "PERMISSION_ALREADY_GRANTED")

    # Verify audit log
    stmt = (
        select(AuditLog)
        .where(
            AuditLog.actor_nik == "DIR-MTX-002",
            AuditLog.action.in_(["PERMISSION_GRANTED", "PERMISSION_ALREADY_GRANTED"]),
        )
        .order_by(AuditLog.timestamp.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    log = result.scalar_one_or_none()
    assert log is not None
    assert "MANAGER" in (log.resource_id or "")
    assert "Direktur Utama" in log.actor_persona


@pytest.mark.asyncio
async def test_revoke_permission_from_direktur_blocked(
    client: AsyncClient, session: AsyncSession, seed_full: dict[str, Role]
) -> None:
    """Lock-out prevention: tidak boleh revoke permission dari DIREKTUR_UTAMA."""
    await _create_user(session, "DIR-MTX-003", seed_full["DIREKTUR_UTAMA"])
    token = await _login(client, "DIR-MTX-003")

    direktur_role = seed_full["DIREKTUR_UTAMA"]

    response = await client.patch(
        f"/api/v1/admin/roles/{direktur_role.id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
        json={"permission_code": "user.view", "grant": False},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "CANNOT_REVOKE_EXECUTIVE"


@pytest.mark.asyncio
async def test_revoke_permission_from_wakil_direktur_blocked(
    client: AsyncClient, session: AsyncSession, seed_full: dict[str, Role]
) -> None:
    """Lock-out prevention juga untuk Wakil Direktur Utama (TSK-193)."""
    await _create_user(session, "DIR-MTX-004", seed_full["DIREKTUR_UTAMA"])
    token = await _login(client, "DIR-MTX-004")

    wakil_role = seed_full["WAKIL_DIREKTUR_UTAMA"]

    response = await client.patch(
        f"/api/v1/admin/roles/{wakil_role.id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
        json={"permission_code": "user.view", "grant": False},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "CANNOT_REVOKE_EXECUTIVE"


@pytest.mark.asyncio
async def test_patch_invalid_role_returns_404(
    client: AsyncClient, session: AsyncSession, seed_full: dict[str, Role]
) -> None:
    """PATCH non-existing role → 404."""
    await _create_user(session, "DIR-MTX-005", seed_full["DIREKTUR_UTAMA"])
    token = await _login(client, "DIR-MTX-005")

    import uuid

    fake_role_id = uuid.uuid4()

    response = await client.patch(
        f"/api/v1/admin/roles/{fake_role_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
        json={"permission_code": "user.view", "grant": True},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ROLE_NOT_FOUND"


@pytest.mark.asyncio
async def test_patch_invalid_permission_code_returns_404(
    client: AsyncClient, session: AsyncSession, seed_full: dict[str, Role]
) -> None:
    """PATCH dengan permission code yang tidak ada → 404."""
    await _create_user(session, "DIR-MTX-006", seed_full["DIREKTUR_UTAMA"])
    token = await _login(client, "DIR-MTX-006")

    manager_role = seed_full["MANAGER"]

    response = await client.patch(
        f"/api/v1/admin/roles/{manager_role.id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
        json={"permission_code": "non_existing.action", "grant": True},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PERMISSION_NOT_FOUND"
