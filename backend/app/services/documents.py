"""Private document storage, extraction, chunking and RAG retrieval.

The database is the source of truth for ownership and processing state. Local
files are stored below a private, non-public directory using random keys. A
Redis/arq worker can call ``process_document_by_id`` in production; the API
uses a database-backed job and a local background task only when Redis is not
configured for local development.
"""

import csv
import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import utc_now
from app.core.config import get_settings
from app.db import SessionLocal
from app.models import (
    ConversationDocument,
    Document,
    DocumentChunk,
    DocumentProcessingJob,
)
from app.services.ai_provider import ProviderRequestError, ProviderUnavailable, get_openai_client

try:
    import magic
except ImportError:  # pragma: no cover - dependency is declared and installed in normal runs
    magic = None

try:
    import tiktoken
except ImportError:  # pragma: no cover - conservative fallback for minimal installs
    tiktoken = None


ALLOWED_DOCUMENTS = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".csv": "text/csv",
}


class DocumentError(ValueError):
    def __init__(self, code: str, message: str | None = None):
        self.code = code
        super().__init__(message or code)


@dataclass
class ParsedSegment:
    text: str
    page_number: int | None
    source_locator: dict


@dataclass
class ParsedDocument:
    segments: list[ParsedSegment]
    page_count: int | None
    status: str = "ready"


@dataclass
class DocumentChunkData:
    content: str
    page_number: int | None
    source_locator: dict
    token_count: int


def _storage_root() -> Path:
    root = Path(get_settings().document_storage_path).expanduser()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root.resolve()


def storage_path(storage_key: str) -> Path:
    root = _storage_root()
    path = (root / storage_key).resolve()
    if root != path and root not in path.parents:
        raise DocumentError("INVALID_STORAGE_KEY")
    return path


def safe_filename(filename: str) -> str:
    value = unicodedata.normalize("NFKC", filename or "document")
    value = Path(value).name
    value = re.sub(r"[^\w.()\- ]", "_", value, flags=re.UNICODE).strip(" .")
    return (value or "document")[:255]


def _normalise_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value).replace("\x00", "")
    return re.sub(r"[ \t\f\v]+", " ", value).strip()


def _detected_mime(data: bytes, extension: str) -> str:
    if magic is not None:
        try:
            detected = magic.from_buffer(data[:4096], mime=True)
            if detected in {"application/pdf", "application/zip", "text/plain", "text/csv"}:
                return detected
        except Exception:  # pragma: no cover - platform libmagic differences
            pass
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"PK\x03\x04"):
        return "application/zip"
    if b"\x00" in data[:4096]:
        return "application/octet-stream"
    if extension in {".txt", ".csv"}:
        return ALLOWED_DOCUMENTS[extension]
    return "application/octet-stream"


def validate_upload(filename: str, data: bytes, declared_type: str | None) -> tuple[str, str]:
    extension = Path(filename or "").suffix.lower()
    if extension not in ALLOWED_DOCUMENTS:
        raise DocumentError("UNSUPPORTED_FILE_TYPE")
    max_bytes = get_settings().document_max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise DocumentError("DOCUMENT_TOO_LARGE")
    detected = _detected_mime(data, extension)
    if extension == ".pdf" and detected != "application/pdf":
        raise DocumentError("FILE_SIGNATURE_MISMATCH")
    if extension == ".docx" and detected not in {
        "application/zip",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }:
        raise DocumentError("FILE_SIGNATURE_MISMATCH")
    if extension in {".txt", ".csv"} and detected in {
        "application/octet-stream",
        "application/pdf",
        "application/zip",
    }:
        raise DocumentError("FILE_SIGNATURE_MISMATCH")
    if declared_type and declared_type not in {
        ALLOWED_DOCUMENTS[extension],
        "application/octet-stream",
        "text/plain",
    }:
        raise DocumentError("MIME_TYPE_MISMATCH")
    return extension, ALLOWED_DOCUMENTS[extension]


