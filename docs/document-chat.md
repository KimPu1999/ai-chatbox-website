# Document chat

Phase 7 adds private PDF, DOCX, TXT and CSV documents to PyChat AI. Uploads are stored below `DOCUMENT_STORAGE_PATH` with a random owner-scoped key and are never served from the frontend public directory. The API validates the extension, detected signature, size, Unicode decoding and parser limits before creating a PostgreSQL processing job.

## Setup

Copy the document settings from `.env.example`. PostgreSQL must have the `vector` extension available. `alembic upgrade head` runs revision `0008_documents_rag`, enables the extension, creates `VECTOR(1536)` chunks and an HNSW cosine index. The embedding dimension and model are stored with every chunk; changing dimensions requires a deliberate re-embedding migration.

The local development path is:

```text
queued → parsing → chunking → embedding → ready
                                      ↘ failed / OCR_REQUIRED / PARTIALLY_EXTRACTED
```

When `REDIS_URL` is configured, the API enqueues `process_document` for ARQ. Start the durable worker with:

```bash
cd backend
source .venv/bin/activate
arq app.worker.WorkerSettings
```

Without Redis, the API uses a database-backed job and a local background task for development. This fallback is not a multi-worker recovery strategy; production deployments should use Redis/ARQ and a stale-job monitor.

## API

All routes require a verified authenticated user. Mutations require the existing HttpOnly session and CSRF header:

```text
POST   /api/v1/documents                         multipart upload
GET    /api/v1/documents                         owner-scoped cursor list
GET    /api/v1/documents/{id}
GET    /api/v1/documents/{id}/status
GET    /api/v1/documents/{id}/preview
GET    /api/v1/documents/{id}/download
PATCH  /api/v1/documents/{id}
DELETE /api/v1/documents/{id}
POST   /api/v1/documents/{id}/reprocess
POST   /api/v1/conversations/{id}/documents     attach ready documents
DELETE /api/v1/conversations/{id}/documents/{document_id}
```

Generation accepts `document_ids` in the existing request body. The server verifies that each document is attached to the owner’s conversation, retrieves only ready owner-scoped chunks, and emits `retrieval.completed` and `citations.updated` before the existing generation events. Final citations are persisted on the assistant message as document, chunk, page/row locator, snippet and relevance metadata.

Document text is untrusted evidence. It is included in a bounded context window and cannot change permissions, tools or system instructions. If no evidence supports the answer, the grounded instruction tells the model to say that the documents do not establish it. Public conversation shares do not include document text or citation snippets unless a future explicit safe-sharing policy is added.

PDF extraction uses `pypdf`; encrypted files fail and image-only pages report `OCR_REQUIRED`. OCR is not installed or claimed. DOCX paragraphs and tables are extracted with `python-docx`. CSV parsing is bounded by row and column settings and keeps row locators. The tokenizer uses `tiktoken` when its local vocabulary is available and a bounded UTF-8 fallback offline.

## Privacy and deletion

Documents are private by default. Every upload, list, preview, download, attach, retrieve, reprocess and delete query includes the authenticated owner. Delete soft-deletes the database record, cancels processing and removes the local original when possible; historical backups and third-party provider retention are governed by deployment policy. Provider embedding and generation calls only occur when a server-side `OPENAI_API_KEY` is configured.
