"""Password reset token service via Redis.

TSK-007: simple Redis-based token store.
- POST /auth/forgot-password (NIK) → generate token, store di Redis 1h TTL
- POST /auth/reset-password (token + new_password) → validate, update user

Dev mode: token di-return di response untuk testing (TANPA email integration).
Production: TODO PH4 — kirim via email (SMTP/SES).

Key format: "pwreset:{token}" → user_id (UUID string)
"""

import secrets
from datetime import UTC, datetime
from uuid import UUID

from app.core.redis_client import get_redis

# Token TTL: 1 hour
RESET_TOKEN_TTL_SECONDS = 60 * 60
RESET_KEY_PREFIX = "pwreset:"


def _key(token: str) -> str:
    return f"{RESET_KEY_PREFIX}{token}"


async def issue_reset_token(user_id: UUID) -> tuple[str, datetime]:
    """Generate reset token, store di Redis.

    Returns (token, expires_at).
    """
    # 32 bytes URL-safe random — ~43 chars base64
    token = secrets.token_urlsafe(32)
    redis = get_redis()
    await redis.set(_key(token), str(user_id), ex=RESET_TOKEN_TTL_SECONDS)

    from datetime import timedelta

    expires_at = datetime.now(UTC) + timedelta(seconds=RESET_TOKEN_TTL_SECONDS)
    return token, expires_at


async def validate_reset_token(token: str) -> UUID | None:
    """Validate token, return user_id jika valid (no consumption yet)."""
    redis = get_redis()
    user_id_str = await redis.get(_key(token))
    if user_id_str is None:
        return None
    try:
        return UUID(user_id_str)
    except (ValueError, TypeError):
        return None


async def consume_reset_token(token: str) -> UUID | None:
    """Validate + consume (single-use). Returns user_id jika valid + token sekarang revoked."""
    redis = get_redis()
    user_id_str = await redis.get(_key(token))
    if user_id_str is None:
        return None
    # Delete token (single-use)
    await redis.delete(_key(token))
    try:
        return UUID(user_id_str)
    except (ValueError, TypeError):
        return None