def save_private_bytes(user_id: UUID, filename: str, data: bytes) -> tuple[str, str, int]:
    safe_name = safe_filename(filename)
    key = f"{user_id}/{uuid4().hex}_{safe_name}"
    path = storage_path(key)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("xb") as output:
        output.write(data)
    return key, hashlib.sha256(data).hexdigest(), len(data)


def _read_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DocumentError("TEXT_ENCODING_UNSUPPORTED")


def parse_document(path: Path, extension: str) -> ParsedDocument:
    settings = get_settings()
    try:
        data = path.read_bytes()
        if extension == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data), strict=False)
            if reader.is_encrypted:
                raise DocumentError("PDF_ENCRYPTED")
            if len(reader.pages) > settings.document_max_pages:
                raise DocumentError("DOCUMENT_PAGE_LIMIT")
            segments: list[ParsedSegment] = []
            extracted_pages = 0
            for page_index, page in enumerate(reader.pages, start=1):
                text = _normalise_text(page.extract_text() or "")
                if text:
                    extracted_pages += 1
                    segments.append(
                        ParsedSegment(text, page_index, {"type": "page", "page": page_index})
                    )
            if not segments:
                return ParsedDocument([], len(reader.pages), "ocr_required")
            status = "partially_extracted" if extracted_pages < len(reader.pages) else "ready"
            return ParsedDocument(segments, len(reader.pages), status)
        if extension == ".docx":
            from docx import Document as DocxDocument

            document = DocxDocument(io.BytesIO(data))
            segments = []
            for index, paragraph in enumerate(document.paragraphs):
                text = _normalise_text(paragraph.text)
                if text:
                    segments.append(
                        ParsedSegment(text, None, {"type": "paragraph", "index": index})
                    )
            for table_index, table in enumerate(document.tables):
                rows = [
                    " | ".join(_normalise_text(cell.text) for cell in row.cells)
                    for row in table.rows
                ]
                text = _normalise_text("\n".join(row for row in rows if row))
                if text:
                    segments.append(
                        ParsedSegment(text, None, {"type": "table", "index": table_index})
                    )
            return ParsedDocument(segments, None, "ready" if segments else "partially_extracted")
        text = _read_text(data)
        if extension == ".csv":
            stream = io.StringIO(text, newline="")
            reader = csv.reader(stream)
            lines: list[str] = []
            for row_index, row in enumerate(reader):
                if row_index >= settings.document_max_csv_rows:
                    raise DocumentError("CSV_ROW_LIMIT")
                if len(row) > settings.document_max_csv_columns:
                    raise DocumentError("CSV_COLUMN_LIMIT")
                values = [_normalise_text(cell) for cell in row]
                if values:
                    lines.append(" | ".join(values))
            segments = [
                ParsedSegment(line, None, {"type": "row", "row": index + 1})
                for index, line in enumerate(lines)
                if line
            ]
            return ParsedDocument(segments, None, "ready" if segments else "partially_extracted")
        text = _normalise_text(text)
        return ParsedDocument(
            [ParsedSegment(text, None, {"type": "text", "offset": 0})] if text else [],
            None,
            "ready" if text else "partially_extracted",
        )
    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError("DOCUMENT_PARSE_FAILED") from exc


def _encoder():
    if tiktoken is None:
        return None
    try:
        return tiktoken.encoding_for_model(get_settings().embedding_model)
    except Exception:
        try:
            return tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Tokenizer data can be downloaded on first use. A bounded byte
            # fallback keeps local/offline processing deterministic.
            return None


def _tokens(encoder, text: str) -> list[int]:
    return encoder.encode(text, disallowed_special=()) if encoder else list(text.encode("utf-8"))


def _decode(encoder, values: list[int]) -> str:
    if encoder:
        return encoder.decode(values)
    return bytes(values).decode("utf-8", errors="ignore")


