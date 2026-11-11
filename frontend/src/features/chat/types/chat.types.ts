export type Conversation = {
  id: string; user_id: string; title: string; created_at: string; updated_at: string;
  archived_at: string | null; is_pinned: boolean;
};
export type Message = { id: string; conversation_id: string; user_id: string; role: 'user' | 'assistant' | 'system' | 'tool'; content: string; created_at: string; status?: string; generation_run_id?: string | null; sequence?: number; version?: number };
export type ModelOption = { id: string; name: string; description: string; available: boolean };
export type ConversationUpdate = { title?: string; is_pinned?: boolean; archived?: boolean };
export type GenerationState = 'idle' | 'starting' | 'streaming' | 'completed' | 'cancelled' | 'failed';
export type StreamEventPayload = { run_id?: string; message_id?: string; delta?: string; content?: string; error_code?: string; model?: string; status?: string; [key: string]: unknown };
