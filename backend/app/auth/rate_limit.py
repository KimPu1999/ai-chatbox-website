from collections import defaultdict, deque
from time import monotonic

from fastapi import HTTPException, Request, status

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
