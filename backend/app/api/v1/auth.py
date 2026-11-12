from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    ensure_trusted_origin,
    get_current_session,
    require_authenticated_user,
    require_csrf,
    require_roles,
    require_verified_user,
    session_cookie_name,
)
from app.auth.email import email_service
from app.auth.rate_limit import enforce_rate_limit_async
from app.auth.schemas import (
    AdminUserResponse,
    AdminUserRoleRequest,
    AdminUserStatusRequest,
    AuthMessage,
    ChangePasswordRequest,
    CsrfResponse,
    EmailRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SessionResponse,
    TokenRequest,
    UserResponse,
)
from app.auth.security import (
    generate_token,
    hash_password,
    hash_token,
    is_breached_password,
    utc_now,
    validate_password,
    verify_password,
)
from app.auth.service import (
    create_email_verification_token,
    create_reset_token,
    create_session,
    record_audit,
    revoke_all_sessions,
)
from app.core.config import get_settings
from app.db import get_db
from app.models import (
    AccountStatus,
    EmailVerificationToken,
    PasswordResetToken,
    Session,
    User,
    UserRole,
)
from app.repositories.users import normalize_email

router = APIRouter(prefix="/auth", tags=["authentication"])


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def set_session_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=session_cookie_name(),
        value=raw_token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=session_cookie_name(),
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite=get_settings().cookie_samesite,
        path="/",
    )


