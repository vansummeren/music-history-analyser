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

    The rate-limit key is derived from the client IP address so that different
    callers share independent buckets.

    Args:
        request:    The incoming FastAPI request (used to extract the client IP).
        redis:      An async Redis client instance.
        limit:      Maximum number of allowed requests in the window.
        window:     Sliding-window duration in seconds.
        key_prefix: Namespace prefix for Redis keys.
    """
    ip = request.client.host if request.client else "unknown"
    key = f"{key_prefix}:{request.url.path}:{ip}"

    count_raw: str | None = await redis.get(key)
    count = int(count_raw) if count_raw is not None else 0

    if count >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests — please try again later.",
            headers={"Retry-After": str(window)},
        )

    if count == 0:
        await redis.set(key, "1", ex=window)
    else:
        await redis.set(key, str(count + 1), ex=window)
