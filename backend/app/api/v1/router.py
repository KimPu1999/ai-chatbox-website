from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ensure_trusted_origin, require_csrf, require_verified_user
from app.db import check_database_connection, get_db
from app.models import Session, User
from app.schemas import ConversationCreate, ConversationRead, DatabaseHealthResponse, HealthResponse
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
) -> list[ConversationRead]:
    return await list_conversations(db, user.id, limit=limit, offset=offset)


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