@router.post("/register", response_model=UserResponse, status_code=201, summary="Register a user")
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    ensure_trusted_origin(request)
    await enforce_rate_limit_async(request, "register", get_settings().auth_rate_limit_per_minute)
    try:
        validate_password(payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "AUTH_WEAK_PASSWORD", "message": str(exc)}
        ) from exc
    if await is_breached_password(payload.password):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "AUTH_BREACHED_PASSWORD",
                "message": "Choose a password that has not appeared in a known breach",
            },
        )
    normalized = normalize_email(str(payload.email))
    existing = await db.scalar(select(User).where(User.email_normalized == normalized))
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "AUTH_EMAIL_EXISTS",
                "message": "An account already exists for this email",
            },
        )
    user = User(
        email=str(payload.email),
        email_normalized=normalized,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    await db.flush()
    token = await create_email_verification_token(db, user)
    session, raw_session = await create_session(db, user)
    await email_service.send_verification(
        str(user.email), f"{get_settings().frontend_url.rstrip('/')}/verify-email?token={token}"
    )
    await record_audit(
        db, user_id=user.id, action="auth.register", entity_type="user", entity_id=user.id
    )
    set_session_cookie(response, raw_session)
    no_store(response)
    return user


@router.post("/login", response_model=UserResponse, summary="Create a server-side session")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    ensure_trusted_origin(request)
    await enforce_rate_limit_async(request, "login", get_settings().auth_rate_limit_per_minute)
    user = await db.scalar(
        select(User).where(User.email_normalized == normalize_email(str(payload.email)))
    )
    if (
        not user
        or not user.password_hash
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_INVALID_CREDENTIALS", "message": "Invalid email or password"},
        )
    if user.account_status in {AccountStatus.suspended, AccountStatus.deleted}:
        raise HTTPException(
            status_code=403,
            detail={"code": "AUTH_ACCOUNT_UNAVAILABLE", "message": "Account is unavailable"},
        )
    if user.email_verified_at is None or user.account_status != AccountStatus.active:
        raise HTTPException(
            status_code=403,
            detail={"code": "AUTH_EMAIL_NOT_VERIFIED", "message": "Email verification is required"},
        )
    user.last_login_at = utc_now()
    session, raw_session = await create_session(db, user)
    await record_audit(
        db, user_id=user.id, action="auth.login", entity_type="session", entity_id=session.id
    )
    set_session_cookie(response, raw_session)
    no_store(response)
    return user


@router.post("/logout", response_model=AuthMessage, summary="Revoke the current session")
async def logout(
    request: Request,
    response: Response,
    session: Session = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> AuthMessage:
    ensure_trusted_origin(request)
    session.revoked_at = utc_now()
    await db.commit()
    clear_session_cookie(response)
    no_store(response)
    return AuthMessage(code="AUTH_LOGGED_OUT", message="Logged out")


@router.post("/logout-all", response_model=AuthMessage, summary="Revoke all sessions")
async def logout_all(
    request: Request,
    response: Response,
    user: User = Depends(require_authenticated_user),
    _: Session = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> AuthMessage:
    ensure_trusted_origin(request)
    await revoke_all_sessions(db, user.id)
    clear_session_cookie(response)
    no_store(response)
    return AuthMessage(code="AUTH_LOGGED_OUT", message="All sessions logged out")


@router.get("/me", response_model=UserResponse, summary="Get the current user")
async def me(response: Response, user: User = Depends(require_authenticated_user)) -> User:
    no_store(response)
    return user


@router.get("/csrf", response_model=CsrfResponse, summary="Get a session-bound CSRF token")
async def csrf(
    response: Response,
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> CsrfResponse:
    raw_token = generate_token()
    session.csrf_token_hash = hash_token(raw_token)
    await db.commit()
    no_store(response)
    return CsrfResponse(token=raw_token)


@router.post(
    "/verify-email", response_model=AuthMessage, summary="Consume an email verification token"
)
async def verify_email(
    payload: TokenRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> AuthMessage:
    ensure_trusted_origin(request)
    await enforce_rate_limit_async(
        request, "verify-email", get_settings().auth_rate_limit_per_minute
    )
    token_row = await db.scalar(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.token_hash == hash_token(payload.token))
        .with_for_update()
    )
    if not token_row or token_row.used_at or token_row.expires_at <= utc_now():
        raise HTTPException(
            status_code=400,
            detail={
                "code": "AUTH_TOKEN_INVALID",
                "message": "Verification token is invalid or expired",
            },
        )
    user = await db.get(User, token_row.user_id)
    token_row.used_at = utc_now()
    if user:
        user.email_verified_at = utc_now()
        user.account_status = AccountStatus.active
    await db.commit()
    no_store(response)
    return AuthMessage(code="AUTH_EMAIL_VERIFIED", message="Email verified")


@router.post(
    "/resend-verification", response_model=AuthMessage, summary="Resend verification email"
)
async def resend_verification(
    payload: EmailRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> AuthMessage:
    ensure_trusted_origin(request)
    await enforce_rate_limit_async(
        request, "resend-verification", get_settings().auth_rate_limit_per_minute
    )
    user = await db.scalar(
        select(User).where(User.email_normalized == normalize_email(str(payload.email)))
    )
    if user and user.email_verified_at is None and user.account_status != AccountStatus.deleted:
        token = await create_email_verification_token(db, user)
        await email_service.send_verification(
            str(user.email), f"{get_settings().frontend_url.rstrip('/')}/verify-email?token={token}"
        )
    no_store(response)
    return AuthMessage(
        code="AUTH_VERIFICATION_SENT",
        message="If the account exists, a verification email has been sent",
    )


@router.post("/forgot-password", response_model=AuthMessage, summary="Request a password reset")
async def forgot_password(
    payload: EmailRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> AuthMessage:
    ensure_trusted_origin(request)
    await enforce_rate_limit_async(
        request, "forgot-password", get_settings().auth_rate_limit_per_minute
    )
    user = await db.scalar(
        select(User).where(User.email_normalized == normalize_email(str(payload.email)))
    )
    if user and user.account_status != AccountStatus.deleted:
        token = await create_reset_token(db, user)
        await email_service.send_password_reset(
            str(user.email),
            f"{get_settings().frontend_url.rstrip('/')}/reset-password?token={token}",
        )
    no_store(response)
    return AuthMessage(
        code="AUTH_RESET_SENT",
        message="If the account exists, a password reset email has been sent",
    )


@router.post("/reset-password", response_model=AuthMessage, summary="Reset a password with a token")
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthMessage:
    ensure_trusted_origin(request)
    await enforce_rate_limit_async(
        request, "reset-password", get_settings().auth_rate_limit_per_minute
    )
    try:
        validate_password(payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "AUTH_WEAK_PASSWORD", "message": str(exc)}
        ) from exc
    if await is_breached_password(payload.password):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "AUTH_BREACHED_PASSWORD",
                "message": "Choose a password that has not appeared in a known breach",
            },
        )
    token_row = await db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == hash_token(payload.token))
        .with_for_update()
    )
    if not token_row or token_row.used_at or token_row.expires_at <= utc_now():
        raise HTTPException(
            status_code=400,
            detail={"code": "AUTH_TOKEN_INVALID", "message": "Reset token is invalid or expired"},
        )
    user = await db.get(User, token_row.user_id, with_for_update=True)
    if not user or user.account_status == AccountStatus.deleted:
        raise HTTPException(
            status_code=400,
            detail={"code": "AUTH_TOKEN_INVALID", "message": "Reset token is invalid or expired"},
        )
    user.password_hash = hash_password(payload.password)
    token_row.used_at = utc_now()
    await db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.id != token_row.id)
        .values(used_at=utc_now())
    )
    await db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    await db.commit()
    await record_audit(
        db, user_id=user.id, action="auth.password_reset", entity_type="user", entity_id=user.id
    )
    no_store(response)
    return AuthMessage(code="AUTH_PASSWORD_RESET", message="Password reset successfully")


@router.post("/change-password", response_model=AuthMessage, summary="Change the current password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: User = Depends(require_verified_user),
    _: Session = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> AuthMessage:
    ensure_trusted_origin(request)
    if not user.password_hash or not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=400,
            detail={"code": "AUTH_PASSWORD_INVALID", "message": "Current password is incorrect"},
        )
    try:
        validate_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "AUTH_WEAK_PASSWORD", "message": str(exc)}
        ) from exc
    if await is_breached_password(payload.new_password):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "AUTH_BREACHED_PASSWORD",
                "message": "Choose a password that has not appeared in a known breach",
            },
        )
    user.password_hash = hash_password(payload.new_password)
    await revoke_all_sessions(db, user.id)
    await record_audit(
        db, user_id=user.id, action="auth.password_changed", entity_type="user", entity_id=user.id
    )
    clear_session_cookie(response)
    no_store(response)
    return AuthMessage(
        code="AUTH_PASSWORD_CHANGED", message="Password changed; please sign in again"
    )


