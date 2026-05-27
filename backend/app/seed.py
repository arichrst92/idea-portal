"""Initial database seed — roles + admin user.

Jalankan SEKALI setelah migration:
    uv run python -m app.seed

Buat:
- 8 roles per knowledge.md sec.2 (L1 + L1B + L2-L6 + outsource)
- 1 admin user untuk testing (NIK: ADMIN-001, password: admin123)

⚠️ Untuk production, GANTI password admin via /api/v1/auth/change-password setelah login pertama.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.database import async_session_factory
from app.identity.models import HierarchyLevel, Role, User, UserRole


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
    """Insert 7 roles jika belum ada. Returns dict {code: Role}."""
    roles = {}
    for spec in ROLES_SEED:
        existing = await session.execute(select(Role).where(Role.code == spec["code"]))
        role = existing.scalar_one_or_none()
        if role is None:
            role = Role(**spec)
            session.add(role)
            print(f"  + Role: {spec['code']:30} (level {spec['level']})")
        else:
            print(f"  = Role: {spec['code']:30} already exists")
        roles[spec["code"]] = role
    await session.commit()
    return roles


async def seed_admin_user(session: AsyncSession, admin_role: Role) -> None:
    """Insert 1 admin user untuk testing."""
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
    await session.flush()  # Get user.id

    # Assign Direktur Utama role
    user_role = UserRole(user_id=user.id, role_id=admin_role.id)
    session.add(user_role)
    await session.commit()
    print(f"  + User: {nik} | password: admin123 | role: {admin_role.code}")
    print()
    print("  ⚠️  GANTI PASSWORD VIA /api/v1/auth/change-password SETELAH LOGIN PERTAMA")


async def main() -> None:
    print("━━━ IDEA Portal — Database Seed ━━━\n")
    async with async_session_factory() as session:
        print("Seeding roles...")
        roles = await seed_roles(session)

        print("\nSeeding admin user...")
        await seed_admin_user(session, roles["DIREKTUR_UTAMA"])

    print("\n✓ Seed complete.")
    print("\nTest login:")
    print("  curl -X POST http://localhost:8000/api/v1/auth/login \\")
    print("    -H 'Content-Type: application/json' \\")
    print('    -d \'{"nik":"ADMIN-001","password":"admin123"}\'')


if __name__ == "__main__":
    asyncio.run(main())
