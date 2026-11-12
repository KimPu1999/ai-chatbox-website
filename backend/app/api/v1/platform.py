from __future__ import annotations

# The API implementation keeps endpoint declarations together for a single
# auditable control-plane surface.
# ruff: noqa: E501, E701, E702
import asyncio
import hmac
from datetime import date, datetime, time, timedelta, timezone
from time import perf_counter
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy import Date, case, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ensure_trusted_origin
from app.auth.rate_limit import enforce_rate_limit_async
from app.auth.security import generate_token, hash_token, token_matches, utc_now, verify_password
from app.auth.service import create_session, record_audit
from app.core.config import get_settings
from app.db import check_database_connection, get_db
from app.models import (
    AccountStatus,
    AdminMFACredential,
    AdminRecoveryCode,
    AIUsage,
    AuditLog,
    Conversation,
    Document,
    DocumentChunk,
    DocumentProcessingJob,
    GenerationRun,
    ModelPricingVersion,
    PlatformModel,
    PlatformSetting,
    QuotaPolicy,
    Session,
    User,
    UserQuotaOverride,
    UserRole,
)
from app.platform.dependencies import (
    get_current_platform_session,
    platform_cookie_name,
    require_platform_csrf,
    require_platform_permission,
)
from app.platform.schemas import (
    AuditLogPage,
    AuditLogRead,
    ModelUsagePoint,
    OverviewResponse,
    PlatformLoginRequest,
    PlatformLoginResponse,
    PlatformMe,
    PlatformMfaEnrollment,
    PlatformMfaVerifyRequest,
    PlatformModelRead,
    PlatformModelUpdate,
    PlatformSettingsRead,
    PlatformSettingsUpdate,
    PlatformUserPage,
    PlatformUserRead,
    PricingCreate,
    PricingRead,
    QuotaRead,
    QuotaUpdate,
    RoleUpdate,
    StatusUpdate,
    UsageSummary,
    UsageTrendPoint,
)
from app.platform.security import (
    decrypt_mfa_secret,
    encrypt_mfa_secret,
    mfa_is_recent,
    new_recovery_codes,
    new_totp_secret,
    provisioning_uri,
    recovery_code_hash,
)
from app.repositories.users import normalize_email

router = APIRouter(prefix="/platform", tags=["platform-admin"])
PREAUTH_CSRF_COOKIE = "pychat_platform_pre_csrf"


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def _platform_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=platform_cookie_name(), value=token, max_age=settings.session_max_age_seconds,
        httponly=True, secure=settings.cookie_secure, samesite=settings.cookie_samesite, path="/"
    )


def _clear_platform_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(key=platform_cookie_name(), httponly=True, secure=settings.cookie_secure, samesite=settings.cookie_samesite, path="/")


def _date_bounds(query_range: str, start: date | None, end: date | None) -> tuple[datetime, datetime]:
    today = utc_now().date()
    if query_range == "today":
        first, last = today, today
    elif query_range == "yesterday":
        first = last = today - timedelta(days=1)
    elif query_range == "7d":
        first, last = today - timedelta(days=6), today
    elif query_range == "custom":
        first, last = start or today - timedelta(days=29), end or today
    else:
        first, last = today - timedelta(days=29), today
    if first > last or (last - first).days > 366:
        raise HTTPException(status_code=422, detail="Date range must be valid and no longer than 366 days")
    return datetime.combine(first, time.min, tzinfo=timezone.utc), datetime.combine(last + timedelta(days=1), time.min, tzinfo=timezone.utc)


