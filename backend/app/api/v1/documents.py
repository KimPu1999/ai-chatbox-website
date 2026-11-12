import asyncio
from datetime import datetime, timezone
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ensure_trusted_origin, require_csrf, require_verified_user
from app.core.config import get_settings
from app.db import get_db
from app.models import (
    Conversation,
    ConversationDocument,
    Document,
    DocumentChunk,
    DocumentProcessingJob,
    User,
)
from app.schemas import (
    ConversationDocumentRead,
    DocumentAttachRequest,
    DocumentPage,
    DocumentPreviewChunk,
    DocumentPreviewRead,
    DocumentRead,
    DocumentStatusRead,
    DocumentUpdate,
)
from app.services.documents import (
    DocumentError,
    delete_private_bytes,
    enqueue_processing,
    read_private_bytes,
    safe_filename,
    save_private_bytes,
    storage_path,
    validate_upload,
)
from app.services.entitlements import get_entitlement_context
from app.services.storage import StorageError

router = APIRouter(tags=["documents"])


async def _owned_document(db: AsyncSession, user_id: UUID, document_id: UUID) -> Document | None:
    return await db.scalar(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )


@router.post("/documents", response_model=DocumentRead, status_code=201)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(require_verified_user),
    _: object = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> DocumentRead:
    ensure_trusted_origin(request)
    settings = get_settings()
    if settings.document_storage_backend not in {"local", "r2"}:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "DOCUMENT_STORAGE_UNAVAILABLE",
                "message": "Configured storage backend is not available",
            },
        )
    if settings.document_malware_scan_required:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "MALWARE_SCANNER_REQUIRED",
                "message": "Document scanning is required but not configured",
            },
        )
    quota_result = await db.execute(
        select(func.count(Document.id), func.coalesce(func.sum(Document.size_bytes), 0)).where(
            Document.user_id == user.id, Document.deleted_at.is_(None)
        )
    )
    count, total = quota_result.one()
    entitlement = await get_entitlement_context(db, user.id)
    limits = entitlement["limits"]
    document_limit = min(
        settings.document_max_files_per_user,
        int(limits.get("document_count_limit", settings.document_max_files_per_user)),
    )
    storage_limit = min(
        settings.document_max_storage_mb_per_user * 1024 * 1024,
        int(
            limits.get(
                "storage_size_limit_bytes",
                settings.document_max_storage_mb_per_user * 1024 * 1024,
            )
        ),
    )
    if count >= document_limit:
        raise HTTPException(
            status_code=413,
            detail={"code": "DOCUMENT_FILE_QUOTA", "message": "Document file quota reached"},
        )
    if int(total or 0) >= storage_limit:
        raise HTTPException(
            status_code=413,
            detail={"code": "DOCUMENT_STORAGE_QUOTA", "message": "Document storage quota reached"},
        )
    data = bytearray()
    max_bytes = settings.document_max_upload_mb * 1024 * 1024
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail={
                    "code": "DOCUMENT_TOO_LARGE",
                    "message": "Document exceeds the upload limit",
                },
            )
    try:
        extension, mime_type = validate_upload(
            file.filename or "document", bytes(data), file.content_type
        )
        storage_key, digest, size = await asyncio.to_thread(
            save_private_bytes,
            user.id,
            file.filename or "document",
            bytes(data),
        )
    except DocumentError as exc:
        raise HTTPException(
            status_code=422, detail={"code": exc.code, "message": "Document validation failed"}
        ) from exc
    except StorageError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "DOCUMENT_STORAGE_UNAVAILABLE",
                "message": "Document storage is unavailable",
            },
        ) from exc
    document = Document(
        user_id=user.id,
        original_filename=safe_filename(file.filename or "document"),
        storage_key=storage_key,
        mime_type=mime_type,
        size_bytes=size,
        sha256_hash=digest,
        status="queued",
    )
    db.add(document)
    await db.flush()
    db.add(DocumentProcessingJob(document_id=document.id, user_id=user.id, status="queued"))
    await db.commit()
    await db.refresh(document)
    background_tasks.add_task(enqueue_processing, document.id)
    return document


