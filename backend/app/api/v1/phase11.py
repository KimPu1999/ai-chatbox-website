"""Account maturity, support, privacy and platform operations APIs."""

# ruff: noqa: E501

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    ensure_trusted_origin,
    require_csrf,
    require_recent_reauthentication,
    require_verified_user,
)
from app.auth.rate_limit import enforce_rate_limit_async
from app.auth.security import utc_now
from app.auth.service import record_audit
from app.core.config import get_settings
from app.db import get_db
from app.models import (
    AIUsage,
    DataPrivacyRequest,
    Document,
    DocumentProcessingJob,
    FeatureFlag,
    GenerationRun,
    IncidentRecord,
    Plan,
    PlanEntitlement,
    Subscription,
    SupportTicket,
    SupportTicketMessage,
    User,
    UserFeedback,
)
from app.phase11_schemas import (
    AccountPlanRead,
    AccountUsageRead,
    FeatureFlagRead,
    FeatureFlagUpdate,
    FeedbackCreate,
    FeedbackRead,
    OperationsSummary,
    PlanRead,
    PlanUpdate,
    PrivacyRequestCreate,
    PrivacyRequestRead,
    SLOStatus,
    SupportMessageCreate,
    SupportTicketCreate,
    SupportTicketDetail,
    SupportTicketRead,
)
from app.platform.dependencies import require_platform_csrf, require_platform_permission
from app.services.documents import read_private_bytes
from app.services.entitlements import current_plan, get_entitlement_context
from app.services.privacy import enqueue_privacy_request

router = APIRouter(tags=["account", "support", "operations"])


async def _plan_read(db: AsyncSession, plan: Plan) -> PlanRead:
    rows = await db.scalars(select(PlanEntitlement).where(PlanEntitlement.plan_id == plan.id))
    return PlanRead.model_validate(plan).model_copy(
        update={"entitlements": {row.feature: row.value for row in rows}}
    )


@router.get("/plans", response_model=list[PlanRead])
async def list_plans(db: AsyncSession = Depends(get_db)) -> list[PlanRead]:
    plans = list(await db.scalars(select(Plan).where(Plan.enabled.is_(True)).order_by(Plan.sort_order, Plan.code)))
    return [await _plan_read(db, plan) for plan in plans]


@router.get("/account/plan", response_model=AccountPlanRead)
async def account_plan(user: User = Depends(require_verified_user), db: AsyncSession = Depends(get_db)) -> AccountPlanRead:
    plan = await current_plan(db, user.id)
    if plan is None:
        raise HTTPException(status_code=503, detail={"code": "PLAN_NOT_INITIALIZED", "message": "Account plan is not initialized"})
    subscription = await db.scalar(
        select(Subscription).where(Subscription.user_id == user.id, Subscription.plan_id == plan.id).order_by(Subscription.updated_at.desc())
    )
    return AccountPlanRead(
        plan=await _plan_read(db, plan),
        subscription_status=subscription.status if subscription else "active",
        current_period_end=subscription.current_period_end if subscription else None,
        billing_enabled=get_settings().billing_enabled,
    )


@router.get("/account/usage", response_model=AccountUsageRead)
async def account_usage(user: User = Depends(require_verified_user), db: AsyncSession = Depends(get_db)) -> AccountUsageRead:
    context = await get_entitlement_context(db, user.id)
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = start + timedelta(days=1)
    token_count = int(await db.scalar(select(func.coalesce(func.sum(AIUsage.total_tokens), 0)).where(AIUsage.user_id == user.id, AIUsage.created_at >= start, AIUsage.created_at < tomorrow)) or 0)
    requests = int(await db.scalar(select(func.count(GenerationRun.id)).where(GenerationRun.user_id == user.id, GenerationRun.created_at >= start, GenerationRun.created_at < tomorrow)) or 0)
    document_count, storage_bytes = (await db.execute(select(func.count(Document.id), func.coalesce(func.sum(Document.size_bytes), 0)).where(Document.user_id == user.id, Document.deleted_at.is_(None)))).one()
    plan = context["plan"]
    return AccountUsageRead(plan_code=plan.code if plan else "free", daily_tokens=token_count, daily_token_limit=context["limits"].get("daily_token_limit"), generation_requests=requests, document_count=int(document_count or 0), storage_bytes=int(storage_bytes or 0), reset_at=tomorrow)


