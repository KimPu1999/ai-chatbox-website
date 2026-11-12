"""Durable privacy request processing for exports and account deletion."""

# ruff: noqa: E501

import asyncio
import json
from uuid import UUID

from sqlalchemy import select

from app.auth.security import utc_now
from app.core.config import get_settings
from app.db import SessionLocal
from app.models import Conversation, DataPrivacyRequest, Document, Message, User
from app.services.documents import delete_private_bytes, save_private_bytes


async def enqueue_privacy_request(request_id: UUID) -> None:
    settings = get_settings()
    if settings.redis_url:
        try:
            from arq import create_pool
            from arq.connections import RedisSettings

            pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            await pool.enqueue_job("process_privacy_request", str(request_id))
            await pool.close()
            return
        except Exception:  # noqa: BLE001 - the queued DB row remains recoverable
            pass


async def process_privacy_request(request_id: UUID) -> None:
    async with SessionLocal() as db:
        request = await db.get(DataPrivacyRequest, request_id)
        if request is None or request.status in {"completed", "cancelled"}:
            return
        request.status = "processing"
        await db.commit()
        try:
            user = await db.get(User, request.user_id)
            if user is None:
                raise RuntimeError("USER_NOT_FOUND")
            if request.request_type == "export":
                conversations = list(await db.scalars(select(Conversation).where(Conversation.user_id == user.id)))
                export = {"schema_version": "1.0", "user": {"id": str(user.id), "email": user.email, "created_at": user.created_at.isoformat()}, "conversations": []}
                for conversation in conversations:
                    messages = list(await db.scalars(select(Message).where(Message.conversation_id == conversation.id, Message.user_id == user.id).order_by(Message.sequence, Message.created_at)))
                    export["conversations"].append({"id": str(conversation.id), "title": conversation.title, "created_at": conversation.created_at.isoformat(), "messages": [{"role": item.role, "content": item.content, "created_at": item.created_at.isoformat()} for item in messages]})
                data = json.dumps(export, ensure_ascii=False).encode("utf-8")
                key, _, _ = await asyncio.to_thread(
                    save_private_bytes, user.id, "pychat-data-export.json", data
                )
                request.result_storage_key = key
            else:
                documents = list(await db.scalars(select(Document).where(Document.user_id == user.id)))
                for document in documents:
                    await asyncio.to_thread(delete_private_bytes, document.storage_key)
                user.account_status = "deleted"
                user.is_active = False
            request.status = "completed"
            request.finished_at = utc_now()
            await db.commit()
        except Exception:
            request.status = "failed"
            request.error_code = "PRIVACY_PROCESSING_FAILED"
            request.finished_at = utc_now()
            await db.commit()
