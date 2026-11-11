export type Conversation = {
  id: string; user_id: string; title: string; created_at: string; updated_at: string;
  archived_at: string | null; is_pinned: boolean;
};
export type Message = { id: string; conversation_id: string; user_id: string; role: 'user' | 'assistant' | 'system' | 'tool'; content: string; created_at: string };
export type ModelOption = { id: string; name: string; description: string; available: boolean };
export type ConversationUpdate = { title?: string; is_pinned?: boolean; archived?: boolean };
