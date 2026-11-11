from __future__ import annotations

# ruff: noqa: E501
from collections.abc import Callable

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import auth_error, ensure_trusted_origin
from app.auth.security import hash_token, is_session_expired, token_matches, utc_now
from app.core.config import get_settings
from app.db import get_db
from app.models import AccountStatus, Session
from app.platform.security import has_permission, mfa_is_recent


def platform_cookie_name() -> str:
    settings = get_settings()
    return "__Host-pychat_platform_session" if settings.cookie_secure else settings.platform_session_cookie_name


async def get_current_platform_session(request: Request, db: AsyncSession = Depends(get_db)) -> Session:
    raw_token = request.cookies.get(platform_cookie_name())
    if not raw_token:
        raise auth_error("PLATFORM_AUTH_REQUIRED", "Platform authentication is required")
    session = await db.scalar(
        select(Session).options(selectinload(Session.user)).where(Session.token_hash == hash_token(raw_token))
    )
    if (
        session is None
        or session.session_kind != "platform"
        or session.revoked_at is not None
        or is_session_expired(session.expires_at, session.last_activity_at)
    ):
        raise auth_error("PLATFORM_SESSION_INVALID", "Platform session is invalid or expired")
    if session.user.account_status != AccountStatus.active or session.user.email_verified_at is None:
        raise auth_error("PLATFORM_ACCOUNT_UNAVAILABLE", "Platform account is unavailable", 403)
    session.last_activity_at = utc_now()
    await db.commit()
    request.state.platform_session = session
    return session


def require_platform_permission(permission: str, *, step_up: bool = False) -> Callable:
    async def dependency(
        request: Request,
        session: Session = Depends(get_current_platform_session),
        db: AsyncSession = Depends(get_db),
    ) -> Session:
        ensure_trusted_origin(request)
        user = session.user
        if not has_permission(user.role, permission):
            raise auth_error("PLATFORM_FORBIDDEN", "You do not have platform permission", 403)
        if step_up and not mfa_is_recent(session.mfa_verified_at):
            raise auth_error("PLATFORM_MFA_STEP_UP_REQUIRED", "Recent MFA verification is required", 403)
        return session

    return dependency


async def require_platform_csrf(
    request: Request,
    session: Session = Depends(get_current_platform_session),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> Session:
    if not x_csrf_token or not session.csrf_token_hash or not token_matches(x_csrf_token, session.csrf_token_hash):
        raise auth_error("AUTH_CSRF_INVALID", "Invalid CSRF token", 403)
    return session

