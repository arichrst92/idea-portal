"""Identity domain — business logic untuk auth, user management, RBAC.

TSK-001: authenticate(nik, password)
TSK-002: issue_token_pair + refresh_token_pair (JWT rotation)
TSK-003: RBAC helpers (user_has_permission, is_executive, get_persona_name)
TSK-005: refresh_token_pair sekarang check blacklist + revoke old token
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
from app.identity import blacklist
from app.identity.models import Role, User, UserRole

settings = get_settings()


class AuthenticationError(Exception):
    """Raised saat kredensial invalid atau account locked."""

    def __init__(
        self,
        message: str,
        code: str = "INVALID_CREDENTIALS",
        locked_until: datetime | None = None,
        remaining_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.locked_until = locked_until
        self.remaining_seconds = remaining_seconds


# ─── User lookup ─────────────────────────────────────────────────


async def get_user_by_nik(session: AsyncSession, nik: str) -> User | None:
    """Lookup user by NIK with roles + permissions eagerly loaded."""
    stmt = (
        select(User)
        .where(User.nik == nik, User.deleted_at.is_(None))
        .options(
            selectinload(User.roles)
            .selectinload(UserRole.role)
            .selectinload(Role.permissions)
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    """Lookup user by UUID with roles + permissions."""
    stmt = (
        select(User)
        .where(User.id == user_id, User.deleted_at.is_(None))
        .options(
            selectinload(User.roles)
            .selectinload(UserRole.role)
            .selectinload(Role.permissions)
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ─── Token issuing ───────────────────────────────────────────────


def issue_token_pair(user: User) -> tuple[str, str]:
    """Issue access + refresh token pair untuk user."""
    role_codes = [ur.role.code for ur in user.roles]
    access = create_access_token(nik=user.nik, user_id=user.id, role_codes=role_codes)
    refresh = create_refresh_token(nik=user.nik, user_id=user.id)
    return access, refresh


async def refresh_token_pair(
    session: AsyncSession, refresh_token: str
) -> tuple[User, str, str]:
    """Rotate refresh token — validate + check blacklist + revoke old + issue new pair.

    TSK-005 changes:
    - Check blacklist before accepting refresh token
    - Revoke old refresh token after issuing new pair (rotation enforcement)
    """
    # Check blacklist first (cheap Redis lookup)
    if await blacklist.is_revoked(refresh_token):
        raise AuthenticationError(
            "Refresh token sudah di-revoke. Silakan login ulang.",
            code="REFRESH_TOKEN_REVOKED",
        )

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

    # Issue new pair, revoke old
    access, refresh = issue_token_pair(user)
    await blacklist.revoke_refresh_token(refresh_token)
    return user, access, refresh


async def logout(refresh_token: str) -> bool:
    """Revoke refresh token at logout. Returns True kalau berhasil."""
    return await blacklist.revoke_refresh_token(refresh_token)


async def unlock_user(session: AsyncSession, user: User) -> User:
    """Admin: unlock account manually. Reset counter + clear lock state."""
    user.is_locked = False
    user.failed_login_attempts = 0
    user.locked_until = None
    await session.commit()
    await session.refresh(user)
    return user


# ─── Authentication ──────────────────────────────────────────────


async def authenticate(
    session: AsyncSession,
    nik: str,
    password: str,
    *,
    client_ip: str | None = None,
) -> User:
    """Authenticate user dengan NIK + password."""
    user = await get_user_by_nik(session, nik)

    if user is None:
        raise AuthenticationError(
            "NIK atau password tidak valid. Silakan coba lagi.",
            code="INVALID_CREDENTIALS",
        )

    if not user.is_active:
        raise AuthenticationError(
            "Akun Anda tidak aktif. Hubungi Operation.",
            code="ACCOUNT_INACTIVE",
        )

    if user.is_locked:
        if user.locked_until and user.locked_until > datetime.now(UTC):
            remaining = int((user.locked_until - datetime.now(UTC)).total_seconds())
            mins = remaining // 60
            raise AuthenticationError(
                f"Account locked due to too many failed attempts. "
                f"Try again in {mins} minute{'s' if mins != 1 else ''} or reset password.",
                code="ACCOUNT_LOCKED",
                locked_until=user.locked_until,
                remaining_seconds=remaining,
            )
        user.is_locked = False
        user.failed_login_attempts = 0
        user.locked_until = None

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

    user.failed_login_attempts = 0
    user.last_login_at = datetime.now(UTC)
    user.last_login_ip = client_ip
    await session.commit()

    return user


# ─── RBAC helpers (TSK-003) ──────────────────────────────────────


def get_user_role_codes(user: User) -> set[str]:
    """Return set role codes yang dimiliki user."""
    return {ur.role.code for ur in user.roles}


def get_user_permissions(user: User) -> set[str]:
    """Compute set semua permissions dari semua roles user."""
    perms: set[str] = set()
    for ur in user.roles:
        for p in ur.role.permissions:
            perms.add(p.code)
    return perms


def user_has_permission(user: User, permission_code: str) -> bool:
    """Cek apakah user punya permission tertentu."""
    return permission_code in get_user_permissions(user)


def user_has_role(user: User, role_codes: str | set[str] | list[str]) -> bool:
    """Cek apakah user punya salah satu role dari role_codes."""
    if isinstance(role_codes, str):
        role_codes = {role_codes}
    elif isinstance(role_codes, list):
        role_codes = set(role_codes)
    user_roles = get_user_role_codes(user)
    return bool(user_roles & role_codes)


def is_executive(user: User) -> bool:
    """True untuk Direktur Utama atau Wakil Direktur Utama."""
    return user_has_role(user, {"DIREKTUR_UTAMA", "WAKIL_DIREKTUR_UTAMA"})


def get_min_user_level(user: User) -> int:
    """Lower number = higher authority. Wakil (level 11) treated as level 1."""
    if not user.roles:
        return 99
    levels = [1 if ur.role.level == 11 else ur.role.level for ur in user.roles]
    return min(levels)


def get_persona_name(user: User) -> str:
    """Get persona name eksplisit untuk audit log (NC-EX-005 critical).

    Format: "Nama Lengkap (Role)" — wajib eksplisit untuk Wakil Direktur.
    """
    top_role: Role | None = None
    for ur in user.roles:
        if top_role is None or ur.role.level < top_role.level:
            top_role = ur.role
        if ur.role.code == "WAKIL_DIREKTUR_UTAMA":
            top_role = ur.role
            break

    role_name = top_role.name if top_role else "—"

    try:
        if user.employee is not None and user.employee.full_name:
            return f"{user.employee.full_name} ({role_name})"
    except Exception:
        pass

    return f"{user.nik} ({role_name})"
