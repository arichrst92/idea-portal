"""Initial database seed — roles + permissions + role-permission mapping + admin user.

Jalankan SEKALI setelah migration:
    uv run python -m app.seed

Idempotent: aman dijalankan berulang, hanya tambah yang belum ada.

Buat:
- 7 roles per knowledge.md sec.2 (L1 Direktur + L1B Wakil Direktur + L2-L6)
- ~50 permissions per app/identity/permissions.py
- Role-permission mapping per ROLE_PERMISSION_MAP
- 1 admin user untuk testing (NIK: ADMIN-001, password: admin123)
"""

import asyncio

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

# Register semua domain models supaya mapper config resolve relationship cross-domain
# (User.employee → Employee, dst). Tanpa ini SQLAlchemy raise InvalidRequestError.
from app.organization import models as _organization_models  # noqa: F401
from app.assessment import models as _assessment_models  # noqa: F401
from app.project import models as _project_models  # noqa: F401
from app.outsource import models as _outsource_models  # noqa: F401
from app.payroll import models as _payroll_models  # noqa: F401
from app.sales import models as _sales_models  # noqa: F401


# ─── Roles ───────────────────────────────────────────────────────
ROLES_SEED = [
    {
        "code": "DIREKTUR_UTAMA",
        "name": "Direktur Utama",
        "level": HierarchyLevel.L1_DIREKTUR_UTAMA.value,
        "description": "Chief executive — wewenang tertinggi, override semua keputusan",
        "is_executive": True,
    },
    {
        "code": "WAKIL_DIREKTUR_UTAMA",
        "name": "Wakil Direktur Utama",
        "level": HierarchyLevel.L1B_WAKIL_DIREKTUR_UTAMA.value,
        "description": "Permission identik Direktur Utama dengan audit identity terpisah (NC-EX-005)",
        "is_executive": True,
    },
    {
        "code": "C_LEVEL",
        "name": "C-Level",
        "level": HierarchyLevel.L2_C_LEVEL.value,
        "description": "CTO, COO, CMO, CFO",
        "is_executive": True,
    },
    {
        "code": "GM",
        "name": "General Manager",
        "level": HierarchyLevel.L3_GM.value,
        "description": "Head of department",
        "is_executive": False,
    },
    {
        "code": "MANAGER",
        "name": "Manager",
        "level": HierarchyLevel.L4_MANAGER.value,
        "description": "Mid-management",
        "is_executive": False,
    },
    {
        "code": "LEAD",
        "name": "Lead",
        "level": HierarchyLevel.L5_LEAD.value,
        "description": "Team lead",
        "is_executive": False,
    },
    {
        "code": "STAFF",
        "name": "Staff",
        "level": HierarchyLevel.L6_STAFF.value,
        "description": "Karyawan staff level (L6)",
        "is_executive": False,
    },
]


async def seed_roles(session: AsyncSession) -> dict[str, Role]:
    """Insert 7 roles. Idempotent."""
    roles = {}
    for spec in ROLES_SEED:
        existing = await session.execute(select(Role).where(Role.code == spec["code"]))
        role = existing.scalar_one_or_none()
        if role is None:
            role = Role(**spec)
            session.add(role)
            print(f"  + Role: {spec['code']:25} (level {spec['level']})")
        else:
            print(f"  = Role: {spec['code']:25} already exists")
        roles[spec["code"]] = role
    await session.commit()
    # Refresh untuk dapat ID
    for role in roles.values():
        await session.refresh(role)
    return roles


async def seed_permissions(session: AsyncSession) -> dict[str, Permission]:
    """Insert all permissions dari PERMISSION_REGISTRY. Idempotent."""
    perms = {}
    new_count = 0
    for code, resource, action, description in PERMISSION_REGISTRY:
        existing = await session.execute(select(Permission).where(Permission.code == code))
        p = existing.scalar_one_or_none()
        if p is None:
            p = Permission(
                code=code,
                resource=resource.value,
                action=action.value,
                description=description,
            )
            session.add(p)
            new_count += 1
        perms[code] = p
    await session.commit()
    for p in perms.values():
        await session.refresh(p)
    print(f"  + {new_count} new permissions added (total registry: {len(PERMISSION_REGISTRY)})")
    return perms


async def seed_role_permissions(
    session: AsyncSession,
    roles: dict[str, Role],
    perms: dict[str, Permission],
) -> None:
    """Map roles → permissions per ROLE_PERMISSION_MAP. Idempotent."""
    total_new = 0
    for role_code, permission_codes in ROLE_PERMISSION_MAP.items():
        role = roles.get(role_code)
        if role is None:
            print(f"  ⚠️  Role {role_code} not found, skipping")
            continue

        # Get existing mappings untuk role ini
        stmt = select(RolePermission).where(RolePermission.role_id == role.id)
        existing_result = await session.execute(stmt)
        existing_perm_ids = {rp.permission_id for rp in existing_result.scalars().all()}

        new_for_role = 0
        for perm_code in permission_codes:
            perm = perms.get(perm_code)
            if perm is None:
                continue
            if perm.id in existing_perm_ids:
                continue
            session.add(RolePermission(role_id=role.id, permission_id=perm.id))
            new_for_role += 1

        if new_for_role > 0:
            print(f"  + {role_code:25} → +{new_for_role} permissions (total: {len(permission_codes)})")
            total_new += new_for_role
        else:
            print(f"  = {role_code:25} → {len(permission_codes)} permissions (already mapped)")

    await session.commit()
    print(f"  Total new role-permission links: {total_new}")


