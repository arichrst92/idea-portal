"""Identity domain — business logic untuk auth, user management, RBAC.

TSK-001: authenticate(nik, password)
TSK-002: issue_token_pair + refresh_token_pair (JWT rotation)
TSK-003: RBAC permission check (next)
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.identity.models import User, UserRole

settings = get_settings()


class AuthenticationError(Exception):
    """Raised saat kredensial invalid atau account locked."""

    def __init__(self, message: str, code: str = "INVALID_CREDENTIALS") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ─── User lookup ─────────────────────────────────────────────────


async def get_user_by_nik(session: AsyncSession, nik: str) -> User | None:
    """Lookup user by NIK with roles eagerly loaded. Returns None jika soft-deleted."""
    stmt = (
        select(User)
        .where(User.nik == nik, User.deleted_at.is_(None))
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    """Lookup user by UUID with roles. Returns None jika soft-deleted."""
    stmt = (
        select(User)
        .where(User.id == user_id, User.deleted_at.is_(None))
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ─── Token issuing ───────────────────────────────────────────────


def issue_token_pair(user: User) -> tuple[str, str]:
    """Issue access + refresh token pair untuk user.

    Returns (access_token, refresh_token).
    """
    role_codes = [ur.role.code for ur in user.roles]
    access = create_access_token(nik=user.nik, user_id=user.id, role_codes=role_codes)
    refresh = create_refresh_token(nik=user.nik, user_id=user.id)
    return access, refresh


async def refresh_token_pair(
    session: AsyncSession, refresh_token: str
) -> tuple[User, str, str]:
    """Rotate refresh token — validate + issue new pair.

    Returns (user, new_access, new_refresh).
    Raises AuthenticationError jika token invalid/expired/wrong-type.
    """
    payload = decode_token(refresh_token, expected_type=TokenType.REFRESH)
    if payload is None:
        raise AuthenticationError(
            "Refresh token invalid atau sudah expired. Silakan login ulang.",
            code="INVALID_REFRESH_TOKEN",
        )

    user_id_str = payload.get("user_id")
    if not user_id_str:
        raise AuthenticationError("Invalid token payload.", code="INVALID_REFRESH_TOKEN")

    try:
        user_id = UUID(user_id_str)
    except (ValueError, TypeError) as e:
        raise AuthenticationError("Invalid user_id format.", code="INVALID_REFRESH_TOKEN") from e

    user = await get_user_by_id(session, user_id)
    if user is None:
        raise AuthenticationError("User tidak ditemukan.", code="USER_NOT_FOUND")
    if not user.is_active:
        raise AuthenticationError(
            "Akun tidak aktif. Silakan hubungi Operation.",
            code="ACCOUNT_INACTIVE",
        )

    access, refresh = issue_token_pair(user)
    return user, access, refresh


# ─── Authentication ──────────────────────────────────────────────


async def authenticate(
    session: AsyncSession,
    nik: str,
    password: str,
    *,
    client_ip: str | None = None,
) -> User:
    """Authenticate user dengan NIK + password.

    Raises AuthenticationError dengan code spesifik:
    - INVALID_CREDENTIALS  — NIK tidak ada atau password salah
    - ACCOUNT_LOCKED       — sudah locked (NC-SYS-001-01: 5x failed = lock 30 min)
    - ACCOUNT_INACTIVE     — is_active=False (NC-SYS-001-04)

    Side effects:
    - Increment failed_login_attempts saat password salah
    - Lock account jika ≥5 failed attempts (30 min)
    - Auto-unlock saat locked_until expired
    - Reset counters + update last_login_at saat sukses
    """
    user = await get_user_by_nik(session, nik)

    # User tidak ditemukan — generic error (timing-attack safety)
    if user is None:
        raise AuthenticationError(
            "NIK atau password tidak valid. Silakan coba lagi.",
            code="INVALID_CREDENTIALS",
        )

    # Account inactive — NC-SYS-001-04
    if not user.is_active:
        raise AuthenticationError(
            "Akun Anda tidak aktif. Hubungi Operation.",
            code="ACCOUNT_INACTIVE",
        )

    # Account locked — NC-SYS-001-01
    if user.is_locked:
        if user.locked_until and user.locked_until > datetime.now(UTC):
            raise AuthenticationError(
                "Account locked due to too many failed attempts. "
                "Try again in 30 minutes or reset password.",
                code="ACCOUNT_LOCKED",
            )
        # Auto-unlock kalau locked_until sudah lewat
        user.is_locked = False
        user.failed_login_attempts = 0
        user.locked_until = None

    # Verify password
    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.is_locked = True
            user.locked_until = datetime.now(UTC) + timedelta(minutes=30)
        await session.commit()
        raise AuthenticationError(
            "NIK atau password tidak valid. Silakan coba lagi.",
            code="INVALID_CREDENTIALS",
        )

    # Success — reset counters, update last_login
    user.failed_login_attempts = 0
    user.last_login_at = datetime.now(UTC)
    user.last_login_ip = client_ip
    await session.commit()

    return user