def chunk_segments(segments: list[ParsedSegment]) -> list[DocumentChunkData]:
    settings = get_settings()
    encoder = _encoder()
    target = settings.document_chunk_tokens
    overlap = settings.document_chunk_overlap
    chunks: list[DocumentChunkData] = []
    current_tokens: list[int] = []
    current_sources: list[ParsedSegment] = []

    def emit() -> None:
        nonlocal current_tokens, current_sources
        if not current_tokens:
            return
        text = _normalise_text(_decode(encoder, current_tokens))
        if text:
            pages = [item.page_number for item in current_sources if item.page_number]
            unique_sources = {str(item.source_locator) for item in current_sources}
            source = (
                current_sources[0].source_locator
                if len(unique_sources) == 1
                else {
                    "type": "range",
                    "sources": [item.source_locator for item in current_sources],
                }
            )
            chunks.append(
                DocumentChunkData(text, pages[0] if pages else None, source, len(current_tokens))
            )
        current_tokens = current_tokens[-overlap:] if overlap else []
        current_sources = current_sources[-1:] if overlap else []

    for segment in segments:
        tokens = _tokens(encoder, segment.text)
        if not tokens:
            continue
        if len(tokens) > target:
            for start in range(0, len(tokens), max(1, target - overlap)):
                current_tokens.extend(tokens[start : start + target])
                current_sources.append(segment)
                emit()
            continue
        if current_tokens and len(current_tokens) + len(tokens) > target:
            emit()
        current_tokens.extend(tokens)
        current_sources.append(segment)
    emit()
    return chunks


async def embed_texts(texts: list[str]) -> tuple[list[list[float]], int]:
    if not texts:
        return [], 0
    client = get_openai_client()
    try:
        response = await client.embeddings.create(
            model=get_settings().embedding_model,
            input=texts,
            dimensions=get_settings().embedding_dimensions,
        )
    except ProviderUnavailable:
        raise
    except Exception as exc:
        raise ProviderRequestError("EMBEDDING_PROVIDER_FAILED") from exc
    vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
    if any(len(vector) != get_settings().embedding_dimensions for vector in vectors):
        raise DocumentError("EMBEDDING_DIMENSION_MISMATCH")
    usage = getattr(response, "usage", None)
    return vectors, int(getattr(usage, "total_tokens", 0) or 0)


async def process_document_by_id(document_id: UUID) -> None:
    async with SessionLocal() as db:
        document = await db.get(Document, document_id)
        if document is None or document.deleted_at is not None:
            return
        job = await db.scalar(
            select(DocumentProcessingJob)
            .where(DocumentProcessingJob.document_id == document.id)
            .order_by(DocumentProcessingJob.created_at.desc())
        )
        if job is None:
            return
        try:
            document.status = "parsing"
            job.status = "running"
            job.started_at = utc_now()
            job.progress = 10
            await db.commit()
            path = storage_path(document.storage_key)
            parsed = parse_document(path, Path(document.original_filename).suffix.lower())
            document.page_count = parsed.page_count
            if parsed.status == "ocr_required":
                document.status = "ocr_required"
                document.error_code = "OCR_REQUIRED"
                job.status = "failed"
                job.error_code = "OCR_REQUIRED"
                job.finished_at = utc_now()
                await db.commit()
                return
            if not parsed.segments:
                document.status = "failed"
                document.error_code = "DOCUMENT_EMPTY"
                job.status = "failed"
                job.error_code = "DOCUMENT_EMPTY"
                job.finished_at = utc_now()
                await db.commit()
                return
            if (
                sum(len(segment.text) for segment in parsed.segments)
                > get_settings().document_max_extracted_characters
            ):
                raise DocumentError("EXTRACTED_TEXT_LIMIT")
            document.status = "chunking"
            job.progress = 35
            await db.commit()
            chunks = chunk_segments(parsed.segments)
            if not chunks:
                raise DocumentError("DOCUMENT_EMPTY")
            document.status = "embedding"
            job.progress = 55
            await db.commit()
            vectors, embedding_tokens = await embed_texts([chunk.content for chunk in chunks])
            job.embedding_tokens = embedding_tokens
            existing_version = int(
                await db.scalar(
                    select(func.max(DocumentChunk.processing_version)).where(
                        DocumentChunk.document_id == document.id
                    )
                )
                or 0
            )
            next_version = existing_version + 1
            # The old index remains available until the new provider response is complete.
            await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
            db.add_all(
                [
                    DocumentChunk(
                        document_id=document.id,
                        user_id=document.user_id,
                        chunk_index=index,
                        content=chunk.content,
                        page_number=chunk.page_number,
                        source_locator=chunk.source_locator,
                        token_count=chunk.token_count,
                        embedding_model=get_settings().embedding_model,
                        embedding_dimensions=get_settings().embedding_dimensions,
                        embedding=vectors[index],
                        processing_version=next_version,
                    )
                    for index, chunk in enumerate(chunks)
                ]
            )
            document.status = (
                "partially_extracted" if parsed.status == "partially_extracted" else "ready"
            )
            document.error_code = (
                "PARTIAL_TEXT_EXTRACTION" if parsed.status == "partially_extracted" else None
            )
            job.status = "completed"
            job.progress = 100
            job.finished_at = utc_now()
            await db.commit()
        except (DocumentError, ProviderUnavailable, ProviderRequestError) as exc:
            await db.rollback()
            document = await db.get(Document, document_id)
            if document is not None:
                document.status = "failed"
                document.error_code = getattr(exc, "code", "DOCUMENT_PROCESSING_FAILED")
            job = (
                await db.scalar(
                    select(DocumentProcessingJob).where(DocumentProcessingJob.id == job.id)
                )
                if job
                else None
            )
            if job is not None:
                job.status = "failed"
                job.error_code = getattr(exc, "code", "DOCUMENT_PROCESSING_FAILED")
                job.finished_at = utc_now()
            await db.commit()
        except Exception:
            await db.rollback()
            document = await db.get(Document, document_id)
            if document is not None:
                document.status = "failed"
                document.error_code = "DOCUMENT_PROCESSING_FAILED"
            await db.commit()


