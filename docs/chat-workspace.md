# Phase 4 chat workspace

The chat UI is a feature module under `frontend/src/features/chat`. `ChatLayout` owns the responsive shell, `ChatSidebar` owns search and conversation actions, and `ChatWorkspace` owns messages and persistence. TanStack Query manages conversations, messages and model configuration; Zustand stores only the sidebar and theme preferences.

## API contract

All requests use the existing Axios client at `/api/v1`, credentialed session cookies, and the Phase 3 CSRF/origin checks.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/conversations?search=&limit=&offset=` | Authenticated user's active conversations |
| POST | `/conversations` | Create a conversation |
| GET/PATCH/DELETE | `/conversations/{id}` | Read, update, or soft-delete an owned conversation |
| GET | `/conversations/{id}/messages` | Read owned conversation messages |
| POST | `/conversations/{id}/messages` | Persist a user message |
| GET | `/models` | Enabled model catalog; empty when no live model is configured |

Every conversation and message query applies the authenticated user ownership predicate. The public message request accepts content only; role and assistant output remain server-controlled. Phase 4 does not call an AI provider or fabricate an assistant reply. The POST response is the persisted user message, making the Phase 5 streaming boundary explicit.

## State and responsive behavior

Routes are `/chat` and `/chat/:conversationId`. The sidebar groups conversations by update date and becomes an Escape-dismissible drawer on small screens. Messages scroll within the workspace, and new messages scroll into view only when the reader is already near the bottom. A failed send leaves the draft in the composer so it can be retried.

The theme preference is the only chat preference persisted in browser storage. Session credentials stay in HttpOnly cookies. Markdown uses `react-markdown`, `remark-gfm`, `rehype-sanitize`, safe URL filtering, and syntax highlighting without raw HTML or `dangerouslySetInnerHTML`.

## Run and test

```bash
cd backend && source .venv/bin/activate && alembic upgrade head && uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
cd frontend && npm run typecheck && npm run test && npm run build
```

The backend message route is persistence-only in this phase. Phase 5 should add an authenticated provider service and streaming transport, then extend the message state machine with server-owned assistant messages, cancellation, usage accounting, and retry semantics.