async def seed_admin_user(session: AsyncSession, admin_role: Role) -> None:
    """Insert 1 admin user untuk testing. Idempotent."""
    nik = "ADMIN-001"
    existing = await session.execute(select(User).where(User.nik == nik))
    user = existing.scalar_one_or_none()
    if user is not None:
        print(f"  = User: {nik} already exists, skipping")
        return

    user = User(
        nik=nik,
        password_hash=hash_password("admin123"),
        email="admin@ide.asia",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    user_role = UserRole(user_id=user.id, role_id=admin_role.id)
    session.add(user_role)
    await session.commit()
    print(f"  + User: {nik} | password: admin123 | role: {admin_role.code}")
    print()
    print("  ⚠️  GANTI PASSWORD VIA /api/v1/auth/change-password SETELAH LOGIN PERTAMA")


async def seed_departments(session: AsyncSession) -> dict[str, "Department"]:
    """Seed 4 dept utama per knowledge.md sec.3. Idempotent."""
    from app.organization.models import Department

    DEPT_SEED = [
        {"code": "TECH", "name": "Teknologi", "description": "Engineering, IT, Product"},
        {"code": "OPS", "name": "Operation", "description": "Operations, HR, Admin"},
        {"code": "SALES", "name": "Sales & Marketing", "description": "Sales, Marketing, BD"},
        {"code": "FIN", "name": "Finance & Tax", "description": "Finance, Accounting, Tax"},
    ]
    depts: dict[str, Department] = {}
    for spec in DEPT_SEED:
        existing = await session.execute(select(Department).where(Department.code == spec["code"]))
        d = existing.scalar_one_or_none()
        if d is None:
            d = Department(**spec)
            session.add(d)
            print(f"  + Department: {spec['code']:8} ({spec['name']})")
        else:
            print(f"  = Department: {spec['code']:8} (exists)")
        depts[spec["code"]] = d
    await session.commit()
    for d in depts.values():
        await session.refresh(d)
    return depts


async def seed_positions(session: AsyncSession, depts: dict[str, "Department"]) -> int:
    """Seed beberapa position default per dept. Idempotent."""
    from app.organization.models import Position

    POSITION_SEED = [
        # Tech
        {"code": "TECH-DIR", "name": "Director of Technology", "dept": "TECH", "level": 2},
        {"code": "TECH-GM", "name": "GM Engineering", "dept": "TECH", "level": 3},
        {"code": "TECH-MGR", "name": "Engineering Manager", "dept": "TECH", "level": 4},
        {"code": "TECH-LEAD", "name": "Tech Lead", "dept": "TECH", "level": 5},
        {"code": "TECH-ENG", "name": "Engineer", "dept": "TECH", "level": 6},
        # Ops
        {"code": "OPS-GM", "name": "GM Operations", "dept": "OPS", "level": 3},
        {"code": "OPS-MGR", "name": "Operations Manager", "dept": "OPS", "level": 4},
        {"code": "OPS-HR", "name": "HR Staff", "dept": "OPS", "level": 6},
        # Sales
        {"code": "SALES-GM", "name": "GM Sales & Marketing", "dept": "SALES", "level": 3},
        {"code": "SALES-MGR", "name": "Sales Manager", "dept": "SALES", "level": 4},
        {"code": "SALES-EXEC", "name": "Sales Executive", "dept": "SALES", "level": 6},
        # Finance
        {"code": "FIN-GM", "name": "GM Finance & Tax", "dept": "FIN", "level": 3},
        {"code": "FIN-MGR", "name": "Finance Manager", "dept": "FIN", "level": 4},
        {"code": "FIN-STAFF", "name": "Finance Staff", "dept": "FIN", "level": 6},
    ]
    created = 0
    for spec in POSITION_SEED:
        existing = await session.execute(select(Position).where(Position.code == spec["code"]))
        if existing.scalar_one_or_none() is not None:
            continue
        pos = Position(
            code=spec["code"],
            name=spec["name"],
            department_id=depts[spec["dept"]].id,
            level=spec["level"],
        )
        session.add(pos)
        created += 1
    await session.commit()
    if created > 0:
        print(f"  + {created} positions seeded")
    else:
        print("  = All positions already exist")
    return created


async def main() -> None:
    print("━━━ IDEA Portal — Database Seed ━━━\n")
    async with async_session_factory() as session:
        print("Seeding roles...")
        roles = await seed_roles(session)

        print("\nSeeding permissions...")
        perms = await seed_permissions(session)

        print("\nSeeding role-permission mapping...")
        await seed_role_permissions(session, roles, perms)

        print("\nSeeding admin user...")
        await seed_admin_user(session, roles["DIREKTUR_UTAMA"])

        print("\nSeeding departments...")
        depts = await seed_departments(session)

        print("\nSeeding positions...")
        await seed_positions(session, depts)

    print("\n✓ Seed complete.")
    print("\nTest login:")
    print("  curl -X POST http://localhost:8000/api/v1/auth/login \\")
    print("    -H 'Content-Type: application/json' \\")
    print('    -d \'{"nik":"ADMIN-001","password":"admin123"}\'')


if __name__ == "__main__":
    asyncio.run(main())
