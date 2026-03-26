"""Shared async Redis client."""
from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis

from app.config import settings

# Module-level pool — one connection pool for the whole process.
_redis: Any = aioredis.from_url(  # type: ignore[no-untyped-call]
    settings.redis_url, decode_responses=True
)


def get_redis_pool() -> Any:
    return _redis


async def get_redis() -> Any:
    return _redis