@router.get("/documents", response_model=DocumentPage)
async def list_documents(
    user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: UUID | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
) -> DocumentPage:
    query = select(Document).where(Document.user_id == user.id, Document.deleted_at.is_(None))
    if search:
        query = query.where(Document.original_filename.ilike(f"%{search.strip()}%"))
    if cursor:
        anchor = await db.get(Document, cursor)
        if anchor and anchor.user_id == user.id:
            query = query.where(
                (Document.created_at < anchor.created_at)
                | ((Document.created_at == anchor.created_at) & (Document.id < anchor.id))
            )
    rows = list(
        await db.scalars(
            query.order_by(Document.created_at.desc(), Document.id.desc()).limit(limit + 1)
        )
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    return DocumentPage(
        items=rows, next_cursor=str(rows[-1].id) if has_more and rows else None, has_more=has_more
    )


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: UUID,
    user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentRead:
    document = await _owned_document(db, user.id, document_id)
    if document is None or document.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/documents/{document_id}/status", response_model=DocumentStatusRead)
async def get_document_status(
    document_id: UUID,
    user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentStatusRead:
    document = await _owned_document(db, user.id, document_id)
    if document is None or document.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Document not found")
    job = await db.scalar(
        select(DocumentProcessingJob)
        .where(DocumentProcessingJob.document_id == document.id)
        .order_by(DocumentProcessingJob.created_at.desc())
    )
    return DocumentStatusRead(
        document_id=document.id,
        status=document.status,
        progress=job.progress if job else (100 if document.status == "ready" else 0),
        error_code=document.error_code,
        attempt_count=job.attempt_count if job else 0,
    )


@router.get("/documents/{document_id}/preview", response_model=DocumentPreviewRead)
async def preview_document(
    document_id: UUID,
    user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentPreviewRead:
    document = await _owned_document(db, user.id, document_id)
    if document is None or document.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Document not found")
    chunks = list(
        await db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.chunk_index)
            .limit(100)
        )
    )
    return DocumentPreviewRead(
        document=document, chunks=[DocumentPreviewChunk.model_validate(chunk) for chunk in chunks]
    )


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: UUID,
    user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    document = await _owned_document(db, user.id, document_id)
    if document is None or document.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Document not found")
    safe_filename = document.original_filename.replace(chr(34), "_")
    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'attachment; filename="{safe_filename}"',
    }
    if get_settings().document_storage_backend == "local":
        path = storage_path(document.storage_key)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Document file not found")
        return FileResponse(path, media_type=document.mime_type, headers=headers)
    try:
        data = await asyncio.to_thread(read_private_bytes, document.storage_key)
    except Exception as exc:  # noqa: BLE001 - do not disclose private storage details
        raise HTTPException(status_code=404, detail="Document file not found") from exc
    return Response(
        content=data,
        media_type=document.mime_type,
        headers=headers,
    )


@router.patch("/documents/{document_id}", response_model=DocumentRead)
async def update_document(
    document_id: UUID,
    payload: DocumentUpdate,
    request: Request,
    user: User = Depends(require_verified_user),
    _: object = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> DocumentRead:
    ensure_trusted_origin(request)
    document = await _owned_document(db, user.id, document_id)
    if document is None or document.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Document not found")
    if payload.original_filename is not None:
        document.original_filename = safe_filename(payload.original_filename)
    await db.commit()
    await db.refresh(document)
    return document


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    request: Request,
    user: User = Depends(require_verified_user),
    _: object = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    ensure_trusted_origin(request)
    document = await _owned_document(db, user.id, document_id)
    if document is None or document.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Document not found")
    document.deleted_at = datetime.now(timezone.utc)
    document.status = "cancelled"
    await db.commit()
    try:
        await asyncio.to_thread(delete_private_bytes, document.storage_key)
    except Exception:
        pass
    return Response(status_code=204)


@router.post("/documents/{document_id}/reprocess", response_model=DocumentStatusRead)
async def reprocess_document(
    document_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_verified_user),
    _: object = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> DocumentStatusRead:
    ensure_trusted_origin(request)
    document = await _owned_document(db, user.id, document_id)
    if document is None or document.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Document not found")
    document.status = "queued"
    document.error_code = None
    previous_attempt = int(
        await db.scalar(
            select(func.max(DocumentProcessingJob.attempt_count)).where(
                DocumentProcessingJob.document_id == document.id
            )
        )
        or 0
    )
    job = DocumentProcessingJob(
        document_id=document.id,
        user_id=user.id,
        status="queued",
        attempt_count=previous_attempt + 1,
    )
    db.add(job)
    await db.commit()
    background_tasks.add_task(enqueue_processing, document.id)
    return DocumentStatusRead(document_id=document.id, status=document.status, progress=0)


@router.post(
    "/conversations/{conversation_id}/documents", response_model=list[ConversationDocumentRead]
)
async def attach_documents(
    conversation_id: UUID,
    payload: DocumentAttachRequest,
    request: Request,
    user: User = Depends(require_verified_user),
    _: object = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationDocumentRead]:
    ensure_trusted_origin(request)
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
            Conversation.deleted_at.is_(None),
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    documents = list(
        await db.scalars(
            select(Document).where(
                Document.id.in_(payload.document_ids),
                Document.user_id == user.id,
                Document.deleted_at.is_(None),
                Document.status.in_(["ready", "partially_extracted"]),
            )
        )
    )
    if len(documents) != len(payload.document_ids):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DOCUMENT_NOT_READY",
                "message": "All selected documents must be owned and ready",
            },
        )
    existing = {
        row.document_id: row
        for row in await db.scalars(
            select(ConversationDocument).where(
                ConversationDocument.conversation_id == conversation_id,
                ConversationDocument.document_id.in_(payload.document_ids),
                ConversationDocument.attached_by == user.id,
            )
        )
    }
    rows = [
        existing.get(document.id)
        or ConversationDocument(
            conversation_id=conversation_id, document_id=document.id, attached_by=user.id
        )
        for document in documents
    ]
    for row in rows:
        db.add(row)
    await db.commit()
    return [ConversationDocumentRead.model_validate(row) for row in rows]


@router.delete("/conversations/{conversation_id}/documents/{document_id}", status_code=204)
async def detach_document(
    conversation_id: UUID,
    document_id: UUID,
    request: Request,
    user: User = Depends(require_verified_user),
    _: object = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    ensure_trusted_origin(request)
    result = await db.execute(
        select(ConversationDocument).where(
            ConversationDocument.conversation_id == conversation_id,
            ConversationDocument.document_id == document_id,
            ConversationDocument.attached_by == user.id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)
