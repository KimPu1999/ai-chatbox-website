import base64
import json
from datetime import datetime, timedelta
from secrets import token_urlsafe
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password, hash_token, utc_now
from app.models import (
    Conversation,
    ConversationBulkJob,
    ConversationFolder,
    ConversationShare,
    Message,
)
from app.schemas import (
    BulkActionRequest,
    FolderCreate,
    FolderUpdate,
    ShareCreate,
)


def _encode_cursor(value: dict) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(value: str | None) -> dict | None:
    if not value:
        return None
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(padded).decode())
        if not {"timestamp", "id", "pinned"} <= decoded.keys():
            return None
        return decoded
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def _conversation_sort_key():
    return case((Conversation.pinned_at.is_not(None), 1), else_=0)


def _conversation_time_key():
    return func.coalesce(
        Conversation.last_message_at, Conversation.updated_at, Conversation.created_at
    )


async def list_conversations_page(
    db: AsyncSession,
    user_id: UUID,
    *,
    limit: int,
    cursor: str | None,
    include_archived: bool,
    include_deleted: bool,
    folder_id: UUID | None,
    search: str | None = None,
) -> tuple[list[Conversation], str | None, bool]:
    filters = [Conversation.user_id == user_id]
    if not include_deleted:
        filters.append(Conversation.deleted_at.is_(None))
    if not include_archived:
        filters.append(Conversation.archived_at.is_(None))
    if folder_id is not None:
        filters.append(Conversation.folder_id == folder_id)
    if search and search.strip():
        filters.append(Conversation.title.ilike(f"%{search.strip()}%"))
    sort_key = _conversation_sort_key()
    time_key = _conversation_time_key()
    decoded = _decode_cursor(cursor)
    if cursor and decoded is None:
        raise ValueError("INVALID_CURSOR")
    if decoded:
        cursor_time = datetime.fromisoformat(decoded["timestamp"])
        cursor_id = UUID(decoded["id"])
        pinned = int(decoded["pinned"])
        filters.append(
            or_(
                sort_key < pinned,
                and_(sort_key == pinned, time_key < cursor_time),
                and_(sort_key == pinned, time_key == cursor_time, Conversation.id < cursor_id),
            )
        )
    result = await db.scalars(
        select(Conversation)
        .where(*filters)
        .order_by(sort_key.desc(), time_key.desc(), Conversation.id.desc())
        .limit(limit + 1)
    )
    items = list(result)
    has_more = len(items) > limit
    items = items[:limit]
    next_cursor = None
    if has_more and items:
        item = items[-1]
        item_time = item.last_message_at or item.updated_at or item.created_at
        next_cursor = _encode_cursor(
            {
                "pinned": 1 if item.pinned_at else 0,
                "timestamp": item_time.isoformat(),
                "id": str(item.id),
            }
        )
    return items, next_cursor, has_more


async def create_folder(
    db: AsyncSession, user_id: UUID, payload: FolderCreate
) -> ConversationFolder:
    name = payload.name.strip()
    folder = ConversationFolder(
        user_id=user_id,
        name=name,
        normalized_name=name.casefold(),
        sort_order=payload.sort_order,
    )
    db.add(folder)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(folder)
    return folder


async def get_folder(db: AsyncSession, user_id: UUID, folder_id: UUID) -> ConversationFolder | None:
    return await db.scalar(
        select(ConversationFolder).where(
            ConversationFolder.id == folder_id, ConversationFolder.user_id == user_id
        )
    )


async def update_folder(
    db: AsyncSession, user_id: UUID, folder_id: UUID, payload: FolderUpdate
) -> ConversationFolder | None:
    folder = await get_folder(db, user_id, folder_id)
    if folder is None:
        return None
    if payload.name is not None:
        folder.name = payload.name.strip()
        folder.normalized_name = folder.name.casefold()
    if payload.sort_order is not None:
        folder.sort_order = payload.sort_order
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(folder)
    return folder