@router.get("/sessions", response_model=list[SessionResponse], summary="List active sessions")
async def sessions(
    response: Response,
    request: Request,
    user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> list[SessionResponse]:
    current = getattr(request.state, "auth_session", None)
    rows = list(
        await db.scalars(
            select(Session)
            .where(Session.user_id == user.id, Session.revoked_at.is_(None))
            .order_by(Session.created_at.desc())
        )
    )
    no_store(response)
    return [
        SessionResponse.model_validate(row).model_copy(
            update={"current": current is not None and row.id == current.id}
        )
        for row in rows
    ]


@router.delete(
    "/sessions/{session_id}", response_model=AuthMessage, summary="Revoke one own session"
)
async def delete_session(
    session_id: UUID,
    request: Request,
    response: Response,
    user: User = Depends(require_authenticated_user),
    _: Session = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> AuthMessage:
    ensure_trusted_origin(request)
    await db.execute(
        update(Session)
        .where(Session.id == session_id, Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    await db.commit()
    no_store(response)
    return AuthMessage(code="AUTH_SESSION_REVOKED", message="Session revoked")


admin_required = require_roles(UserRole.admin, UserRole.superadmin)


@router.get(
    "/admin/users", response_model=list[AdminUserResponse], summary="List users for administrators"
)
async def admin_users(
    response: Response, _: User = Depends(admin_required), db: AsyncSession = Depends(get_db)
) -> list[User]:
    no_store(response)
    return list(await db.scalars(select(User).order_by(User.created_at.desc()).limit(100)))


@router.patch(
    "/admin/users/{user_id}/status",
    response_model=AdminUserResponse,
    summary="Update an allowed account status",
)
async def admin_user_status(
    user_id: UUID,
    payload: AdminUserStatusRequest,
    request: Request,
    response: Response,
    actor: User = Depends(admin_required),
    _: Session = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> User:
    ensure_trusted_origin(request)
    target = await db.get(User, user_id, with_for_update=True)
    if not target:
        raise HTTPException(
            status_code=404, detail={"code": "AUTH_USER_NOT_FOUND", "message": "User not found"}
        )
    if target.role != UserRole.user and actor.role != UserRole.superadmin:
        raise HTTPException(
            status_code=403, detail={"code": "AUTH_FORBIDDEN", "message": "Insufficient permission"}
        )
    if target.id == actor.id and payload.account_status == AccountStatus.suspended:
        raise HTTPException(
            status_code=403,
            detail={"code": "AUTH_SELF_PROTECTION", "message": "You cannot suspend yourself"},
        )
    if target.role == UserRole.superadmin and payload.account_status == AccountStatus.suspended:
        count = await db.scalar(
            select(func.count(User.id)).where(
                User.role == UserRole.superadmin, User.account_status == AccountStatus.active
            )
        )
        if count <= 1:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AUTH_LAST_SUPERADMIN",
                    "message": "The last superadmin cannot be suspended",
                },
            )
    target.account_status = payload.account_status
    await db.commit()
    await record_audit(
        db,
        user_id=actor.id,
        action="admin.user_status_changed",
        entity_type="user",
        entity_id=target.id,
    )
    no_store(response)
    return target


@router.patch(
    "/admin/users/{user_id}/role",
    response_model=AdminUserResponse,
    summary="Change a user role as superadmin",
)
async def admin_user_role(
    user_id: UUID,
    payload: AdminUserRoleRequest,
    request: Request,
    response: Response,
    actor: User = Depends(require_roles(UserRole.superadmin)),
    _: Session = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> User:
    ensure_trusted_origin(request)
    target = await db.get(User, user_id, with_for_update=True)
    if not target:
        raise HTTPException(
            status_code=404, detail={"code": "AUTH_USER_NOT_FOUND", "message": "User not found"}
        )
    if target.id == actor.id and payload.role != UserRole.superadmin:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "AUTH_SELF_PROTECTION",
                "message": "You cannot remove your own superadmin role",
            },
        )
    if target.role == UserRole.superadmin and payload.role != UserRole.superadmin:
        count = await db.scalar(
            select(func.count(User.id)).where(
                User.role == UserRole.superadmin, User.account_status == AccountStatus.active
            )
        )
        if count <= 1:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AUTH_LAST_SUPERADMIN",
                    "message": "The last superadmin cannot be demoted",
                },
            )
    target.role = payload.role
    await db.commit()
    await record_audit(
        db,
        user_id=actor.id,
        action="admin.user_role_changed",
        entity_type="user",
        entity_id=target.id,
    )
    no_store(response)
    return target
