# Advanced conversation management

Phase 6 adds migration `0006_conversation_management` on top of Phase 5. It preserves existing conversations, backfills `pinned_at` from the existing `is_pinned` flag, and derives `last_message_at` from existing messages.

## API

All authenticated endpoints use the existing HttpOnly session, verified-user dependency, exact Origin checks, and CSRF token for mutations.

- `GET /api/v1/conversations?cursor=&limit=&search=&include_archived=&include_deleted=&folder_id=` returns `{items,next_cursor,has_more}`. Ordering is pinned first, then latest message/update time and UUID. The cursor is an opaque URL-safe value and must be sent back unchanged.
- `POST /api/v1/conversations/{id}/restore` restores a soft-deleted conversation.
- `GET /api/v1/conversations/search?q=&cursor=&limit=` searches authorized titles and completed message contents.
- `GET|POST /api/v1/folders`, `PATCH|DELETE /api/v1/folders/{id}`, and `POST /api/v1/folders/{id}/conversations` manage folders.
- `POST /api/v1/conversations/bulk` applies archive, unarchive, pin, unpin, move-to-folder, soft-delete, or restore atomically for up to 100 owned conversations.
- `GET /api/v1/conversations/{id}/export?format=json|markdown` downloads a privacy-filtered export.
- `POST|GET /api/v1/conversations/{id}/shares` creates or lists read-only snapshots. `DELETE /api/v1/shares/{id}` revokes a share.
- `GET /api/v1/shared/{public_token}` reads a snapshot without account access. The plaintext token is returned once at creation and only its SHA-256 digest is stored.

## Search and language behavior

PostgreSQL stores generated `tsvector` columns using the `simple` configuration and GIN indexes. `websearch_to_tsquery` handles ordinary English queries. A bounded `ILIKE` fallback supports Burmese and mixed Unicode substring searches. `simple` does not provide Burmese linguistic segmentation; it is an index-assisted fallback rather than a Burmese analyzer.

Deleted conversations, superseded messages, and messages owned by another user are excluded. Search snippets are plain text rendered through the existing safe Markdown pipeline.

## Folders and lifecycle

Folders are unique per user after Unicode case folding. The composite conversation-to-folder foreign key prevents a folder from another user being assigned. Deleting a folder unlinks its conversations into the unfiled view. Archive hides a conversation from the active list; delete is a reversible soft delete and restore clears `deleted_at`.

Small bulk batches are all-or-nothing and create a completed `conversation_bulk_jobs` record. The table is ready for a durable worker for larger jobs; the current API caps requests at 100 to avoid pretending an in-process background task is durable.

## Exports and sharing

Exports contain schema version, title, timestamps, message roles, message text, and message versions. They exclude system messages, failed/partial messages, attachments, provider metadata, tokens, and secrets.

Shares capture an immutable snapshot at creation. They can expire, be revoked, and optionally use an Argon2 password. Public access is read-only, has `no-store`, `noindex`, restrictive CSP, and no account or conversation mutation capability. Revocation blocks future access but cannot remove copies already made by a viewer.

## Frontend

The existing chat sidebar now supports active/archived/deleted filters and folder selection. The API data layer uses TanStack Query invalidation. `ConversationExportDialog`, `ConversationShareDialog`, `ConversationBulkToolbar`, context menus, and the public `SharedConversationViewer` are reusable building blocks for the remaining management surface. The existing Phase 5 SSE generation flow remains in `ChatWorkspace`.

## Verification

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
ruff check app migrations
pytest -q

cd ../frontend
npm run typecheck
npm run test -- --run
npm run build
```
