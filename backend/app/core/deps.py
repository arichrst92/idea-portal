"""FastAPI dependency injection helpers.

TSK-001: DBSession
TSK-002: CurrentUser, OptionalCurrentUser dari JWT bearer token
TSK-003: require_role(level) — RBAC enforcement (next)
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenType, decode_token
from app.database import get_db

DBSession = Annotated[AsyncSession, Depends(get_db)]

# HTTP Bearer scheme — auto-extract token dari Authorization: Bearer <jwt>
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    session: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
):
    """FastAPI dependency: validate JWT + return current user.

    Raises 401 jika:
    - Token tidak ada
    - Token invalid / expired
    - Token bukan type "access" (mis. refresh token tidak boleh dipakai sebagai access)
    - User tidak ditemukan di DB
    - User soft-deleted atau inactive

    Returns: User dengan roles eagerly loaded.
    """
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
        # Per NC-SYS-001-04: terminated/resigned → revoke immediate
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCOUNT_INACTIVE", "message": "Akun Anda tidak aktif."},
        )

    return user


# Lazy-typed annotation untuk avoid circular import di startup
# Usage: async def my_endpoint(user: CurrentUser = ..., db: DBSession = ...)
# (proper type ditambah saat User model di-import eksplisit)
CurrentUser = Annotated[object, Depends(get_current_user)]
