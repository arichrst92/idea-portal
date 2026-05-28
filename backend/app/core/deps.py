"""FastAPI dependency injection helpers.

TSK-001: DBSession
TSK-002: CurrentUser dari JWT bearer token
TSK-003: RBAC dependency factories — require_permission, require_role, require_level, require_executive
"""

from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenType, decode_token
from app.database import get_db

DBSession = Annotated[AsyncSession, Depends(get_db)]

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    session: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
):
    """Validate JWT + return current user (with roles + permissions eagerly loaded)."""
    # Lazy import untuk hindari circular dependency
    from app.identity.service import get_user_by_id

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "MISSING_TOKEN", "message": "Authorization header tidak ditemukan."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials, expected_type=TokenType.ACCESS)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Token tidak valid atau sudah expired."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("user_id")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Token payload tidak lengkap."},
        )

    try:
        user_id = UUID(user_id_str)
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid user_id format."},
        ) from e

    user = await get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "USER_NOT_FOUND", "message": "User tidak ditemukan."},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCOUNT_INACTIVE", "message": "Akun Anda tidak aktif."},
        )

    return user


CurrentUser = Annotated[object, Depends(get_current_user)]


# ─── RBAC dependency factories (TSK-003) ─────────────────────────


def require_permission(
    permission_code: str,
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """Dependency factory: ensure user punya permission_code.

    Usage:
        @router.post("/employees")
        async def create_employee(
            ...,
            user = Depends(require_permission("employee.create"))
        ):
            ...

    Raises 403 jika permission tidak ada.
    """

    async def _checker(user=Depends(get_current_user)):
        from app.identity.service import user_has_permission

        if not user_has_permission(user, permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PERMISSION_DENIED",
                    "message": f"Anda tidak memiliki permission '{permission_code}'.",
                    "required": permission_code,
                },
            )
        return user

    return _checker


def require_role(
    role_codes: str | list[str],
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """Dependency factory: ensure user punya salah satu role.

    Usage:
        @router.post("/projects/{id}/override-close")
        async def override_close(
            user = Depends(require_role(["DIREKTUR_UTAMA", "WAKIL_DIREKTUR_UTAMA"]))
        ):
            ...
    """
    if isinstance(role_codes, str):
        role_codes_set = {role_codes}
    else:
        role_codes_set = set(role_codes)

    async def _checker(user=Depends(get_current_user)):
        from app.identity.service import user_has_role

        if not user_has_role(user, role_codes_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "ROLE_DENIED",
                    "message": "Role Anda tidak memiliki akses ke endpoint ini.",
                    "required_roles": list(role_codes_set),
                },
            )
        return user

    return _checker


def require_level(min_level: int) -> Callable[..., Coroutine[Any, Any, Any]]:
    """Dependency factory: ensure user level ≤ min_level (lower number = higher authority).

    Usage:
        @router.post("/payroll/run")
        async def run_payroll(
            user = Depends(require_level(3))   # GM (level 3) or higher
        ):
            ...

    Note: Wakil Direktur Utama (encoded level 11) di-treat sebagai level 1.
    """

    async def _checker(user=Depends(get_current_user)):
        from app.identity.service import get_min_user_level

        user_level = get_min_user_level(user)
        if user_level > min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "LEVEL_DENIED",
                    "message": f"Endpoint ini memerlukan minimal level {min_level}.",
                    "user_level": user_level,
                    "required_level": min_level,
                },
            )
        return user

    return _checker


def require_executive() -> Callable[..., Coroutine[Any, Any, Any]]:
    """Dependency factory: ensure user adalah Direktur Utama atau Wakil Direktur Utama.

    Per knowledge.md sec.2: keduanya setara dengan akses Executive Portal.
    Per NC-EX-005: audit log wajib record persona explicit.
    """

    async def _checker(user=Depends(get_current_user)):
        from app.identity.service import is_executive

        if not is_executive(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "EXECUTIVE_ONLY",
                    "message": "Endpoint ini hanya untuk Direktur Utama atau Wakil Direktur Utama.",
                },
            )
        return user

    return _checker
