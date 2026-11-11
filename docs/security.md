# PyChat AI security boundaries

Every private conversation, message, folder, export, bulk job, and share-management query includes the authenticated owner ID. Composite foreign keys add a database-level ownership check for conversations, messages, generations, folders, and shares.

Sessions remain opaque HttpOnly cookies. Mutating requests use the existing synchronizer CSRF token and trusted Origin checks. Public sharing is the only unauthenticated conversation access path, and it reads an immutable snapshot rather than the owner’s live conversation.

Share tokens use at least 256 bits of randomness and only their SHA-256 digests are stored. Password-protected shares use the existing Argon2 password hasher. Public share responses use `Cache-Control: no-store`, `X-Robots-Tag: noindex`, `Referrer-Policy: no-referrer`, and a restrictive CSP. Tokens are returned once during share creation and should not be placed in analytics, logs, or persistent browser storage.

Search and exports are owner-scoped. Exports omit system instructions, failed assistant output, attachments, provider IDs, session values, API keys, and internal errors. Markdown and shared viewer content use the existing safe renderer without raw HTML execution.

The local rate limiter is process-local. Configure shared Redis coordination before running multiple API workers. PostgreSQL remains the source of truth for ownership, soft deletion, share revocation, and generation state.
