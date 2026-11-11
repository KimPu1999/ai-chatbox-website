# RAG architecture

The application source of truth is PostgreSQL. `documents` records private file metadata, `document_processing_jobs` records durable progress, and `document_chunks` stores normalized source text, source locators, tokenizer counts, embedding model/version and a `VECTOR(1536)` embedding. `conversation_documents` is an owner-bound join table.

Retrieval first restricts by authenticated `user_id`, attached conversation and non-deleted ready document status. It then performs cosine distance against the HNSW `vector_cosine_ops` index and caps candidates using `DOCUMENT_RETRIEVAL_TOP_K`. The selected chunks become evidence context and citations are generated from the database rows, never from model-generated source names.

Grounded generation reuses the Phase 5 Responses API SSE lifecycle. The server emits:

```text
retrieval.completed  {run_id, document_count, chunk_count}
citations.updated    {run_id, message_id, citations[]}
message.delta        {run_id, message_id, delta, sequence}
message.completed    {run_id, message_id, content}
usage.updated        {run_id, usage}
run.completed        {run_id, message_id}
```

The model receives a trusted server instruction and evidence labeled as untrusted document content. Prompt injection inside a document cannot authorize access, expose secrets or create tools. The React renderer sanitizes model output and source cards link only to authenticated owner document previews.

Redis/ARQ is the intended multi-worker processing path. The local fallback is useful for development but does not claim crash recovery, cross-worker cancellation or production malware scanning. `DOCUMENT_MALWARE_SCAN_REQUIRED=true` is a deployment gate for a scanner integration; this repository does not claim an installed scanner.
