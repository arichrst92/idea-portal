"""Admin endpoints untuk role-permission matrix management — TSK-004.

Endpoints (require_executive — Direktur Utama / Wakil Direktur Utama only):
- GET    /admin/permissions/matrix         — return role × permission matrix
- GET    /admin/permissions                — list semua permissions
- GET    /admin/roles                      — list semua roles dengan permissions
- PATCH  /admin/roles/{role_id}/permissions — toggle permission untuk role
- POST   /admin/roles                      — create custom role (future)

Semua perubahan diaudit dengan persona eksplisit (NC-EX-005).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import audit_log
from app.core.deps import DBSession, require_executive
from app.identity.models import Permission, Role, RolePermission, User

router = APIRouter(prefix="/admin", tags=["admin"])


# ─── Schemas ─────────────────────────────────────────────────────


class PermissionItem(BaseModel):
    """Single permission row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    resource: str
    action: str
    description: str | None


class RoleItem(BaseModel):
    """Single role row dengan permission IDs."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    level: int
    is_executive: bool
    description: str | None
    permission_ids: list[UUID] = Field(default_factory=list)


class PermissionMatrix(BaseModel):
    """Full matrix: list semua permissions + roles + role-permission mappings."""

    permissions: list[PermissionItem]
    roles: list[RoleItem]


class TogglePermissionRequest(BaseModel):
    """PATCH /admin/roles/{role_id}/permissions body."""

    permission_code: str = Field(..., description="Code permission yang di-toggle")
    grant: bool = Field(..., description="True untuk grant, False untuk revoke")


# ─── Endpoints ───────────────────────────────────────────────────


@router.get(
    "/permissions/matrix",
    response_model=PermissionMatrix,
    status_code=status.HTTP_200_OK,
    summary="Get full permission matrix (Executive only)",
)
async def get_permission_matrix(
    session: DBSession,
    _user: User = Depends(require_executive()),
) -> PermissionMatrix:
    """Return matrix lengkap: semua permissions + roles + mappings."""
    # Load all permissions
    perm_stmt = select(Permission).order_by(Permission.resource, Permission.action)
    perm_result = await session.execute(perm_stmt)
    permissions = [PermissionItem.model_validate(p) for p in perm_result.scalars().all()]

    # Load all roles with permission relationships eagerly
    role_stmt = (
        select(Role)
        .order_by(Role.level)
        .options(selectinload(Role.permissions))
    )
    role_result = await session.execute(role_stmt)
    roles_data = []
    for role in role_result.scalars().all():
        roles_data.append(
            RoleItem(
                id=role.id,
                code=role.code,
                name=role.name,
                level=role.level,
                is_executive=role.is_executive,
                description=role.description,
                permission_ids=[p.id for p in role.permissions],
            )
        )

    return PermissionMatrix(permissions=permissions, roles=roles_data)


@router.patch(
    "/roles/{role_id}/permissions",
    status_code=status.HTTP_200_OK,
    summary="Grant atau revoke permission untuk role (Executive only)",
    description=(
        "Toggle single permission untuk role. Selalu audit-logged dengan persona explicit. "
        "Mengubah permission Direktur/Wakil Direktur Utama secara default dilarang "
        "(prevent lock-out scenario)."
    ),
)
async def toggle_role_permission(
    role_id: UUID,
    payload: TogglePermissionRequest,
    request: Request,
    session: DBSession,
    current_user: User = Depends(require_executive()),
) -> dict[str, str]:
    """PATCH /admin/roles/{role_id}/permissions — grant/revoke single permission."""
    client_ip = request.client.host if request.client else None

    # Lookup role
    role = await session.get(Role, role_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ROLE_NOT_FOUND", "message": f"Role {role_id} not found."},
        )

    # Lock out prevention: jangan boleh revoke permission core dari Direktur Utama / Wakil
    if role.code in ("DIREKTUR_UTAMA", "WAKIL_DIREKTUR_UTAMA") and not payload.grant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CANNOT_REVOKE_EXECUTIVE",
                "message": (
                    "Tidak boleh revoke permission dari Direktur Utama atau Wakil Direktur Utama "
                    "untuk mencegah lock-out scenario. Kalau yakin, modify via database direct."
                ),
            },
        )

    # Lookup permission
    perm_stmt = select(Permission).where(Permission.code == payload.permission_code)
    perm_result = await session.execute(perm_stmt)
    permission = perm_result.scalar_one_or_none()
    if permission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PERMISSION_NOT_FOUND", "message": f"Permission '{payload.permission_code}' not found."},
        )

    # Cek existing mapping
    rp_stmt = select(RolePermission).where(
        RolePermission.role_id == role.id,
        RolePermission.permission_id == permission.id,
    )
    existing = (await session.execute(rp_stmt)).scalar_one_or_none()

    if payload.grant:
        if existing is None:
            session.add(RolePermission(role_id=role.id, permission_id=permission.id))
            action_str = "PERMISSION_GRANTED"
            result_msg = f"Permission '{payload.permission_code}' di-grant ke role '{role.code}'."
        else:
            action_str = "PERMISSION_ALREADY_GRANTED"
            result_msg = f"Permission '{payload.permission_code}' sudah ada di role '{role.code}' (no-op)."
    else:
        if existing is not None:
            await session.delete(existing)
            action_str = "PERMISSION_REVOKED"
            result_msg = f"Permission '{payload.permission_code}' di-revoke dari role '{role.code}'."
        else:
            action_str = "PERMISSION_ALREADY_REVOKED"
            result_msg = f"Permission '{payload.permission_code}' tidak ada di role '{role.code}' (no-op)."

    await session.commit()

    # Audit log dengan persona explicit (NC-EX-005)
    await audit_log(
        session,
        actor=current_user,
        action=action_str,
        resource_type="role_permission",
        resource_id=f"{role.code}:{payload.permission_code}",
        ip_address=client_ip,
        before_state={"granted": existing is not None},
        after_state={"granted": payload.grant if existing is None or payload.grant else False},
        notes=result_msg,
        commit=True,
    )

    return {"message": result_msg, "action": action_str}
