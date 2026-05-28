"""Tests untuk Employee + Department + Position endpoints — TSK-013 (M1.2)."""

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
from app.organization.models import Department, Position


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


# ─── Seed helpers ──────────────────────────────────────────────────


async def _seed_permissions(session: AsyncSession) -> dict[str, Permission]:
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
    return perm_lookup


async def _seed_roles(session: AsyncSession, perms: dict[str, Permission]) -> dict[str, Role]:
    """Seed 3 roles untuk testing: DIREKTUR_UTAMA, GM, STAFF."""
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

    # Map permissions per role (kalau belum ada)
    for code, role in role_lookup.items():
        for perm_code in ROLE_PERMISSION_MAP.get(code, []):
            perm = perms.get(perm_code)
            if perm is None:
                continue
            existing = await session.execute(
                select(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == perm.id,
                )
            )
            if existing.scalar_one_or_none() is None:
                session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    await session.flush()
    return role_lookup


async def _seed_departments(session: AsyncSession) -> dict[str, Department]:
    DEPT_SPEC = [
        ("TECH", "Teknologi"),
        ("OPS", "Operation"),
        ("SALES", "Sales & Marketing"),
        ("FIN", "Finance & Tax"),
    ]
    depts: dict[str, Department] = {}
    for code, name in DEPT_SPEC:
        existing = await session.execute(select(Department).where(Department.code == code))
        d = existing.scalar_one_or_none()
        if d is None:
            d = Department(code=code, name=name)
            session.add(d)
        depts[code] = d
    await session.flush()
    return depts


async def _seed_positions(
    session: AsyncSession, depts: dict[str, Department]
) -> dict[str, Position]:
    POS_SPEC = [
        ("TECH-DIR", "Director of Technology", "TECH", 2),
        ("TECH-MGR", "Engineering Manager", "TECH", 4),
        ("TECH-ENG", "Engineer", "TECH", 6),
        ("OPS-HR", "HR Staff", "OPS", 6),
    ]
    positions: dict[str, Position] = {}
    for code, name, dept_code, level in POS_SPEC:
        existing = await session.execute(select(Position).where(Position.code == code))
        p = existing.scalar_one_or_none()
        if p is None:
            p = Position(
                code=code,
                name=name,
                department_id=depts[dept_code].id,
                level=level,
            )
            session.add(p)
        positions[code] = p
    await session.flush()
    return positions


async def _create_user_with_role(
    session: AsyncSession, nik: str, role: Role, password: str = "test123"
) -> User:
    existing = await session.execute(select(User).where(User.nik == nik))
    u = existing.scalar_one_or_none()
    if u is not None:
        return u
    u = User(nik=nik, password_hash=hash_password(password), email=f"{nik}@test.local", is_active=True)
    session.add(u)
    await session.flush()
    session.add(UserRole(user_id=u.id, role_id=role.id))
    await session.flush()
    return u


@pytest_asyncio.fixture
async def setup_org(session: AsyncSession):
    """Seed permissions + roles + depts + positions + admin user."""
    perms = await _seed_permissions(session)
    roles = await _seed_roles(session, perms)
    depts = await _seed_departments(session)
    positions = await _seed_positions(session, depts)
    admin = await _create_user_with_role(session, "TEST-ADMIN", roles["DIREKTUR_UTAMA"], "admin123")
    staff = await _create_user_with_role(session, "TEST-STAFF", roles["STAFF"], "staff123")
    await session.commit()
    return {
        "perms": perms,
        "roles": roles,
        "depts": depts,
        "positions": positions,
        "admin": admin,
        "staff": staff,
    }


