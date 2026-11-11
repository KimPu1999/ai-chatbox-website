from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, ConversationFolder, Message
from app.schemas import ConversationCreate, ConversationUpdate, MessageCreate


async def list_for_user(
    db: AsyncSession,
    user_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
) -> list[Conversation]:
    filters = [Conversation.user_id == user_id, Conversation.deleted_at.is_(None)]
    if search and search.strip():
        filters.append(Conversation.title.ilike(f"%{search.strip()}%"))
    result = await db.scalars(
        select(Conversation)
        .where(*filters)
        .order_by(
            Conversation.is_pinned.desc(),
            Conversation.updated_at.desc(),
            Conversation.id.desc(),
        )
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
            Conversation.deleted_at.is_(None),
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


async def update_for_user(
    db: AsyncSession, user_id: UUID, conversation_id: UUID, payload: ConversationUpdate
) -> Conversation | None:
    conversation = await get_for_user(db, user_id, conversation_id)
    if conversation is None:
        return None
    if payload.title is not None:
        conversation.title = payload.title.strip()
    if payload.is_pinned is not None:
        conversation.is_pinned = payload.is_pinned
        conversation.pinned_at = datetime.now(timezone.utc) if payload.is_pinned else None
    if payload.archived is not None:
        conversation.archived_at = datetime.now(timezone.utc) if payload.archived else None
    if "folder_id" in payload.model_fields_set:
        if payload.folder_id is None:
            conversation.folder_id = None
        else:
            folder = await db.scalar(
                select(ConversationFolder).where(
                    ConversationFolder.id == payload.folder_id,
                    ConversationFolder.user_id == user_id,
                )
            )
            if folder is None:
                raise ValueError("FOLDER_NOT_FOUND")
            conversation.folder_id = payload.folder_id
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def soft_delete_for_user(db: AsyncSession, user_id: UUID, conversation_id: UUID) -> bool:
    conversation = await get_for_user(db, user_id, conversation_id)
    if conversation is None:
        return False
    conversation.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return True


async def list_messages_for_user(
    db: AsyncSession,
    user_id: UUID,
    conversation_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[Message]:
    result = await db.scalars(
        select(Message)
        .where(Message.user_id == user_id, Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(result)


async def create_user_message(
    db: AsyncSession,
    user_id: UUID,
    conversation_id: UUID,
    payload: MessageCreate,
) -> Message | None:
    conversation = await get_for_user(db, user_id, conversation_id)
    if conversation is None:
        return None
    message = Message(
        user_id=user_id,
        conversation_id=conversation_id,
        role="user",
        content=payload.content.strip(),
    )
    db.add(message)
    conversation.last_message_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(message)
    return message
