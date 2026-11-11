import { api } from '../../../api/client';
import type { Conversation, ConversationUpdate, Message, ModelOption } from '../types/chat.types';

export async function listConversations(search = '') { return (await api.get<Conversation[]>('/conversations', { params: { limit: 100, search: search || undefined } })).data; }
export async function createConversation(title = 'New conversation') { return (await api.post<Conversation>('/conversations', { title })).data; }
export async function getConversation(id: string) { return (await api.get<Conversation>(`/conversations/${id}`)).data; }
export async function updateConversation(id: string, update: ConversationUpdate) { return (await api.patch<Conversation>(`/conversations/${id}`, update)).data; }
export async function deleteConversation(id: string) { await api.delete(`/conversations/${id}`); }
export async function listMessages(id: string) { return (await api.get<Message[]>(`/conversations/${id}/messages`, { params: { limit: 100 } })).data; }
export async function createMessage(id: string, content: string) { return (await api.post<Message>(`/conversations/${id}/messages`, { content })).data; }
export async function listModels() { return (await api.get<ModelOption[]>('/models')).data; }
