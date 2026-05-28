"""JWT token blacklist — Redis-backed.

TSK-005: Revoke refresh tokens saat logout supaya tidak bisa dipakai lagi.
Access token TIDAK di-blacklist (short-lived, expire 60 min). Untuk force-revoke
access immediate, gunakan user.is_active=False (NC-SYS-001-04 sudah enforce).

Key format:
- "bl:refresh:{jti}" → "1" (with TTL = sisa expiry refresh token)

Karena kita pakai HS256 tanpa JTI claim, kita pakai SHA256 dari refresh token
sebagai key (fungsi 1-way, tidak leak token content).
"""

import hashlib
from datetime import UTC, datetime

from app.core.redis_client import get_redis
from app.core.security import TokenType, decode_token


def _token_key(token: str) -> str:
    """Hash token jadi short key untuk Redis (avoid storing full JWT)."""
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]
    return f"bl:refresh:{digest}"


async def revoke_refresh_token(refresh_token: str) -> bool:
    """Add refresh token ke blacklist. Returns True kalau berhasil revoke.

    TTL otomatis di-set ke sisa expiry token (no garbage in Redis).
    """
    payload = decode_token(refresh_token, expected_type=TokenType.REFRESH)
    if payload is None:
        # Token invalid/expired — no-op (treat as already revoked)
        return False

    exp_ts = payload.get("exp")
    if exp_ts is None:
        return False

    # TTL = sisa detik sampai expiry
    remaining = int(exp_ts - datetime.now(UTC).timestamp())
    if remaining <= 0:
        return False  # Already expired

    redis = get_redis()
    await redis.set(_token_key(refresh_token), "1", ex=remaining)
    return True


async def is_revoked(refresh_token: str) -> bool:
    """Cek apakah refresh token sudah di-blacklist."""
    redis = get_redis()
    return await redis.exists(_token_key(refresh_token)) > 0
