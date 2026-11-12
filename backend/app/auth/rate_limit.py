from collections import defaultdict, deque
from time import monotonic

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

_attempts: dict[str, deque[float]] = defaultdict(deque)


def enforce_rate_limit(request: Request, action: str, limit: int, window_seconds: int = 60) -> None:
    key = f"{action}:{request.client.host if request.client else 'unknown'}"
    now = monotonic()
    attempts = _attempts[key]
    while attempts and attempts[0] <= now - window_seconds:
        attempts.popleft()
    if len(attempts) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "AUTH_RATE_LIMITED", "message": "Too many attempts"},
            headers={"Retry-After": str(window_seconds)},
        )
    attempts.append(now)


async def enforce_rate_limit_async(
    request: Request, action: str, limit: int, window_seconds: int = 60
) -> None:
    """Enforce a fixed-window limit with Redis when configured.

    The Lua operation makes increment/expiry atomic across workers. Local
    development without Redis keeps the bounded in-process fallback above. A
    configured but unavailable Redis instance fails closed for sensitive flows,
    preventing a deployment from silently losing its rate limit.
    """
    settings = get_settings()
    if not settings.redis_url:
        enforce_rate_limit(request, action, limit, window_seconds)
        return

    try:
        import redis.asyncio as redis

        client = redis.from_url(settings.redis_url, decode_responses=True)
        key = f"pychat:ratelimit:{action}:{request.client.host if request.client else 'unknown'}"
        script = """
        local current = redis.call('INCR', KEYS[1])
        if current == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
        return current
        """
        try:
            current = int(await client.eval(script, 1, key, window_seconds))
        finally:
            await client.aclose()
    except Exception as exc:  # noqa: BLE001 - fail closed when distributed limits are required
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "RATE_LIMIT_UNAVAILABLE",
                "message": "Request protection is unavailable",
            },
            headers={"Retry-After": "5"},
        ) from exc
    if current > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "AUTH_RATE_LIMITED", "message": "Too many attempts"},
            headers={"Retry-After": str(window_seconds)},
        )