async def delete_folder(db: AsyncSession, user_id: UUID, folder_id: UUID) -> bool:
    folder = await get_folder(db, user_id, folder_id)
    if folder is None:
        return False
    await db.execute(
        update(Conversation)
        .where(Conversation.user_id == user_id, Conversation.folder_id == folder_id)
        .values(folder_id=None)
    )
    await db.delete(folder)
    await db.commit()
    return True


async def apply_bulk_action(
    db: AsyncSession, user_id: UUID, payload: BulkActionRequest
) -> ConversationBulkJob:
    conversations = list(
        await db.scalars(
            select(Conversation).where(
                Conversation.user_id == user_id, Conversation.id.in_(payload.conversation_ids)
            )
        )
    )
    if len(conversations) != len(payload.conversation_ids):
        raise ValueError("CONVERSATION_OWNERSHIP_REQUIRED")
    if payload.action == "move_to_folder":
        if payload.folder_id is None or await get_folder(db, user_id, payload.folder_id) is None:
            raise ValueError("FOLDER_NOT_FOUND")
    now = utc_now()
    for conversation in conversations:
        if payload.action == "archive":
            conversation.archived_at = now
        elif payload.action == "unarchive":
            conversation.archived_at = None
        elif payload.action == "pin":
            conversation.is_pinned = True
            conversation.pinned_at = now
        elif payload.action == "unpin":
            conversation.is_pinned = False
            conversation.pinned_at = None
        elif payload.action == "move_to_folder":
            conversation.folder_id = payload.folder_id
        elif payload.action == "soft_delete":
            conversation.deleted_at = now
        elif payload.action == "restore":
            conversation.deleted_at = None
    job = ConversationBulkJob(
        user_id=user_id,
        action=payload.action,
        status="completed",
        total_count=len(conversations),
        processed_count=len(conversations),
        finished_at=now,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def create_share(
    db: AsyncSession, user_id: UUID, conversation: Conversation, payload: ShareCreate
) -> tuple[ConversationShare, str]:
    allowed_ids = set(payload.message_ids or [])
    messages = list(
        await db.scalars(
            select(Message)
            .where(
                Message.user_id == user_id,
                Message.conversation_id == conversation.id,
                Message.status == "completed",
                Message.superseded_at.is_(None),
            )
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
    )
    if allowed_ids:
        unknown = allowed_ids - {message.id for message in messages}
        if unknown:
            raise ValueError("MESSAGE_NOT_FOUND")
        messages = [message for message in messages if message.id in allowed_ids]
    raw_token = token_urlsafe(32)
    snapshot = {
        "schema_version": "1.0",
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
        "messages": [
            {
                "id": str(message.id),
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
                "version": message.version,
            }
            for message in messages
            if message.role in {"user", "assistant"}
        ],
    }
    share = ConversationShare(
        owner_id=user_id,
        conversation_id=conversation.id,
        token_hash=hash_token(raw_token),
        snapshot_json=snapshot,
        password_hash=hash_password(payload.password) if payload.password else None,
        expires_at=(utc_now() + timedelta(days=payload.expires_in_days))
        if payload.expires_in_days
        else None,
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)
    return share, raw_token


async def list_shares(
    db: AsyncSession, user_id: UUID, conversation_id: UUID
) -> list[ConversationShare]:
    return list(
        await db.scalars(
            select(ConversationShare)
            .where(
                ConversationShare.owner_id == user_id,
                ConversationShare.conversation_id == conversation_id,
            )
            .order_by(ConversationShare.created_at.desc())
        )
    )


async def revoke_share(db: AsyncSession, user_id: UUID, share_id: UUID) -> bool:
    share = await db.scalar(
        select(ConversationShare).where(
            ConversationShare.id == share_id, ConversationShare.owner_id == user_id
        )
    )
    if share is None:
        return False
    if share.revoked_at is None:
        share.revoked_at = utc_now()
        await db.commit()
    return True


async def get_public_share(db: AsyncSession, raw_token: str) -> ConversationShare | None:
    share = await db.scalar(
        select(ConversationShare).where(ConversationShare.token_hash == hash_token(raw_token))
    )
    if share is None or share.revoked_at is not None:
        return None
    if share.expires_at is not None and share.expires_at <= utc_now():
        return None
    share.last_accessed_at = utc_now()
    await db.commit()
    return share
