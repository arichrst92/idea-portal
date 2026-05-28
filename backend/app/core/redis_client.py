"""Async Redis connection — singleton dipakai untuk token blacklist + cache.

Connection di-init lazy. Disposed di FastAPI lifespan shutdown.
"""

from redis import asyncio as aioredis

from app.config import get_settings

settings = get_settings()

_redis_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Return singleton async Redis client. Lazy init."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client


async def close_redis() -> None:
    """Close Redis connection — call di app shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