async def _login(client: AsyncClient, nik: str, password: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"nik": nik, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ─── Department endpoints ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_departments_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/departments")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_departments_returns_seeded(client: AsyncClient, setup_org) -> None:
    token = await _login(client, "TEST-ADMIN", "admin123")
    resp = await client.get("/api/v1/departments", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = resp.json()
    codes = {d["code"] for d in items}
    assert {"TECH", "OPS", "SALES", "FIN"}.issubset(codes)


@pytest.mark.asyncio
async def test_create_department_executive_only(client: AsyncClient, setup_org) -> None:
    """Staff tidak bisa create department — Executive only."""
    token = await _login(client, "TEST-STAFF", "staff123")
    resp = await client.post(
        "/api/v1/departments",
        json={"code": "MARKETING", "name": "Marketing"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "EXECUTIVE_ONLY"


# ─── Position endpoints ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_positions_with_department_name(client: AsyncClient, setup_org) -> None:
    token = await _login(client, "TEST-ADMIN", "admin123")
    resp = await client.get("/api/v1/positions", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = resp.json()
    tech_eng = next((p for p in items if p["code"] == "TECH-ENG"), None)
    assert tech_eng is not None
    assert tech_eng["department_name"] == "Teknologi"
    assert tech_eng["level"] == 6


@pytest.mark.asyncio
async def test_filter_positions_by_department(client: AsyncClient, setup_org) -> None:
    token = await _login(client, "TEST-ADMIN", "admin123")
    tech_dept_id = str(setup_org["depts"]["TECH"].id)
    resp = await client.get(
        f"/api/v1/positions?department_id={tech_dept_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert all(p["department_id"] == tech_dept_id for p in items)


# ─── Employee endpoints ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_employee_success(client: AsyncClient, setup_org) -> None:
    token = await _login(client, "TEST-ADMIN", "admin123")
    dept_id = str(setup_org["depts"]["TECH"].id)
    pos_id = str(setup_org["positions"]["TECH-ENG"].id)

    resp = await client.post(
        "/api/v1/employees",
        json={
            "nik": "TEST-EMP-100",
            "email": "emp100@test.local",
            "full_name": "Test Employee 100",
            "employee_type": "A",
            "status": "PROBATION",
            "department_id": dept_id,
            "position_id": pos_id,
            "joined_date": "2026-05-01",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["nik"] == "TEST-EMP-100"
    assert data["full_name"] == "Test Employee 100"
    assert data["department_name"] == "Teknologi"
    assert data["position_name"] == "Engineer"


@pytest.mark.asyncio
async def test_create_employee_duplicate_nik(client: AsyncClient, setup_org) -> None:
    """NIK sudah dipakai → 409 CONFLICT."""
    token = await _login(client, "TEST-ADMIN", "admin123")
    payload = {
        "nik": "TEST-EMP-DUP",
        "full_name": "Dup Test",
        "employee_type": "A",
        "status": "PROBATION",
    }
    resp1 = await client.post(
        "/api/v1/employees",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        "/api/v1/employees",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 409
    assert resp2.json()["detail"]["code"] == "DUPLICATE_NIK"


@pytest.mark.asyncio
async def test_create_employee_staff_denied(client: AsyncClient, setup_org) -> None:
    """Staff tidak punya employee.create → 403."""
    token = await _login(client, "TEST-STAFF", "staff123")
    resp = await client.post(
        "/api/v1/employees",
        json={
            "nik": "TEST-FAIL",
            "full_name": "Should Fail",
            "employee_type": "A",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_create_employee_invalid_department(client: AsyncClient, setup_org) -> None:
    """department_id tidak exist → 400 INVALID_FK."""
    token = await _login(client, "TEST-ADMIN", "admin123")
    resp = await client.post(
        "/api/v1/employees",
        json={
            "nik": "TEST-EMP-BADFK",
            "full_name": "Bad FK",
            "employee_type": "A",
            "department_id": "00000000-0000-0000-0000-000000000000",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_FK"


@pytest.mark.asyncio
async def test_get_employee_by_nik(client: AsyncClient, setup_org) -> None:
    token = await _login(client, "TEST-ADMIN", "admin123")
    await client.post(
        "/api/v1/employees",
        json={
            "nik": "TEST-EMP-GET",
            "full_name": "Get Me",
            "employee_type": "A",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        "/api/v1/employees/TEST-EMP-GET", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Get Me"


@pytest.mark.asyncio
async def test_get_employee_not_found(client: AsyncClient, setup_org) -> None:
    token = await _login(client, "TEST-ADMIN", "admin123")
    resp = await client.get(
        "/api/v1/employees/NONEXISTENT", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "EMPLOYEE_NOT_FOUND"


@pytest.mark.asyncio
async def test_list_employees_pagination(client: AsyncClient, setup_org) -> None:
    token = await _login(client, "TEST-ADMIN", "admin123")
    # Create 3 employees
    for i in range(3):
        await client.post(
            "/api/v1/employees",
            json={
                "nik": f"TEST-PAGE-{i}",
                "full_name": f"Pager {i}",
                "employee_type": "A",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = await client.get(
        "/api/v1/employees?page=1&page_size=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) <= 2
    assert data["total"] >= 3


@pytest.mark.asyncio
async def test_list_employees_search_by_nik(client: AsyncClient, setup_org) -> None:
    token = await _login(client, "TEST-ADMIN", "admin123")
    await client.post(
        "/api/v1/employees",
        json={
            "nik": "TEST-SEARCH-XYZ",
            "full_name": "Searchable Person",
            "employee_type": "A",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        "/api/v1/employees?q=XYZ",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    niks = {item["nik"] for item in resp.json()["items"]}
    assert "TEST-SEARCH-XYZ" in niks


@pytest.mark.asyncio
async def test_patch_employee(client: AsyncClient, setup_org) -> None:
    token = await _login(client, "TEST-ADMIN", "admin123")
    await client.post(
        "/api/v1/employees",
        json={
            "nik": "TEST-PATCH",
            "full_name": "Original Name",
            "employee_type": "A",
            "status": "PROBATION",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.patch(
        "/api/v1/employees/TEST-PATCH",
        json={"full_name": "Updated Name", "status": "ACTIVE"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["full_name"] == "Updated Name"
    assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_soft_delete_employee(client: AsyncClient, setup_org) -> None:
    token = await _login(client, "TEST-ADMIN", "admin123")
    await client.post(
        "/api/v1/employees",
        json={
            "nik": "TEST-DELETE",
            "full_name": "To Be Deleted",
            "employee_type": "A",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.delete(
        "/api/v1/employees/TEST-DELETE", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ALUMNI"

    # After delete, get should 404 (soft-deleted excluded)
    resp_get = await client.get(
        "/api/v1/employees/TEST-DELETE", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp_get.status_code == 404


# ─── Promote / Mutate ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_promote_employee_success(client: AsyncClient, setup_org) -> None:
    """Promote dari level 6 (Engineer) ke level 4 (Manager) → success."""
    token = await _login(client, "TEST-ADMIN", "admin123")
    pos_eng = str(setup_org["positions"]["TECH-ENG"].id)
    pos_mgr = str(setup_org["positions"]["TECH-MGR"].id)

    await client.post(
        "/api/v1/employees",
        json={
            "nik": "TEST-PROMOTE",
            "full_name": "Promote Me",
            "employee_type": "A",
            "position_id": pos_eng,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.post(
        "/api/v1/employees/TEST-PROMOTE/promote",
        json={
            "new_position_id": pos_mgr,
            "effective_date": "2026-06-01",
            "reason": "Strong performance over 6 months",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["change_type"] == "PROMOTION"
    assert data["before_snapshot"]["position_level"] == 6
    assert data["after_snapshot"]["position_level"] == 4


@pytest.mark.asyncio
async def test_promote_employee_lower_rank_rejected(client: AsyncClient, setup_org) -> None:
    """Promote ke level lebih tinggi (lower rank) → 400."""
    token = await _login(client, "TEST-ADMIN", "admin123")
    pos_mgr = str(setup_org["positions"]["TECH-MGR"].id)
    pos_eng = str(setup_org["positions"]["TECH-ENG"].id)

    await client.post(
        "/api/v1/employees",
        json={
            "nik": "TEST-DEMOTE",
            "full_name": "Cannot Demote via Promote",
            "employee_type": "A",
            "position_id": pos_mgr,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.post(
        "/api/v1/employees/TEST-DEMOTE/promote",
        json={
            "new_position_id": pos_eng,
            "effective_date": "2026-06-01",
            "reason": "Should not be allowed via promote endpoint",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_PROMOTION"


@pytest.mark.asyncio
async def test_mutate_employee_creates_audit(client: AsyncClient, setup_org) -> None:
    """Mutate dari TECH ke OPS → OrgChange entry."""
    token = await _login(client, "TEST-ADMIN", "admin123")
    tech_dept = str(setup_org["depts"]["TECH"].id)
    ops_dept = str(setup_org["depts"]["OPS"].id)

    await client.post(
        "/api/v1/employees",
        json={
            "nik": "TEST-MUTATE",
            "full_name": "Lateral Mover",
            "employee_type": "A",
            "department_id": tech_dept,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.post(
        "/api/v1/employees/TEST-MUTATE/mutate",
        json={
            "new_department_id": ops_dept,
            "effective_date": "2026-06-15",
            "reason": "Lateral move to Operations team",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["change_type"] == "MUTATION"
    assert data["before_snapshot"]["department_id"] == tech_dept
    assert data["after_snapshot"]["department_id"] == ops_dept

    # History should include this change
    history_resp = await client.get(
        "/api/v1/employees/TEST-MUTATE/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) >= 1
    assert history[0]["change_type"] == "MUTATION"
