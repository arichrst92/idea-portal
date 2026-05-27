"""Security utilities: password hashing, JWT encode/decode.

TSK-001: stub functions.
TSK-002: real JWT issuing dengan access + refresh token rotation.

Konvensi:
- Access token: 60 menit expiry, claim type="access"
- Refresh token: 7 hari expiry, claim type="refresh", subject = NIK
- Both tokens disigned dengan SECRET_KEY (HS256)
- Refresh token rotation: setiap pakai refresh, issue token PAIR baru
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── Password hashing ────────────────────────────────────────────


def hash_password(plain: str) -> str:
    """Hash password using bcrypt."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain, hashed)


# ─── JWT — access + refresh tokens ───────────────────────────────


class TokenType:
    """JWT token type constants."""

    ACCESS = "access"
    REFRESH = "refresh"


def _create_token(
    subject: str,
    token_type: str,
    expires_in: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Internal helper untuk create JWT dengan type + expiry."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_in,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(
    nik: str,
    user_id: UUID,
    role_codes: list[str] | None = None,
) -> str:
    """Create JWT access token untuk authenticated user.

    Claims:
    - sub: NIK karyawan (subject)
    - user_id: UUID untuk DB lookup tanpa query NIK lagi
    - roles: list role codes untuk RBAC fast-path check (TSK-003)
    - type: "access"
    - exp: now + 60 menit
    """
    return _create_token(
        subject=nik,
        token_type=TokenType.ACCESS,
        expires_in=timedelta(minutes=settings.access_token_expire_minutes),
        extra_claims={
            "user_id": str(user_id),
            "roles": role_codes or [],
        },
    )


def create_refresh_token(nik: str, user_id: UUID) -> str:
    """Create JWT refresh token. Lebih panjang expiry, minimal claims."""
    return _create_token(
        subject=nik,
        token_type=TokenType.REFRESH,
        expires_in=timedelta(days=settings.refresh_token_expire_days),
        extra_claims={"user_id": str(user_id)},
    )


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any] | None:
    """Decode JWT token. Returns None jika invalid/expired/wrong-type.

    Args:
        token: JWT string
        expected_type: jika di-set, reject token dengan type yang beda
                       (mis. tolak refresh token saat expecting access).
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None

    if expected_type is not None and payload.get("type") != expected_type:
        return None

    return payload
