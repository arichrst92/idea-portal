"""Tests untuk global search endpoint — TSK-012."""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.database import async_session_factory
from app.identity.models import (
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
        ("GM", "GM", HierarchyLevel.L3_GM.value, False),
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


async def _create_user(session: AsyncSession, nik: str, email: str, role: Role) -> User:
    user = User(nik=nik, password_hash=hash_password("test123"), email=email, is_active=True)
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
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_search_requires_auth(client: AsyncClient) -> None:
    """Search tanpa Bearer token → 401."""
    response = await client.get("/api/v1/auth/search?q=test")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_search_minimum_query_length(
    client: AsyncClient, session: AsyncSession, seed_full: dict[str, Role]
) -> None:
    """Query < 2 chars → empty results."""
    await _create_user(session, "SRC-001", "src001@ide.asia", seed_full["GM"])
    token = await _login(client, "SRC-001")

    response = await client.get(
        "/api/v1/auth/search?q=a",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["results"] == []


@pytest.mark.asyncio
async def test_gm_can_search_other_users(
    client: AsyncClient, session: AsyncSession, seed_full: dict[str, Role]
) -> None:
    """GM dengan employee.view permission bisa search semua users."""
    await _create_user(session, "GM-SRC-001", "gm@ide.asia", seed_full["GM"])
    await _create_user(session, "TARGET-USER-001", "target@ide.asia", seed_full["STAFF"])

    token = await _login(client, "GM-SRC-001")

    response = await client.get(
        "/api/v1/auth/search?q=TARGET",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    results = response.json()["results"]
    # Cari TARGET-USER-001 di results
    assert any(r["title"] == "TARGET-USER-001" for r in results)


@pytest.mark.asyncio
async def test_staff_can_only_find_self(
    client: AsyncClient, session: AsyncSession, seed_full: dict[str, Role]
) -> None:
    """Staff tanpa employee.view hanya boleh find dirinya sendiri."""
    await _create_user(session, "STAFF-SRC-001", "staff@ide.asia", seed_full["STAFF"])
    await _create_user(session, "TARGET-002", "secret@ide.asia", seed_full["STAFF"])

    token = await _login(client, "STAFF-SRC-001")

    # Search untuk target user lain → tidak ditemukan
    response = await client.get(
        "/api/v1/auth/search?q=TARGET",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert not any(r["title"] == "TARGET-002" for r in results)

    # Search untuk diri sendiri → ketemu
    response2 = await client.get(
        "/api/v1/auth/search?q=STAFF-SRC",
        headers={"Authorization": f"Bearer {token}"},
    )
    results2 = response2.json()["results"]
    assert any(r["title"] == "STAFF-SRC-001" for r in results2)


@pytest.mark.asyncio
async def test_search_by_email(
    client: AsyncClient, session: AsyncSession, seed_full: dict[str, Role]
) -> None:
    """Search match by email."""
    await _create_user(session, "EMAIL-SRC-001", "alice.smith@ide.asia", seed_full["GM"])
    await _create_user(session, "EMAIL-SRC-002", "alice.smith2@ide.asia", seed_full["STAFF"])

    token = await _login(client, "EMAIL-SRC-001")

    response = await client.get(
        "/api/v1/auth/search?q=alice.smith2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    results = response.json()["results"]
    found = next((r for r in results if r["title"] == "EMAIL-SRC-002"), None)
    assert found is not None
    assert "alice.smith2" in found["subtitle"]
