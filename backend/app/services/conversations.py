from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation
from app.repositories.conversations import create_for_user, list_for_user
from app.schemas import ConversationCreate


async def list_conversations(
    db: AsyncSession, user_id: UUID, *, limit: int = 50, offset: int = 0
) -> list[Conversation]:
    return await list_for_user(db, user_id, limit=limit, offset=offset)


async def create_conversation(
    db: AsyncSession, user_id: UUID, payload: ConversationCreate
) -> Conversation:
    return await create_for_user(db, user_id, payload)