@router.post("/feedback", response_model=FeedbackRead, status_code=201)
async def submit_feedback(payload: FeedbackCreate, request: Request, user: User = Depends(require_verified_user), _: object = Depends(require_csrf), db: AsyncSession = Depends(get_db)) -> UserFeedback:
    ensure_trusted_origin(request)
    await enforce_rate_limit_async(request, f"feedback:{user.id}", 5)
    row = UserFeedback(user_id=user.id, category=payload.category, message=payload.message, rating=payload.rating)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    await enqueue_privacy_request(row.id)
    return row


@router.get("/support/tickets", response_model=list[SupportTicketRead])
async def list_support_tickets(user: User = Depends(require_verified_user), db: AsyncSession = Depends(get_db), limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> list[SupportTicket]:
    return list(await db.scalars(select(SupportTicket).where(SupportTicket.user_id == user.id).order_by(SupportTicket.updated_at.desc()).offset(offset).limit(limit)))


def _ticket_detail(ticket: SupportTicket, messages: list[SupportTicketMessage]) -> SupportTicketDetail:
    base = SupportTicketRead.model_validate(ticket).model_dump()
    base["messages"] = [{"id": str(item.id), "body": item.body, "author_user_id": str(item.author_user_id), "is_internal": item.is_internal, "created_at": item.created_at} for item in messages if not item.is_internal]
    return SupportTicketDetail.model_validate(base)


@router.post("/support/tickets", response_model=SupportTicketRead, status_code=201)
async def create_support_ticket(payload: SupportTicketCreate, request: Request, user: User = Depends(require_verified_user), _: object = Depends(require_csrf), db: AsyncSession = Depends(get_db)) -> SupportTicket:
    ensure_trusted_origin(request)
    await enforce_rate_limit_async(request, f"support:{user.id}", 5)
    ticket = SupportTicket(user_id=user.id, ticket_number=f"TKT-{uuid4().hex[:12].upper()}", subject=payload.subject.strip(), priority=payload.priority)
    db.add(ticket)
    await db.flush()
    db.add(SupportTicketMessage(ticket_id=ticket.id, author_user_id=user.id, body=payload.body.strip()))
    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.get("/support/tickets/{ticket_id}", response_model=SupportTicketDetail)
async def get_support_ticket(ticket_id: UUID, user: User = Depends(require_verified_user), db: AsyncSession = Depends(get_db)) -> SupportTicketDetail:
    ticket = await db.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.user_id == user.id))
    if ticket is None:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    messages = list(await db.scalars(select(SupportTicketMessage).where(SupportTicketMessage.ticket_id == ticket.id).order_by(SupportTicketMessage.created_at)))
    return _ticket_detail(ticket, messages)


@router.post("/support/tickets/{ticket_id}/messages", response_model=SupportTicketDetail)
async def add_support_message(ticket_id: UUID, payload: SupportMessageCreate, request: Request, user: User = Depends(require_verified_user), _: object = Depends(require_csrf), db: AsyncSession = Depends(get_db)) -> SupportTicketDetail:
    ensure_trusted_origin(request)
    ticket = await db.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.user_id == user.id))
    if ticket is None:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    db.add(SupportTicketMessage(ticket_id=ticket.id, author_user_id=user.id, body=payload.body.strip()))
    ticket.status = "open"
    await db.commit()
    messages = list(await db.scalars(select(SupportTicketMessage).where(SupportTicketMessage.ticket_id == ticket.id).order_by(SupportTicketMessage.created_at)))
    return _ticket_detail(ticket, messages)


@router.get("/account/privacy", response_model=list[PrivacyRequestRead])
async def privacy_requests(user: User = Depends(require_verified_user), db: AsyncSession = Depends(get_db)) -> list[DataPrivacyRequest]:
    return list(await db.scalars(select(DataPrivacyRequest).where(DataPrivacyRequest.user_id == user.id).order_by(DataPrivacyRequest.created_at.desc()).limit(50)))


async def _privacy_request(request_type: str, payload: PrivacyRequestCreate, request: Request, user: User, db: AsyncSession) -> DataPrivacyRequest:
    ensure_trusted_origin(request)
    existing = await db.scalar(select(DataPrivacyRequest).where(DataPrivacyRequest.user_id == user.id, DataPrivacyRequest.request_type == request_type, DataPrivacyRequest.idempotency_key == payload.idempotency_key))
    if existing:
        return existing
    row = DataPrivacyRequest(user_id=user.id, request_type=request_type, idempotency_key=payload.idempotency_key)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/account/data-export", response_model=PrivacyRequestRead, status_code=202)
