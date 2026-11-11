from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation
from app.schemas import ConversationCreate


async def list_for_user(
    db: AsyncSession, user_id: UUID, *, limit: int = 50, offset: int = 0
) -> list[Conversation]:
    result = await db.scalars(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result)


async def get_for_user(
    db: AsyncSession, user_id: UUID, conversation_id: UUID
) -> Conversation | None:
    return await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )


async def create_for_user(
    db: AsyncSession, user_id: UUID, payload: ConversationCreate
) -> Conversation:
    conversation = Conversation(user_id=user_id, title=payload.title.strip())
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation
