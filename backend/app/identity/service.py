"""Identity domain — business logic untuk auth, user management, RBAC.

TSK-001: authenticate(nik, password)
TSK-002: issue_token_pair + refresh_token_pair (JWT rotation)
TSK-003: RBAC helpers (user_has_permission, is_executive, get_persona_name)
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
from app.identity.models import Permission, Role, User, UserRole

settings = get_settings()


class AuthenticationError(Exception):
    """Raised saat kredensial invalid atau account locked."""

    def __init__(self, message: str, code: str = "INVALID_CREDENTIALS") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


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
    """Rotate refresh token — validate + issue new pair."""
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
            raise AuthenticationError(
                "Account locked due to too many failed attempts. "
                "Try again in 30 minutes or reset password.",
                code="ACCOUNT_LOCKED",
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
    """Compute set semua permissions dari semua roles user.

    Asumsi: user.roles → UserRole.role → Role.permissions sudah eagerly loaded
    (lihat get_user_by_nik / get_user_by_id).
    """
    perms: set[str] = set()
    for ur in user.roles:
        for p in ur.role.permissions:
            perms.add(p.code)
    return perms


def user_has_permission(user: User, permission_code: str) -> bool:
    """Cek apakah user punya permission tertentu (resource.action)."""
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
    """Cek apakah user termasuk Executive (Direktur Utama atau Wakil Direktur Utama).

    Per knowledge.md sec.2: kedua role setara dengan permission identik.
    Wakil Direktur = ROLE TERPISAH (NC-EX-005) tapi punya akses Executive Portal.
    """
    return user_has_role(user, {"DIREKTUR_UTAMA", "WAKIL_DIREKTUR_UTAMA"})


def get_min_user_level(user: User) -> int:
    """Return hierarchy level terendah (= jabatan tertinggi) dari roles user.

    Untuk Wakil Direktur Utama (level 11), return 1 karena setara Direktur Utama
    di sisi authority — meskipun encoded sebagai 11 untuk identification.
    """
    if not user.roles:
        return 99  # No role = lowest authority

    levels = []
    for ur in user.roles:
        # Wakil Direktur Utama (level 11) = treat as level 1 untuk hierarchy check
        levels.append(1 if ur.role.level == 11 else ur.role.level)

    return min(levels)


def get_persona_name(user: User) -> str:
    """Get persona name eksplisit untuk audit log (NC-EX-005 critical).

    Format: "Nama Lengkap (Role)" — wajib eksplisit untuk Wakil Direktur.

    Contoh:
    - "Rudi Atmadja (Direktur Utama)" — bukan generic "Direktur"
    - "Siti Hartono (Wakil Direktur Utama)" — wajib eksplisit
    - "Ari Christian (Manager · Teknologi)" — untuk staff

    Asumsi: user.employee eagerly loaded jika ada (untuk dapat full_name).
    Fallback ke NIK kalau employee record belum ada.
    """
    # Get top role (lowest level number)
    top_role: Role | None = None
    for ur in user.roles:
        if top_role is None or ur.role.level < top_role.level:
            top_role = ur.role
        # Wakil Direktur (level 11) treat as priority equal to Direktur Utama
        if ur.role.code == "WAKIL_DIREKTUR_UTAMA":
            top_role = ur.role
            break

    role_name = top_role.name if top_role else "—"

    # Try get employee.full_name (loaded via relationship)
    # Fallback to NIK kalau employee record belum ada
    try:
        if user.employee is not None and user.employee.full_name:
            return f"{user.employee.full_name} ({role_name})"
    except Exception:
        pass  # Relationship not loaded

    return f"{user.nik} ({role_name})"
