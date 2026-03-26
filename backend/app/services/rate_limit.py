"""Redis-backed sliding-window rate limiter for sensitive endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request, status


async def rate_limit(
    request: Request,
    redis: Any,
    *,
    limit: int,
    window: int,
    key_prefix: str = "rl",
) -> None:
    """Raise HTTP 429 if the caller exceeds *limit* requests per *window* seconds.

    The counter is incremented atomically with Redis INCR. A TTL is set on the
    first increment so the window resets automatically.  This avoids the GET →
    SET race condition that would exist with two separate commands.

    Args:
        request:    The incoming FastAPI request (used to extract the client IP).
        redis:      An async Redis client instance.
        limit:      Maximum number of allowed requests in the window.
        window:     Sliding-window duration in seconds.
        key_prefix: Namespace prefix for Redis keys.
    """
    ip = request.client.host if request.client else "unknown"
    key = f"{key_prefix}:{request.url.path}:{ip}"

    count: int = await redis.incr(key)
    if count == 1:
        # New key — set the expiry so the window resets automatically.
        await redis.expire(key, window)

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests — please try again later.",
            headers={"Retry-After": str(window)},
        )
