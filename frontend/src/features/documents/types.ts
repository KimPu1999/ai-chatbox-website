export type DocumentStatus = 'quarantined' | 'queued' | 'parsing' | 'chunking' | 'embedding' | 'ready' | 'failed' | 'cancelled' | 'ocr_required' | 'partially_extracted';
export type DocumentRecord = { id: string; original_filename: string; mime_type: string; size_bytes: number; page_count: number | null; status: DocumentStatus; error_code: string | null; created_at: string; updated_at: string; deleted_at: string | null };
export type DocumentPage = { items: DocumentRecord[]; next_cursor: string | null; has_more: boolean };
export type DocumentStatusRecord = { document_id: string; status: DocumentStatus; progress: number; error_code: string | null; attempt_count: number };
export type DocumentChunk = { id: string; chunk_index: number; content: string; page_number: number | null; source_locator: Record<string, unknown> };
export type DocumentPreview = { document: DocumentRecord; chunks: DocumentChunk[] };