async def request_data_export(payload: PrivacyRequestCreate, request: Request, user: User = Depends(require_verified_user), _: object = Depends(require_csrf), db: AsyncSession = Depends(get_db)) -> DataPrivacyRequest:
    return await _privacy_request("export", payload, request, user, db)


@router.post("/account/delete-request", response_model=PrivacyRequestRead, status_code=202)
async def request_account_deletion(payload: PrivacyRequestCreate, request: Request, user: User = Depends(require_verified_user), __: object = Depends(require_recent_reauthentication), _: object = Depends(require_csrf), db: AsyncSession = Depends(get_db)) -> DataPrivacyRequest:
    return await _privacy_request("delete", payload, request, user, db)


@router.get("/account/data-export/{request_id}/download")
async def download_data_export(request_id: UUID, user: User = Depends(require_verified_user), db: AsyncSession = Depends(get_db)) -> Response:
    row = await db.scalar(select(DataPrivacyRequest).where(DataPrivacyRequest.id == request_id, DataPrivacyRequest.user_id == user.id, DataPrivacyRequest.request_type == "export", DataPrivacyRequest.status == "completed"))
    if row is None or not row.result_storage_key:
        raise HTTPException(status_code=404, detail="Data export is not ready")
    try:
        content = await asyncio.to_thread(read_private_bytes, row.result_storage_key)
    except Exception as exc:  # noqa: BLE001 - do not expose private storage errors
        raise HTTPException(status_code=503, detail="Data export is temporarily unavailable") from exc
    return Response(content=content, media_type="application/json", headers={"Cache-Control": "no-store", "Content-Disposition": 'attachment; filename="pychat-data-export.json"', "X-Content-Type-Options": "nosniff"})


@router.get("/platform/operations/summary", response_model=OperationsSummary)
async def operations_summary(response: Response, session=Depends(require_platform_permission("platform.operations.read")), db: AsyncSession = Depends(get_db)) -> OperationsSummary:
    del response, session
    since = utc_now() - timedelta(hours=24)
    active_incidents = int(await db.scalar(select(func.count(IncidentRecord.id)).where(IncidentRecord.status != "resolved")) or 0)
    open_tickets = int(await db.scalar(select(func.count(SupportTicket.id)).where(SupportTicket.status.in_(["open", "pending"]))) or 0)
    queued_documents = int(await db.scalar(select(func.count(DocumentProcessingJob.id)).where(DocumentProcessingJob.status.in_(["queued", "running"]))) or 0)
    failed_generations = int(await db.scalar(select(func.count(GenerationRun.id)).where(GenerationRun.status == "failed", GenerationRun.created_at >= since)) or 0)
    cost = await db.scalar(select(func.sum(AIUsage.estimated_cost)).where(AIUsage.created_at >= since))
    flags = int(await db.scalar(select(func.count(FeatureFlag.id)).where(FeatureFlag.enabled.is_(True))) or 0)
    return OperationsSummary(active_incidents=active_incidents, open_support_tickets=open_tickets, queued_documents=queued_documents, failed_generations_24h=failed_generations, estimated_cost_24h=cost, flags_enabled=flags)


@router.get("/platform/operations/feature-flags", response_model=list[FeatureFlagRead])
async def list_feature_flags(session=Depends(require_platform_permission("platform.feature_flags.read")), db: AsyncSession = Depends(get_db)) -> list[FeatureFlag]:
    del session
    return list(await db.scalars(select(FeatureFlag).order_by(FeatureFlag.key)))


@router.get("/platform/operations/plans", response_model=list[PlanRead])
async def platform_plans(session=Depends(require_platform_permission("platform.plans.read")), db: AsyncSession = Depends(get_db)) -> list[PlanRead]:
    del session
    plans = list(await db.scalars(select(Plan).order_by(Plan.sort_order, Plan.code)))
    return [await _plan_read(db, plan) for plan in plans]


