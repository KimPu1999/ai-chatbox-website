from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ensure_trusted_origin, require_csrf, require_verified_user
from app.db import check_database_connection, get_db
from app.models import Session, User
from app.repositories.conversations import (
    create_user_message,
    get_for_user,
    list_messages_for_user,
    soft_delete_for_user,
    update_for_user,
)
from app.schemas import (
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    DatabaseHealthResponse,
    HealthResponse,
    MessageCreate,
    MessageRead,
    ModelOption,
)
from app.services.conversations import create_conversation, list_conversations

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="pychat-api")


@router.get("/health/database", response_model=DatabaseHealthResponse, tags=["health"])
async def database_health() -> DatabaseHealthResponse:
    await check_database_connection()
    return DatabaseHealthResponse(status="ok", database="postgresql")


@router.get("/conversations", response_model=list[ConversationRead], tags=["conversations"])
async def get_conversations(
    user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, max_length=200),
) -> list[ConversationRead]:
    return await list_conversations(db, user.id, limit=limit, offset=offset, search=search)


@router.post(
    "/conversations", response_model=ConversationRead, status_code=201, tags=["conversations"]
)
async def post_conversation(
    payload: ConversationCreate,
    request: Request,
    user: User = Depends(require_verified_user),
    _: Session = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> ConversationRead:
    ensure_trusted_origin(request)
    return await create_conversation(db, user.id, payload)


@router.get(
    "/conversations/{conversation_id}", response_model=ConversationRead, tags=["conversations"]
)
async def get_conversation(
    conversation_id: UUID,
    user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationRead:
    conversation = await get_for_user(db, user.id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.patch(
    "/conversations/{conversation_id}", response_model=ConversationRead, tags=["conversations"]
)
async def patch_conversation(
    conversation_id: UUID,
    payload: ConversationUpdate,
    request: Request,
    user: User = Depends(require_verified_user),
    _: Session = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> ConversationRead:
    ensure_trusted_origin(request)
    conversation = await update_for_user(db, user.id, conversation_id, payload)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.delete("/conversations/{conversation_id}", status_code=204, tags=["conversations"])
async def delete_conversation(
    conversation_id: UUID,
    request: Request,
    user: User = Depends(require_verified_user),
    _: Session = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    ensure_trusted_origin(request)
    if not await soft_delete_for_user(db, user.id, conversation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return Response(status_code=204)


@router.get(
    "/conversations/{conversation_id}/messages", response_model=list[MessageRead], tags=["messages"]
)
async def get_messages(
    conversation_id: UUID,
    user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[MessageRead]:
    if await get_for_user(db, user.id, conversation_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return await list_messages_for_user(db, user.id, conversation_id, limit=limit, offset=offset)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageRead,
    status_code=201,
    tags=["messages"],
)
async def post_message(
    conversation_id: UUID,
    payload: MessageCreate,
    request: Request,
    user: User = Depends(require_verified_user),
    _: Session = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> MessageRead:
    ensure_trusted_origin(request)
    message = await create_user_message(db, user.id, conversation_id, payload)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return message


@router.get("/models", response_model=list[ModelOption], tags=["models"])
async def get_models(user: User = Depends(require_verified_user)) -> list[ModelOption]:
    return []
