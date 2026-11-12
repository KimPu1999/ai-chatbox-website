import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha1

import httpx
from pwdlib import PasswordHash

from app.core.config import get_settings

password_hash = PasswordHash.recommended()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def validate_password(password: str) -> None:
    settings = get_settings()
    minimum = settings.password_min_length
    maximum = settings.password_max_length
    if len(password) < minimum:
        raise ValueError(f"Password must be at least {minimum} characters")
    if len(password) > maximum:
        raise ValueError(f"Password must be no more than {maximum} characters")
    if password.strip() != password:
        raise ValueError("Password cannot start or end with whitespace")


async def is_breached_password(password: str) -> bool:
    settings = get_settings()
    if not settings.password_breach_check_enabled:
        return False
    # HIBP's k-anonymity range API requires SHA-1. This digest is never used
    # as a password hash or authentication token; explicitly mark that fact
    # for Python and static security scanners.
    digest = sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            response = await client.get(
                f"{settings.password_breach_api_url.rstrip('/')}/{digest[:5]}"
            )
            response.raise_for_status()
    except httpx.HTTPError:
        return False
    suffix = digest[5:]
    return any(
        line.split(":", 1)[0].strip().upper() == suffix
        for line in response.text.splitlines()
        if ":" in line
    )


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_matches(token: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), expected_hash)


def session_expiration() -> datetime:
    return utc_now() + timedelta(seconds=get_settings().session_max_age_seconds)


def is_session_expired(expires_at: datetime, last_activity_at: datetime) -> bool:
    now = utc_now()
    idle_deadline = last_activity_at + timedelta(
        seconds=get_settings().session_idle_timeout_seconds
    )
    return expires_at <= now or idle_deadline <= now