async def retrieve_chunks(
    db: AsyncSession,
    *,
    user_id: UUID,
    conversation_id: UUID,
    document_ids: list[UUID],
    query: str,
) -> tuple[list[dict[str, str]], list[dict]]:
    """Retrieve owner-scoped chunks; no client-provided text is trusted."""
    if not document_ids:
        return [], []
    allowed = list(
        await db.scalars(
            select(ConversationDocument.document_id).where(
                ConversationDocument.conversation_id == conversation_id,
                ConversationDocument.attached_by == user_id,
                ConversationDocument.document_id.in_(document_ids),
            )
        )
    )
    if not allowed:
        raise DocumentError("DOCUMENT_NOT_ATTACHED")
    if not get_settings().openai_api_key:
        raise DocumentError("EMBEDDING_PROVIDER_UNAVAILABLE")
    vectors, _ = await embed_texts([query])
    query_vector = vectors[0]
    distance = DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
    rows = list(
        await db.execute(
            select(DocumentChunk, Document, distance)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.user_id == user_id,
                DocumentChunk.document_id.in_(allowed),
                Document.status.in_(["ready", "partially_extracted"]),
                Document.deleted_at.is_(None),
                DocumentChunk.embedding.is_not(None),
            )
            .order_by(distance.asc(), DocumentChunk.chunk_index.asc())
            .limit(get_settings().document_retrieval_top_k)
        )
    )
    context: list[dict[str, str]] = []
    citations: list[dict] = []
    for chunk, document, chunk_distance in rows:
        citation = {
            "document_id": str(document.id),
            "document_name": document.original_filename,
            "chunk_id": str(chunk.id),
            "page_number": chunk.page_number,
            "source_locator": chunk.source_locator,
            "snippet": chunk.content[:500],
            "relevance": round(max(0.0, 1.0 - float(chunk_distance or 0.0)), 4),
        }
        citations.append(citation)
        context.append(
            {
                "role": "user",
                "content": f"Document evidence ({document.original_filename}):\n{chunk.content}",
            }
        )
    return context, citations


async def enqueue_processing(document_id: UUID) -> None:
    settings = get_settings()
    if settings.redis_url:
        try:
            from arq import create_pool
            from arq.connections import RedisSettings

            pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            await pool.enqueue_job("process_document", str(document_id))
            await pool.close()
            return
        except Exception:
            # The durable row remains visible and can be recovered by the worker.
            pass
    await process_document_by_id(document_id)
