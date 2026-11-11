import { api, loadCsrfToken } from '../../../api/client';
import type { Conversation, ConversationUpdate, Message, ModelOption, StreamEventPayload } from '../types/chat.types';

export async function listConversations(search = '') { return (await api.get<Conversation[]>('/conversations', { params: { limit: 100, search: search || undefined } })).data; }
export async function createConversation(title = 'New conversation') { return (await api.post<Conversation>('/conversations', { title })).data; }
export async function getConversation(id: string) { return (await api.get<Conversation>(`/conversations/${id}`)).data; }
export async function updateConversation(id: string, update: ConversationUpdate) { return (await api.patch<Conversation>(`/conversations/${id}`, update)).data; }
export async function deleteConversation(id: string) { await api.delete(`/conversations/${id}`); }
export async function listMessages(id: string) { return (await api.get<Message[]>(`/conversations/${id}/messages`, { params: { limit: 100 } })).data; }
export async function createMessage(id: string, content: string) { return (await api.post<Message>(`/conversations/${id}/messages`, { content })).data; }
export async function listModels() { return (await api.get<ModelOption[]>('/models')).data; }

type StreamHandlers = { onEvent: (event: string, payload: StreamEventPayload, id?: string) => void };

export function parseSseBlock(block: string): { event: string; id?: string; payload: StreamEventPayload } | null {
  let event = 'message'; let id: string | undefined; const data: string[] = [];
  for (const line of block.split(/\r?\n/)) { if (!line || line.startsWith(':')) continue; const separator = line.indexOf(':'); const field = separator === -1 ? line : line.slice(0, separator); const value = separator === -1 ? '' : line.slice(separator + 1).replace(/^ /, ''); if (field === 'event') event = value; else if (field === 'id') id = value; else if (field === 'data') data.push(value); }
  if (!data.length) return null;
  return { event, id, payload: JSON.parse(data.join('\n')) as StreamEventPayload };
}

export async function streamGeneration(conversationId: string, body: { content?: string; model?: string; idempotency_key: string }, handlers: StreamHandlers, signal: AbortSignal, regenerate = false) {
  const csrf = await loadCsrfToken();
  const response = await fetch(`/api/v1/conversations/${conversationId}/${regenerate ? 'regenerate' : 'generate'}`, { method: 'POST', credentials: 'include', signal, headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(body) });
  if (!response.ok) { const data = await response.json().catch(() => null); const detail = data?.detail; throw new Error(typeof detail === 'string' ? detail : detail?.message || 'Generation request failed'); }
  if (!response.body) throw new Error('The server did not provide a stream');
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''; let block = '';
  const dispatch = () => { if (!block.trim()) return; try { const parsed = parseSseBlock(block); if (parsed) handlers.onEvent(parsed.event, parsed.payload, parsed.id); } catch { throw new Error('Invalid streaming event'); } block = ''; };
  const consume = (chunk: string) => { buffer += chunk; const lines = buffer.split(/\r?\n/); buffer = lines.pop() || ''; for (const line of lines) { if (!line) { dispatch(); continue; } block += `${line}\n`; } };
  while (true) { const { value, done } = await reader.read(); if (done) break; consume(decoder.decode(value, { stream: true })); }
  consume(decoder.decode()); if (buffer) consume('\n'); dispatch();
}

export async function cancelGeneration(runId: string) { return (await api.post<{ id: string; status: string }>(`/generations/${runId}/cancel`)).data; }