@router.patch("/platform/operations/plans/{plan_id}", response_model=PlanRead)
async def update_platform_plan(plan_id: UUID, payload: PlanUpdate, request: Request, session=Depends(require_platform_permission("platform.plans.update", step_up=True)), _: object = Depends(require_platform_csrf), db: AsyncSession = Depends(get_db)) -> PlanRead:
    ensure_trusted_origin(request)
    plan = await db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    values = payload.model_dump(exclude_unset=True)
    entitlements = values.pop("entitlements", None)
    for key, value in values.items():
        setattr(plan, key, value)
    if entitlements is not None:
        existing = {item.feature: item for item in await db.scalars(select(PlanEntitlement).where(PlanEntitlement.plan_id == plan.id))}
        for feature, value in entitlements.items():
            if feature in existing:
                existing[feature].value = value
            else:
                db.add(PlanEntitlement(plan_id=plan.id, feature=feature, value=value))
    await record_audit(db, user_id=session.user_id, action="platform.plan.updated", entity_type="plan", entity_id=plan.id, metadata={"code": plan.code, "keys": list(values)})
    await db.commit()
    await db.refresh(plan)
    return await _plan_read(db, plan)


@router.patch("/platform/operations/feature-flags/{flag_id}", response_model=FeatureFlagRead)
async def update_feature_flag(flag_id: UUID, payload: FeatureFlagUpdate, request: Request, session=Depends(require_platform_permission("platform.feature_flags.update", step_up=True)), _: object = Depends(require_platform_csrf), db: AsyncSession = Depends(get_db)) -> FeatureFlag:
    ensure_trusted_origin(request)
    flag = await db.get(FeatureFlag, flag_id)
    if flag is None:
        raise HTTPException(status_code=404, detail="Feature flag not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(flag, key, value)
    await record_audit(db, user_id=session.user_id, action="platform.feature_flag.updated", entity_type="feature_flag", entity_id=flag.id, metadata={"key": flag.key})
    await db.commit()
    await db.refresh(flag)
    return flag


@router.get("/platform/operations/slo", response_model=list[SLOStatus])
async def slo_status(session=Depends(require_platform_permission("platform.operations.read")), db: AsyncSession = Depends(get_db)) -> list[SLOStatus]:
    del session
    since = utc_now() - timedelta(days=28)
    total = int(await db.scalar(select(func.count(GenerationRun.id)).where(GenerationRun.created_at >= since)) or 0)
    completed = int(await db.scalar(select(func.count(GenerationRun.id)).where(GenerationRun.created_at >= since, GenerationRun.status == "completed")) or 0)
    observed = completed / total if total else None
    return [SLOStatus(name="AI generation completion", target=0.995, observed=observed, error_budget_remaining=((observed - 0.995) / 0.005) if observed is not None else None)]


@router.get("/platform/support/tickets", response_model=list[SupportTicketRead])
async def platform_support_tickets(session=Depends(require_platform_permission("platform.support.read")), db: AsyncSession = Depends(get_db), limit: int = Query(50, ge=1, le=100)) -> list[SupportTicket]:
    del session
    return list(await db.scalars(select(SupportTicket).order_by(SupportTicket.updated_at.desc()).limit(limit)))


@router.patch("/platform/support/tickets/{ticket_id}", response_model=SupportTicketRead)
async def update_platform_ticket(ticket_id: UUID, request: Request, status: str = Query(..., pattern="^(open|pending|resolved|closed)$"), session=Depends(require_platform_permission("platform.support.update", step_up=True)), _: object = Depends(require_platform_csrf), db: AsyncSession = Depends(get_db)) -> SupportTicket:
    ensure_trusted_origin(request)
    ticket = await db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    ticket.status = status
    await record_audit(db, user_id=session.user_id, action="platform.support_ticket.updated", entity_type="support_ticket", entity_id=ticket.id, metadata={"status": status})
    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.post("/platform/support/tickets/{ticket_id}/reply", response_model=SupportTicketDetail)
async def reply_platform_ticket(ticket_id: UUID, payload: SupportMessageCreate, request: Request, session=Depends(require_platform_permission("platform.support.update", step_up=True)), _: object = Depends(require_platform_csrf), db: AsyncSession = Depends(get_db)) -> SupportTicketDetail:
    ensure_trusted_origin(request)
    ticket = await db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    db.add(SupportTicketMessage(ticket_id=ticket.id, author_user_id=session.user_id, body=payload.body.strip()))
    ticket.status = "pending"
    await db.commit()
    messages = list(await db.scalars(select(SupportTicketMessage).where(SupportTicketMessage.ticket_id == ticket.id).order_by(SupportTicketMessage.created_at)))
    return _ticket_detail(ticket, messages)
