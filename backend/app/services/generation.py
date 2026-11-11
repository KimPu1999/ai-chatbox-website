from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import utc_now
from app.core.config import get_settings
from app.models import AIUsage, Conversation, GenerationRun, Message
from app.services.context import build_context


async def get_owned_conversation(
    db: AsyncSession, user_id: UUID, conversation_id: UUID
) -> Conversation | None:
    return await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.deleted_at.is_(None),
        )
    )


async def active_run_count(db: AsyncSession, user_id: UUID) -> int:
    return int(
        await db.scalar(
            select(func.count(GenerationRun.id)).where(
                GenerationRun.user_id == user_id, GenerationRun.status.in_(["queued", "streaming"])
            )
        )
        or 0
    )


async def daily_token_count(db: AsyncSession, user_id: UUID) -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(
        await db.scalar(
            select(func.coalesce(func.sum(AIUsage.total_tokens), 0)).where(
                AIUsage.user_id == user_id,
                AIUsage.created_at >= start,
            )
        )
        or 0
    )


async def recover_stale_runs(db: AsyncSession, user_id: UUID) -> None:
    cutoff = utc_now() - timedelta(seconds=get_settings().ai_timeout_seconds * 2)
    stale = await db.scalars(
        select(GenerationRun.id).where(
            GenerationRun.user_id == user_id,
            GenerationRun.status.in_(["queued", "streaming"]),
            GenerationRun.created_at < cutoff,
        )
    )
    ids = list(stale)
    if not ids:
        return
    await db.execute(
        update(GenerationRun)
        .where(GenerationRun.id.in_(ids))
        .values(status="failed", error_code="STALE_RUN_RECOVERED", completed_at=utc_now())
    )
    await db.execute(
        update(Message)
        .where(Message.generation_run_id.in_(ids), Message.status == "streaming")
        .values(status="failed")
    )
    await db.commit()


async def create_generation(
    db: AsyncSession,
    *,
    user_id: UUID,
    conversation_id: UUID,
    content: str | None,
    model: str,
    idempotency_key: str,
    regenerate: bool = False,
) -> tuple[GenerationRun | None, Message | None, list[dict[str, str]]]:
    await recover_stale_runs(db, user_id)
    existing = await db.scalar(
        select(GenerationRun).where(
            GenerationRun.user_id == user_id, GenerationRun.idempotency_key == idempotency_key
        )
    )
    if existing:
        return existing, None, []
    conversation = await get_owned_conversation(db, user_id, conversation_id)
    if conversation is None:
        return None, None, []
    if await active_run_count(db, user_id) >= get_settings().ai_max_concurrent_generations:
        raise ValueError("AI_CONCURRENCY_LIMIT")
    if regenerate:
        previous = await db.scalar(
            select(Message)
            .where(
                Message.user_id == user_id,
                Message.conversation_id == conversation_id,
                Message.role == "assistant",
                Message.status == "completed",
                Message.superseded_at.is_(None),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
        )
        if previous:
            previous.status = "superseded"
            previous.superseded_at = utc_now()
    if content and not regenerate:
        user_message = Message(
            user_id=user_id,
            conversation_id=conversation_id,
            role="user",
            content=content,
            status="completed",
            sequence=0,
        )
        db.add(user_message)
        await db.flush()
    context = await build_context(db, user_id=user_id, conversation_id=conversation_id)
    run = GenerationRun(
        user_id=user_id,
        conversation_id=conversation_id,
        model=model,
        idempotency_key=idempotency_key,
    )
    db.add(run)
    await db.flush()
    last_sequence = int(
        await db.scalar(
            select(func.coalesce(func.max(Message.sequence), 0)).where(
                Message.conversation_id == conversation_id, Message.user_id == user_id
            )
        )
        or 0
    )
    assistant = Message(
        user_id=user_id,
        conversation_id=conversation_id,
        role="assistant",
        content="",
        generation_run_id=run.id,
        status="streaming",
        sequence=last_sequence + 1,
        version=1,
    )
    db.add(assistant)
    await db.commit()
    await db.refresh(run)
    await db.refresh(assistant)
    return run, assistant, context


async def set_run_status(
    db: AsyncSession,
    run_id: UUID,
    status: str,
    *,
    error_code: str | None = None,
    provider_response_id: str | None = None,
) -> None:
    run = await db.get(GenerationRun, run_id)
    if run is None:
        return
    run.status = status
    run.error_code = error_code
    run.provider_response_id = provider_response_id or run.provider_response_id
    if status == "streaming":
        run.started_at = utc_now()
    if status in {"completed", "cancelled", "failed", "incomplete"}:
        run.completed_at = utc_now()
    await db.commit()


async def append_usage(
    db: AsyncSession,
    *,
    run_id: UUID,
    user_id: UUID,
    message_id: UUID,
    model: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    provider_response_id: str | None,
    confirmed: bool,
) -> None:
    existing = await db.scalar(select(AIUsage).where(AIUsage.generation_run_id == run_id))
    if existing:
        return
    db.add(
        AIUsage(
            generation_run_id=run_id,
            user_id=user_id,
            message_id=message_id,
            model=model,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            total_tokens=total_tokens,
            provider_response_id=provider_response_id,
            usage_confirmed=confirmed,
            pricing_version=get_settings().ai_pricing_version,
        )
    )
    await db.commit()


async def finalize_message(db: AsyncSession, message_id: UUID, content: str, status: str) -> None:
    message = await db.get(Message, message_id)
    if message is None:
        return
    message.content = content
    message.status = status
    await db.commit()
