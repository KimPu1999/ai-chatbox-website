from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Message


def estimate_tokens(value: str) -> int:
    return max(1, len(value) // 4)


async def build_context(db: AsyncSession, *, user_id, conversation_id) -> list[dict[str, str]]:
    rows = await db.scalars(
        select(Message)
        .where(
            Message.user_id == user_id,
            Message.conversation_id == conversation_id,
            Message.status == "completed",
            Message.superseded_at.is_(None),
            Message.role.in_(["user", "assistant"]),
        )
        .order_by(Message.created_at.asc(), Message.sequence.asc(), Message.id.asc())
    )
    messages = list(rows)
    budget = get_settings().ai_context_token_budget
    selected: list[Message] = []
    used = 0
    for message in reversed(messages):
        cost = estimate_tokens(message.content)
        if selected and used + cost > budget:
            break
        selected.append(message)
        used += cost
    selected.reverse()
    return [{"role": message.role, "content": message.content} for message in selected]
