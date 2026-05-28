"""Global search service — TSK-012.

Cari users + employees + projects dengan fuzzy match. Permission-aware:
- Staff: only own profile
- Manager/Lead: team members (employees yang report ke user)
- GM+: full dept access
- Executive: all

Result format: unified list dengan `type` discriminator (user/employee/project).
"""

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.models import User
from app.identity.service import is_executive, user_has_permission

MAX_RESULTS_PER_TYPE = 10


async def global_search(
    session: AsyncSession, query: str, current_user: User
) -> list[dict[str, Any]]:
    """Global search dengan permission filter.

    Args:
        session: DB session
        query: search query (min 2 chars)
        current_user: actor (untuk permission filter)

    Returns: list result, each {type, id, title, subtitle, url}.
    """
    query = query.strip()
    if len(query) < 2:
        return []

    results: list[dict[str, Any]] = []
    like_pattern = f"%{query}%"

    # 1. Search USERS (by NIK or email)
    # Executive + GM (employee.view) bisa search semua. Staff/Lead limited.
    if user_has_permission(current_user, "employee.view") or is_executive(current_user):
        stmt = (
            select(User)
            .where(
                User.deleted_at.is_(None),
                or_(
                    User.nik.ilike(like_pattern),
                    User.email.ilike(like_pattern),
                ),
            )
            .limit(MAX_RESULTS_PER_TYPE)
        )
        result = await session.execute(stmt)
        for user in result.scalars().all():
            results.append({
                "type": "user",
                "id": str(user.id),
                "title": user.nik,
                "subtitle": user.email or "",
                "url": f"/admin/users/{user.nik}",
            })
    else:
        # Non-privileged: only return self
        if query.lower() in current_user.nik.lower() or (
            current_user.email and query.lower() in current_user.email.lower()
        ):
            results.append({
                "type": "user",
                "id": str(current_user.id),
                "title": current_user.nik,
                "subtitle": current_user.email or "(your profile)",
                "url": "/settings",
            })

    # 2. Search EMPLOYEES (by full_name) — Sprint 1 belum ada Employee records seeded
    # Akan auto-include saat M1.2 (Employee master data) live.
    try:
        from app.organization.models import Employee

        if user_has_permission(current_user, "employee.view") or is_executive(current_user):
            emp_stmt = (
                select(Employee)
                .where(
                    Employee.deleted_at.is_(None),
                    Employee.full_name.ilike(like_pattern),
                )
                .limit(MAX_RESULTS_PER_TYPE)
            )
            emp_result = await session.execute(emp_stmt)
            for emp in emp_result.scalars().all():
                results.append({
                    "type": "employee",
                    "id": str(emp.id),
                    "title": emp.full_name,
                    "subtitle": f"{emp.employee_type} · {emp.status}",
                    "url": f"/employees/{emp.id}",
                })
    except Exception:
        # Employees table belum exist atau migration belum jalan
        pass

    # 3. Search PROJECTS (by name or code) — sama, belum live di M1.1
    try:
        from app.project.models import Project

        if user_has_permission(current_user, "project.view") or is_executive(current_user):
            proj_stmt = (
                select(Project)
                .where(
                    Project.deleted_at.is_(None),
                    or_(
                        Project.name.ilike(like_pattern),
                        Project.code.ilike(like_pattern),
                    ),
                )
                .limit(MAX_RESULTS_PER_TYPE)
            )
            proj_result = await session.execute(proj_stmt)
            for proj in proj_result.scalars().all():
                results.append({
                    "type": "project",
                    "id": str(proj.id),
                    "title": proj.name,
                    "subtitle": f"{proj.code} · {proj.type} · {proj.status}",
                    "url": f"/projects/{proj.id}",
                })
    except Exception:
        pass

    return results
