"""Identity domain — business logic untuk auth, user management, RBAC.

Sprint 1 (TSK-001): `authenticate(nik, password)` happy + sad path.
Sprint 1 (TSK-002): real JWT issuing.
Sprint 1 (TSK-003): RBAC permission check.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import verify_password
from app.identity.models import Role, User, UserRole


class AuthenticationError(Exception):
    """Raised saat kredensial invalid atau account locked."""

    def __init__(self, message: str, code: str = "INVALID_CREDENTIALS") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def get_user_by_nik(session: AsyncSession, nik: str) -> User | None:
    """Lookup user by NIK, with roles eagerly loaded.

    Returns None jika tidak ditemukan atau soft-deleted.
    """
    stmt = (
        select(User)
        .where(User.nik == nik, User.deleted_at.is_(None))
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


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
    - ACCOUNT_INACTIVE     — is_active = False (resigned/terminated → NC-SYS-001-04)

    Side effects:
    - Increment failed_login_attempts jika password salah
    - Lock account jika >= 5 failed attempts
    - Reset failed_login_attempts saat sukses
    - Update last_login_at + last_login_ip saat sukses
    """
    user = await get_user_by_nik(session, nik)

    # User tidak ditemukan — return generic error untuk timing-attack safety
    if user is None:
        raise AuthenticationError(
            "NIK atau password tidak valid. Silakan coba lagi.",
            code="INVALID_CREDENTIALS",
        )

    # Account inactive (resigned/terminated) — NC-SYS-001-04
    if not user.is_active:
        raise AuthenticationError(
            "Akun Anda tidak aktif. Hubungi Operation.",
            code="ACCOUNT_INACTIVE",
        )

    # Account locked — NC-SYS-001-01
    if user.is_locked:
        # Cek apakah lock period sudah expire
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
        # Lock setelah 5x failed — NC-SYS-001-01
        if user.failed_login_attempts >= 5:
            user.is_locked = True
            from datetime import timedelta

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
