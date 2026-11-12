from collections.abc import Callable
from datetime import timedelta

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.security import hash_token, is_session_expired, token_matches, utc_now
from app.core.config import get_settings
from app.db import get_db
from app.models import AccountStatus, Session, User, UserRole


def auth_error(code: str, message: str, status_code: int = 401) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def session_cookie_name() -> str:
    settings = get_settings()
    return "__Host-pychat_session" if settings.cookie_secure else settings.session_cookie_name


async def get_current_session(request: Request, db: AsyncSession = Depends(get_db)) -> Session:
    raw_token = request.cookies.get(session_cookie_name())
    if not raw_token:
        raise auth_error("AUTH_REQUIRED", "Authentication is required")
    session = await db.scalar(
        select(Session)
        .options(selectinload(Session.user))
        .where(Session.token_hash == hash_token(raw_token))
    )
    if (
        session is None
        or session.revoked_at is not None
        or is_session_expired(session.expires_at, session.last_activity_at)
    ):
        raise auth_error("AUTH_SESSION_INVALID", "Session is invalid or expired")
    if session.user.account_status in {AccountStatus.suspended, AccountStatus.deleted}:
        raise auth_error("AUTH_ACCOUNT_UNAVAILABLE", "Account is unavailable", 403)
    session.last_activity_at = utc_now()
    await db.commit()
    request.state.auth_session = session
    return session


async def require_authenticated_user(session: Session = Depends(get_current_session)) -> User:
    return session.user


async def require_verified_user(user: User = Depends(require_authenticated_user)) -> User:
    if user.email_verified_at is None or user.account_status != AccountStatus.active:
        raise auth_error("AUTH_EMAIL_NOT_VERIFIED", "Email verification is required", 403)
    return user


async def require_recent_reauthentication(
    session: Session = Depends(get_current_session),
) -> Session:
    if session.created_at < utc_now() - timedelta(minutes=15):
        raise auth_error(
            "AUTH_RECENT_REAUTH_REQUIRED",
            "Please sign in again before changing sensitive account data",
            403,
        )
    if session.user.email_verified_at is None:
        raise auth_error("AUTH_EMAIL_NOT_VERIFIED", "Email verification is required", 403)
    return session


def require_roles(*roles: UserRole) -> Callable:
    async def dependency(user: User = Depends(require_authenticated_user)) -> User:
        if user.role not in {role.value for role in roles}:
            raise auth_error(
                "AUTH_FORBIDDEN", "You do not have permission to perform this action", 403
            )
        return user

    return dependency


async def require_csrf(
    request: Request,
    session: Session = Depends(get_current_session),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> Session:
    if (
        not x_csrf_token
        or not session.csrf_token_hash
        or not token_matches(x_csrf_token, session.csrf_token_hash)
    ):
        raise auth_error("AUTH_CSRF_INVALID", "Invalid CSRF token", 403)
    return session


def ensure_trusted_origin(request: Request) -> None:
    settings = get_settings()
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    if origin and origin.rstrip("/") not in {item.rstrip("/") for item in settings.allowed_origins}:
        raise auth_error("AUTH_ORIGIN_INVALID", "Request origin is not allowed", 403)
    if not origin and referer:
        if not any(referer.startswith(item.rstrip("/") + "/") for item in settings.allowed_origins):
            raise auth_error("AUTH_ORIGIN_INVALID", "Request origin is not allowed", 403)
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise auth_error("AUTH_ORIGIN_INVALID", "Request origin is not allowed", 403)