async def _ensure_default_model(db: AsyncSession) -> PlatformModel:
    settings = get_settings()
    model = await db.scalar(select(PlatformModel).where(PlatformModel.identifier == settings.openai_model))
    if model:
        return model
    model = PlatformModel(
        identifier=settings.openai_model, display_name=settings.openai_model,
        enabled=bool(settings.openai_api_key), is_default=True,
        capabilities={"responses": True, "streaming": True},
        max_output_tokens=settings.ai_max_output_tokens, context_limit=settings.ai_context_token_budget,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


@router.get("/auth/csrf")
async def platform_csrf(response: Response, session: Session = Depends(get_current_platform_session), db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    token = generate_token()
    session.csrf_token_hash = hash_token(token)
    await db.commit()
    no_store(response)
    return {"token": token}


@router.get("/auth/preflight")
async def platform_preflight(response: Response) -> dict[str, str]:
    """Issue a short-lived double-submit token before platform login."""
    token = generate_token()
    response.set_cookie(
        key=PREAUTH_CSRF_COOKIE,
        value=token,
        max_age=300,
        httponly=False,
        secure=get_settings().cookie_secure,
        samesite=get_settings().cookie_samesite,
        path="/",
    )
    no_store(response)
    return {"token": token}


@router.post("/auth/login", response_model=PlatformLoginResponse)
async def platform_login(payload: PlatformLoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db), x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token")) -> PlatformLoginResponse:
    ensure_trusted_origin(request)
    preflight = request.cookies.get(PREAUTH_CSRF_COOKIE)
    if not preflight or not x_csrf_token or not hmac.compare_digest(preflight, x_csrf_token):
        raise HTTPException(status_code=403, detail={"code": "AUTH_CSRF_INVALID", "message": "Invalid CSRF token"})
    await enforce_rate_limit_async(request, "platform-login", get_settings().auth_rate_limit_per_minute)
    user = await db.scalar(select(User).where(User.email_normalized == normalize_email(payload.email)))
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail={"code": "PLATFORM_INVALID_CREDENTIALS", "message": "Invalid email or password"})
    if user.role not in {UserRole.admin.value, UserRole.superadmin.value} or user.account_status != AccountStatus.active or not user.email_verified_at:
        raise HTTPException(status_code=403, detail={"code": "PLATFORM_FORBIDDEN", "message": "Platform access is not available for this account"})
    session, raw = await create_session(db, user, session_kind="platform")
    csrf = generate_token()
    session.csrf_token_hash = hash_token(csrf)
    await db.commit()
    _platform_cookie(response, raw)
    no_store(response)
    mfa = await db.scalar(select(AdminMFACredential).where(AdminMFACredential.user_id == user.id, AdminMFACredential.enabled.is_(True)))
    await record_audit(db, user_id=user.id, action="platform.login", entity_type="session", entity_id=session.id)
    return PlatformLoginResponse(code="PLATFORM_LOGIN_OK", message="MFA verification required", mfa_required=True, mfa_enrollment_required=mfa is None)


@router.get("/auth/me", response_model=PlatformMe)
async def platform_me(response: Response, session: Session = Depends(get_current_platform_session)) -> PlatformMe:
    no_store(response)
    return PlatformMe(id=session.user.id, email=session.user.email, display_name=session.user.display_name, role=session.user.role, mfa_verified=mfa_is_recent(session.mfa_verified_at))


@router.post("/auth/mfa/enroll", response_model=PlatformMfaEnrollment)
async def enroll_mfa(response: Response, session: Session = Depends(get_current_platform_session), _: Session = Depends(require_platform_csrf), db: AsyncSession = Depends(get_db)) -> PlatformMfaEnrollment:
    existing = await db.scalar(select(AdminMFACredential).where(AdminMFACredential.user_id == session.user_id, AdminMFACredential.enabled.is_(True)))
    if existing:
        raise HTTPException(status_code=409, detail="MFA is already enrolled")
    secret = new_totp_secret()
    credential = AdminMFACredential(user_id=session.user_id, encrypted_secret=encrypt_mfa_secret(secret))
    db.add(credential)
    codes = new_recovery_codes()
    await db.flush()
    db.add_all([AdminRecoveryCode(mfa_credential_id=credential.id, code_hash=recovery_code_hash(code)) for code in codes])
    await db.commit()
    await record_audit(db, user_id=session.user_id, action="platform.mfa.enrolled", entity_type="user", entity_id=session.user_id)
    no_store(response)
    return PlatformMfaEnrollment(secret=secret, provisioning_uri=provisioning_uri(secret, session.user.email), recovery_codes=codes)


@router.post("/auth/mfa/verify", response_model=PlatformMe)
async def verify_mfa(payload: PlatformMfaVerifyRequest, response: Response, request: Request, session: Session = Depends(get_current_platform_session), _: Session = Depends(require_platform_csrf), db: AsyncSession = Depends(get_db)) -> PlatformMe:
    credential = await db.scalar(select(AdminMFACredential).where(AdminMFACredential.user_id == session.user_id, AdminMFACredential.enabled.is_(True)).with_for_update())
    if not credential:
        raise HTTPException(status_code=403, detail={"code": "PLATFORM_MFA_ENROLLMENT_REQUIRED", "message": "Enroll MFA before continuing"})
    now = utc_now()
    if credential.locked_until and credential.locked_until > now:
        raise HTTPException(status_code=429, detail="MFA verification temporarily locked")
    secret = decrypt_mfa_secret(credential.encrypted_secret)
    totp = __import__("pyotp").TOTP(secret)
    counter = totp.timecode(now)
    candidate = payload.code.strip()
    valid_totp = totp.verify(candidate, valid_window=1) and (
        credential.last_counter is None or counter > credential.last_counter
    )
    recovery = None
    if not valid_totp:
        recovery_rows = (await db.execute(select(AdminRecoveryCode).where(AdminRecoveryCode.mfa_credential_id == credential.id, AdminRecoveryCode.used_at.is_(None)).with_for_update())).scalars().all()
        recovery = next((row for row in recovery_rows if token_matches(candidate, row.code_hash)), None)
    valid = valid_totp or recovery is not None
    if not valid:
        credential.failed_attempts += 1
        if credential.failed_attempts >= 5:
            credential.locked_until = now + timedelta(minutes=10)
            credential.failed_attempts = 0
        await db.commit()
        await record_audit(db, user_id=session.user_id, action="platform.mfa.failed", entity_type="user", entity_id=session.user_id, result="failure")
        raise HTTPException(status_code=401, detail={"code": "PLATFORM_MFA_INVALID", "message": "Invalid MFA code"})
    credential.failed_attempts = 0
    if valid_totp:
        credential.last_counter = counter
    if recovery:
        recovery.used_at = now
    credential.last_verified_at = now
    session.mfa_verified_at = now
    await db.commit()
    await record_audit(db, user_id=session.user_id, action="platform.mfa.verified", entity_type="session", entity_id=session.id)
    no_store(response)
    return PlatformMe(id=session.user.id, email=session.user.email, display_name=session.user.display_name, role=session.user.role, mfa_verified=True)


@router.post("/auth/logout")
async def platform_logout(response: Response, request: Request, session: Session = Depends(require_platform_csrf), db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    ensure_trusted_origin(request)
    session.revoked_at = utc_now()
    await db.commit()
    _clear_platform_cookie(response)
    no_store(response)
    return {"code": "PLATFORM_LOGGED_OUT"}


@router.get("/overview", response_model=OverviewResponse)
async def overview(
    response: Response,
    session: Session = Depends(require_platform_permission("platform.overview.read")),
    db: AsyncSession = Depends(get_db),
    range: str = Query(default="30d", pattern="^(today|yesterday|7d|30d|custom)$"),
    start: date | None = None,
    end: date | None = None,
) -> OverviewResponse:
    no_store(response)
    since, until = _date_bounds(range, start, end)
    total_users = await db.scalar(select(func.count(User.id))) or 0
    active_users = await db.scalar(select(func.count(User.id)).where(User.account_status == AccountStatus.active.value)) or 0
    new_users = await db.scalar(select(func.count(User.id)).where(User.created_at >= since, User.created_at < until)) or 0
    conversations = await db.scalar(select(func.count(Conversation.id)).where(Conversation.created_at >= since, Conversation.created_at < until)) or 0
    requests = await db.scalar(select(func.count(GenerationRun.id)).where(GenerationRun.created_at >= since, GenerationRun.created_at < until)) or 0
    completed = await db.scalar(select(func.count(GenerationRun.id)).where(GenerationRun.created_at >= since, GenerationRun.created_at < until, GenerationRun.status == "completed")) or 0
    failed = await db.scalar(select(func.count(GenerationRun.id)).where(GenerationRun.created_at >= since, GenerationRun.created_at < until, GenerationRun.status.in_(["failed", "incomplete"]))) or 0
    usage = await db.execute(select(func.coalesce(func.sum(AIUsage.prompt_tokens), 0), func.coalesce(func.sum(AIUsage.completion_tokens), 0), func.sum(AIUsage.estimated_cost)).where(AIUsage.created_at >= since, AIUsage.created_at < until))
    input_tokens, output_tokens, estimated_spend = usage.one()
    storage = await db.execute(select(func.count(Document.id), func.coalesce(func.sum(Document.size_bytes), 0)).where(Document.deleted_at.is_(None)))
    doc_count, storage_bytes = storage.one()
    queue = await db.scalar(select(func.count(DocumentProcessingJob.id)).where(DocumentProcessingJob.status.in_(["queued", "running"]))) or 0
    audit_rows = (await db.execute(select(AuditLog).order_by(desc(AuditLog.created_at), desc(AuditLog.id)).limit(8))).scalars().all()
    recent = [{"id": str(row.id), "action": row.action, "entity_type": row.entity_type, "result": row.result, "created_at": row.created_at.isoformat()} for row in audit_rows]
    return OverviewResponse(range_start=since, range_end=until, total_users=total_users, active_users=active_users, new_users=new_users, conversations=conversations, generation_requests=requests, completed_generations=completed, failed_generations=failed, input_tokens=input_tokens, output_tokens=output_tokens, estimated_ai_spend=estimated_spend, document_storage_bytes=storage_bytes, documents=doc_count, processing_queue=queue, recent_activity=recent)


@router.get("/users", response_model=PlatformUserPage)
async def users(
    response: Response,
    session: Session = Depends(require_platform_permission("platform.users.read")),
    db: AsyncSession = Depends(get_db),
    q: str | None = Query(default=None, max_length=200), role: str | None = Query(default=None), account_status: str | None = None,
    verified: bool | None = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=10, ge=1, le=100),
) -> PlatformUserPage:
    no_store(response)
    filters = []
    if q:
        term = q.strip().lower()
        filters.append((User.email_normalized.ilike(f"%{term}%")) | (User.display_name.ilike(f"%{term}%")))
    if role in {item.value for item in UserRole}: filters.append(User.role == role)
    if account_status in {item.value for item in AccountStatus}: filters.append(User.account_status == account_status)
    if verified is not None: filters.append(User.email_verified_at.is_not(None) if verified else User.email_verified_at.is_(None))
    total = await db.scalar(select(func.count(User.id)).where(*filters)) or 0
    rows = (await db.execute(select(User).where(*filters).order_by(desc(User.created_at), desc(User.id)).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return PlatformUserPage(items=[PlatformUserRead.model_validate(row) for row in rows], total=total, page=page, page_size=page_size)


@router.get("/users/{user_id}", response_model=PlatformUserRead)
async def user_detail(user_id: UUID, response: Response, session: Session = Depends(require_platform_permission("platform.users.read")), db: AsyncSession = Depends(get_db)) -> User:
    no_store(response)
    user = await db.get(User, user_id)
    if not user: raise HTTPException(status_code=404, detail="User not found")
    return user


async def _target_user(db: AsyncSession, user_id: UUID) -> User:
    user = await db.get(User, user_id, with_for_update=True)
    if not user: raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{user_id}/status", response_model=PlatformUserRead)
async def update_status(user_id: UUID, payload: StatusUpdate, request: Request, response: Response, session: Session = Depends(require_platform_permission("platform.users.status.update", step_up=True)), _: Session = Depends(require_platform_csrf), db: AsyncSession = Depends(get_db)) -> User:
    ensure_trusted_origin(request)
    target = await _target_user(db, user_id)
    actor = session.user
    if target.id == actor.id or (target.role in {UserRole.admin.value, UserRole.superadmin.value} and actor.role != UserRole.superadmin.value):
        raise HTTPException(status_code=403, detail="This account cannot be changed by the current administrator")
    if target.role == UserRole.superadmin.value and payload.account_status != AccountStatus.active.value:
        count = await db.scalar(select(func.count(User.id)).where(User.role == UserRole.superadmin.value, User.account_status == AccountStatus.active.value)) or 0
        if count <= 1: raise HTTPException(status_code=409, detail="The last active superadmin is protected")
    target.account_status = payload.account_status
    target.is_active = payload.account_status == AccountStatus.active.value
    if payload.account_status in {AccountStatus.suspended.value, AccountStatus.deleted.value}: await db.execute(update(Session).where(Session.user_id == target.id, Session.revoked_at.is_(None)).values(revoked_at=utc_now()))
    await db.commit()
    await record_audit(db, user_id=actor.id, action="platform.user.status_updated", entity_type="user", entity_id=target.id, metadata={"status": payload.account_status})
    no_store(response)
    return target


@router.patch("/users/{user_id}/role", response_model=PlatformUserRead)
async def update_role(user_id: UUID, payload: RoleUpdate, request: Request, response: Response, session: Session = Depends(require_platform_permission("platform.users.role.update", step_up=True)), _: Session = Depends(require_platform_csrf), db: AsyncSession = Depends(get_db)) -> User:
    ensure_trusted_origin(request)
    target = await _target_user(db, user_id)
    if target.id == session.user.id: raise HTTPException(status_code=403, detail="Self role changes are blocked")
    if target.role == UserRole.superadmin.value and payload.role != UserRole.superadmin.value:
        count = await db.scalar(select(func.count(User.id)).where(User.role == UserRole.superadmin.value, User.account_status == AccountStatus.active.value)) or 0
        if count <= 1: raise HTTPException(status_code=409, detail="The last active superadmin is protected")
    old = target.role; target.role = payload.role
    await db.execute(update(Session).where(Session.user_id == target.id, Session.revoked_at.is_(None)).values(revoked_at=utc_now()))
    await db.commit()
    await record_audit(db, user_id=session.user.id, action="platform.user.role_updated", entity_type="user", entity_id=target.id, metadata={"from": old, "to": payload.role})
    no_store(response)
    return target


@router.post("/users/{user_id}/revoke-sessions")
async def revoke_user_sessions(user_id: UUID, request: Request, response: Response, session: Session = Depends(require_platform_permission("platform.users.status.update", step_up=True)), _: Session = Depends(require_platform_csrf), db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    ensure_trusted_origin(request)
    target = await _target_user(db, user_id)
    if target.role == UserRole.superadmin.value and session.user.role != UserRole.superadmin.value: raise HTTPException(status_code=403, detail="Superadmin sessions are protected")
    result = await db.execute(update(Session).where(Session.user_id == target.id, Session.revoked_at.is_(None)).values(revoked_at=utc_now()))
    await db.commit()
    await record_audit(db, user_id=session.user.id, action="platform.user.sessions_revoked", entity_type="user", entity_id=target.id)
    return {"revoked": result.rowcount or 0}


@router.get("/usage/summary", response_model=UsageSummary)
async def usage_summary(response: Response, session: Session = Depends(require_platform_permission("platform.usage.read")), db: AsyncSession = Depends(get_db), range: str = "30d", start: date | None = None, end: date | None = None) -> UsageSummary:
    no_store(response); since, until = _date_bounds(range, start, end)
    row = (await db.execute(select(func.count(AIUsage.id), func.count(case((GenerationRun.status == "completed", 1))), func.count(case((GenerationRun.status.in_(["failed", "incomplete"]), 1))), func.coalesce(func.sum(AIUsage.prompt_tokens), 0), func.coalesce(func.sum(AIUsage.completion_tokens), 0), func.coalesce(func.sum(AIUsage.cached_input_tokens), 0), func.avg(AIUsage.latency_ms), func.count(case((AIUsage.usage_confirmed.is_(True), 1))), func.count(case((AIUsage.usage_confirmed.is_(False), 1)))).outerjoin(GenerationRun, GenerationRun.id == AIUsage.generation_run_id).where(AIUsage.created_at >= since, AIUsage.created_at < until))).one()
    return UsageSummary(requests=row[0], completed=row[1], failed=row[2], input_tokens=row[3], output_tokens=row[4], cached_input_tokens=row[5], embedding_tokens=0, average_latency_ms=float(row[6]) if row[6] is not None else None, confirmed_usage_rows=row[7], unknown_usage_rows=row[8])


@router.get("/usage/trends", response_model=list[UsageTrendPoint])
async def usage_trends(response: Response, session: Session = Depends(require_platform_permission("platform.usage.read")), db: AsyncSession = Depends(get_db), range: str = "30d", start: date | None = None, end: date | None = None) -> list[UsageTrendPoint]:
    no_store(response); since, until = _date_bounds(range, start, end)
    rows = (await db.execute(select(func.cast(AIUsage.created_at, Date), func.count(AIUsage.id), func.coalesce(func.sum(AIUsage.prompt_tokens), 0), func.coalesce(func.sum(AIUsage.completion_tokens), 0), func.sum(AIUsage.estimated_cost)).where(AIUsage.created_at >= since, AIUsage.created_at < until).group_by(func.cast(AIUsage.created_at, Date)).order_by(func.cast(AIUsage.created_at, Date)))).all()
    return [UsageTrendPoint(date=row[0], requests=row[1], completed=0, failed=0, input_tokens=row[2], output_tokens=row[3], estimated_cost=row[4]) for row in rows]


@router.get("/usage/by-model", response_model=list[ModelUsagePoint])
async def usage_by_model(response: Response, session: Session = Depends(require_platform_permission("platform.usage.read")), db: AsyncSession = Depends(get_db), range: str = "30d", start: date | None = None, end: date | None = None) -> list[ModelUsagePoint]:
    no_store(response); since, until = _date_bounds(range, start, end)
    rows = (await db.execute(select(AIUsage.model, func.count(AIUsage.id), func.coalesce(func.sum(AIUsage.prompt_tokens), 0), func.coalesce(func.sum(AIUsage.completion_tokens), 0), func.sum(AIUsage.estimated_cost)).where(AIUsage.created_at >= since, AIUsage.created_at < until).group_by(AIUsage.model).order_by(desc(func.count(AIUsage.id))))).all()
    return [ModelUsagePoint(model=row[0], requests=row[1], input_tokens=row[2], output_tokens=row[3], estimated_cost=row[4]) for row in rows]


@router.get("/costs")
async def costs(response: Response, session: Session = Depends(require_platform_permission("platform.costs.read")), db: AsyncSession = Depends(get_db), range: str = "30d", start: date | None = None, end: date | None = None) -> dict:
    no_store(response); since, until = _date_bounds(range, start, end)
    row = (await db.execute(select(func.coalesce(func.sum(AIUsage.estimated_cost), 0), func.count(case((AIUsage.estimated_cost.is_(None), 1))), func.count(AIUsage.id)).where(AIUsage.created_at >= since, AIUsage.created_at < until))).one()
    return {"range_start": since, "range_end": until, "estimated_cost": row[0], "currency": "USD", "missing_pricing_rows": row[1], "usage_rows": row[2], "reconciled_cost": None, "reconciliation_available": False}


@router.get("/pricing", response_model=list[PricingRead])
async def pricing(response: Response, session: Session = Depends(require_platform_permission("platform.costs.read")), db: AsyncSession = Depends(get_db)) -> list[ModelPricingVersion]:
    rows = (await db.execute(select(ModelPricingVersion).order_by(ModelPricingVersion.model_identifier, ModelPricingVersion.effective_start.desc()))).scalars().all()
    no_store(response)
    return rows


@router.post("/pricing", response_model=PricingRead, status_code=201)
async def create_pricing(payload: PricingCreate, request: Request, response: Response, session: Session = Depends(require_platform_permission("platform.costs.read", step_up=True)), _: Session = Depends(require_platform_csrf), db: AsyncSession = Depends(get_db)) -> ModelPricingVersion:
    ensure_trusted_origin(request)
    if payload.effective_end and payload.effective_end <= payload.effective_start:
        raise HTTPException(status_code=422, detail="effective_end must be after effective_start")
    row = ModelPricingVersion(**payload.model_dump(), created_by=session.user.id)
    db.add(row)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A pricing version already exists for this effective start") from exc
    await record_audit(db, user_id=session.user.id, action="platform.pricing.created", entity_type="model_pricing_version", entity_id=row.id)
    no_store(response)
    return row


@router.get("/models", response_model=list[PlatformModelRead])
async def models(response: Response, session: Session = Depends(require_platform_permission("platform.models.read")), db: AsyncSession = Depends(get_db)) -> list[PlatformModel]:
    await _ensure_default_model(db)
    no_store(response)
    return list((await db.execute(select(PlatformModel).order_by(PlatformModel.identifier))).scalars().all())


@router.patch("/models/{model_id}", response_model=PlatformModelRead)
async def update_model(model_id: UUID, payload: PlatformModelUpdate, request: Request, response: Response, session: Session = Depends(require_platform_permission("platform.models.update", step_up=True)), _: Session = Depends(require_platform_csrf), db: AsyncSession = Depends(get_db)) -> PlatformModel:
    ensure_trusted_origin(request); model = await db.get(PlatformModel, model_id)
    if not model: raise HTTPException(status_code=404, detail="Model not found")
    if payload.enabled is False and model.is_default: raise HTTPException(status_code=409, detail="Choose another default model before disabling this one")
    if payload.is_default is True:
        await db.execute(update(PlatformModel).where(PlatformModel.id != model.id).values(is_default=False))
        model.enabled = True
    if payload.enabled is not None: model.enabled = payload.enabled
    if payload.is_default is not None: model.is_default = payload.is_default
    for key in ("display_name", "max_output_tokens", "context_limit"):
        value = getattr(payload, key)
        if value is not None: setattr(model, key, value)
    model.updated_by = session.user.id
    await db.commit(); await db.refresh(model)
    await record_audit(db, user_id=session.user.id, action="platform.model.updated", entity_type="platform_model", entity_id=model.id)
    no_store(response); return model


@router.get("/quotas", response_model=list[QuotaRead])
async def quotas(response: Response, session: Session = Depends(require_platform_permission("platform.quotas.read")), db: AsyncSession = Depends(get_db)) -> list[QuotaPolicy]:
    row = await db.scalar(select(QuotaPolicy).where(QuotaPolicy.scope == "global", QuotaPolicy.scope_key == "default"))
    if not row:
        settings = get_settings(); row = QuotaPolicy(scope="global", scope_key="default", requests_per_minute=settings.ai_max_requests_per_minute, daily_token_limit=settings.ai_daily_token_budget, concurrent_generation_limit=settings.ai_max_concurrent_generations, document_count_limit=settings.document_max_files_per_user, storage_size_limit_bytes=settings.document_max_storage_mb_per_user * 1024 * 1024, enabled=True); db.add(row); await db.commit(); await db.refresh(row)
    no_store(response); return [row]


@router.put("/quotas/{quota_id}", response_model=QuotaRead)
async def update_quota(quota_id: UUID, payload: QuotaUpdate, request: Request, response: Response, session: Session = Depends(require_platform_permission("platform.quotas.update", step_up=True)), _: Session = Depends(require_platform_csrf), db: AsyncSession = Depends(get_db)) -> QuotaPolicy:
    ensure_trusted_origin(request); row = await db.get(QuotaPolicy, quota_id)
    if not row: raise HTTPException(status_code=404, detail="Quota policy not found")
    for key, value in payload.model_dump().items(): setattr(row, key, value)
    row.updated_by = session.user.id; await db.commit(); await db.refresh(row)
    await record_audit(db, user_id=session.user.id, action="platform.quota.updated", entity_type="quota_policy", entity_id=row.id)
    no_store(response); return row


@router.put("/quotas/users/{user_id}")
async def update_user_quota_override(
    user_id: UUID,
    payload: dict[str, int | None],
    request: Request,
    response: Response,
    session: Session = Depends(require_platform_permission("platform.quotas.update", step_up=True)),
    _: Session = Depends(require_platform_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    ensure_trusted_origin(request)
    if not await db.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    allowed = {"requests_per_minute", "requests_per_hour", "daily_token_limit", "monthly_token_limit", "concurrent_generation_limit", "document_count_limit", "storage_size_limit_bytes", "embedding_token_budget"}
    if set(payload) - allowed or any(value is not None and (not isinstance(value, int) or value < 0) for value in payload.values()):
        raise HTTPException(status_code=422, detail="Invalid quota override")
    row = await db.get(UserQuotaOverride, user_id, with_for_update=True)
    if not row:
        row = UserQuotaOverride(user_id=user_id, limits=payload, updated_by=session.user.id)
        db.add(row)
    else:
        row.limits = payload
        row.updated_by = session.user.id
    await db.commit()
    await record_audit(db, user_id=session.user.id, action="platform.user_quota.updated", entity_type="user", entity_id=user_id)
    no_store(response)
    return {"user_id": str(user_id), "limits": payload}


@router.get("/storage")
async def storage(response: Response, session: Session = Depends(require_platform_permission("platform.storage.read")), db: AsyncSession = Depends(get_db)) -> dict:
    no_store(response)
    count, size = (await db.execute(select(func.count(Document.id), func.coalesce(func.sum(Document.size_bytes), 0)).where(Document.deleted_at.is_(None)))).one()
    chunks = await db.scalar(select(func.count()).select_from(DocumentChunk))
    jobs = (await db.execute(select(DocumentProcessingJob.status, func.count()).group_by(DocumentProcessingJob.status))).all()
    formats = (await db.execute(select(Document.mime_type, func.count(), func.coalesce(func.sum(Document.size_bytes), 0)).where(Document.deleted_at.is_(None)).group_by(Document.mime_type))).all()
    return {"documents": count, "original_file_bytes": size, "chunk_count": chunks or 0, "vector_index_bytes": None, "temporary_storage_bytes": None, "formats": [{"mime_type": r[0], "count": r[1], "bytes": r[2]} for r in formats], "jobs": {r[0]: r[1] for r in jobs}, "measurements": {"vector_index_bytes": "unavailable without a storage metrics provider", "temporary_storage_bytes": "unavailable"}}


@router.get("/storage/jobs")
async def storage_jobs(response: Response, session: Session = Depends(require_platform_permission("platform.storage.read")), db: AsyncSession = Depends(get_db), page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100)) -> dict:
    total = await db.scalar(select(func.count(DocumentProcessingJob.id))) or 0
    rows = (await db.execute(select(DocumentProcessingJob).order_by(desc(DocumentProcessingJob.created_at)).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    no_store(response); return {"items": [{"id": str(r.id), "document_id": str(r.document_id), "status": r.status, "progress": r.progress, "attempt_count": r.attempt_count, "error_code": r.error_code, "created_at": r.created_at} for r in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/audit-logs", response_model=AuditLogPage)
async def audit_logs(response: Response, session: Session = Depends(require_platform_permission("platform.audit.read")), db: AsyncSession = Depends(get_db), action: str | None = Query(default=None, max_length=100), result: str | None = Query(default=None, max_length=20), page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100)) -> AuditLogPage:
    filters = ([AuditLog.action == action] if action else []) + ([AuditLog.result == result] if result else [])
    total = await db.scalar(select(func.count(AuditLog.id)).where(*filters)) or 0
    rows = (await db.execute(select(AuditLog).where(*filters).order_by(desc(AuditLog.created_at), desc(AuditLog.id)).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    no_store(response); return AuditLogPage(items=[AuditLogRead(id=r.id, user_id=r.user_id, action=r.action, entity_type=r.entity_type, entity_id=r.entity_id, result=r.result, metadata=r.metadata_json, correlation_id=r.correlation_id, created_at=r.created_at) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/health")
async def platform_health(response: Response, session: Session = Depends(require_platform_permission("platform.health.read")), db: AsyncSession = Depends(get_db)) -> dict:
    started = perf_counter(); components = []
    try:
        await asyncio.wait_for(check_database_connection(), timeout=2); db_status = "ok"
    except Exception:  # noqa: BLE001
        db_status = "error"
    components.append({"component": "postgresql", "status": db_status, "latency_ms": round((perf_counter() - started) * 1000)})
    redis_status = "unconfigured"
    if get_settings().redis_url:
        try:
            import redis.asyncio as redis
            client = redis.from_url(get_settings().redis_url)
            await asyncio.wait_for(client.ping(), timeout=2); await client.aclose(); redis_status = "ok"
        except Exception:  # noqa: BLE001
            redis_status = "error"
    components.append({"component": "redis", "status": redis_status, "latency_ms": None})
    components.append({"component": "openai", "status": "configured" if get_settings().openai_api_key else "unconfigured", "latency_ms": None})
    queue = await db.scalar(select(func.count(DocumentProcessingJob.id)).where(DocumentProcessingJob.status.in_(["queued", "running"]))) or 0
    components.append({"component": "document_workers", "status": "degraded" if queue else "ok", "queue_size": queue})
    no_store(response); return {"status": "ok" if all(item["status"] not in {"error"} for item in components) else "degraded", "checked_at": utc_now(), "components": components}


def _settings_defaults() -> dict:
    settings = get_settings()
    return {"app_display_name": settings.app_name, "signup_enabled": True, "email_verification_required": True, "default_user_role": "user", "default_model": settings.openai_model, "maintenance_message": None, "feature_flags": {"documents": True, "platform": True}, "language": "en"}


@router.get("/settings", response_model=PlatformSettingsRead)
async def platform_settings(response: Response, session: Session = Depends(require_platform_permission("platform.overview.read")), db: AsyncSession = Depends(get_db)) -> PlatformSettingsRead:
    defaults = _settings_defaults(); rows = (await db.execute(select(PlatformSetting))).scalars().all()
    values = {**defaults, **{row.key: row.value.get("value") for row in rows if isinstance(row.value, dict) and "value" in row.value}}
    no_store(response); return PlatformSettingsRead(**values)


@router.patch("/settings", response_model=PlatformSettingsRead)
async def update_settings(payload: PlatformSettingsUpdate, request: Request, response: Response, session: Session = Depends(require_platform_permission("platform.settings.update", step_up=True)), _: Session = Depends(require_platform_csrf), db: AsyncSession = Depends(get_db)) -> PlatformSettingsRead:
    ensure_trusted_origin(request); values = payload.model_dump(exclude_unset=True)
    if "default_user_role" in values: raise HTTPException(status_code=422, detail="Default user role is fixed to user")
    for key, value in values.items():
        row = await db.scalar(select(PlatformSetting).where(PlatformSetting.key == key).with_for_update())
        if not row: row = PlatformSetting(key=key, value={"value": value}); db.add(row)
        else: row.value = {"value": value}; row.version += 1
    await db.commit(); await record_audit(db, user_id=session.user.id, action="platform.settings.updated", entity_type="platform_settings", metadata={"keys": list(values)})
    return await platform_settings(response, session, db)
