export type Conversation = {
  id: string; user_id: string; title: string; created_at: string; updated_at: string;
  archived_at: string | null; deleted_at?: string | null; folder_id?: string | null;
  pinned_at?: string | null; last_message_at?: string | null; is_pinned: boolean;
};
export type ConversationPage = { items: Conversation[]; next_cursor: string | null; has_more: boolean };
export type Folder = { id: string; user_id: string; name: string; normalized_name: string; sort_order: number; created_at: string; updated_at: string };
export type SearchResult = { conversation_id: string; message_id: string | null; title: string; snippet: string; role: string | null; created_at: string; rank: number };
export type SearchPage = { items: SearchResult[]; next_cursor: string | null; has_more: boolean };
export type Share = { id: string; conversation_id: string; expires_at: string | null; revoked_at: string | null; created_at: string; last_accessed_at: string | null; password_protected: boolean };
export type ShareCreated = Share & { public_token: string };
export type SharedConversation = { schema_version: string; title: string; created_at: string; messages: Array<{ id: string; role: string; content: string; created_at: string; version: number }> };
export type Message = { id: string; conversation_id: string; user_id: string; role: 'user' | 'assistant' | 'system' | 'tool'; content: string; created_at: string; status?: string; generation_run_id?: string | null; sequence?: number; version?: number; citations?: Citation[] | null };
export type Citation = { document_id: string; document_name: string; chunk_id: string; page_number?: number | null; source_locator: Record<string, unknown>; snippet: string; relevance?: number };
export type ModelOption = { id: string; name: string; description: string; available: boolean };
export type ConversationUpdate = { title?: string; is_pinned?: boolean; archived?: boolean; folder_id?: string | null };
export type GenerationState = 'idle' | 'starting' | 'streaming' | 'completed' | 'cancelled' | 'failed';
export type StreamEventPayload = { run_id?: string; message_id?: string; delta?: string; content?: string; error_code?: string; model?: string; status?: string; citations?: Citation[]; [key: string]: unknown };
