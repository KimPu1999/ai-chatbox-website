import { api, loadCsrfToken } from '../../api/client';
import type { DocumentPage, DocumentPreview, DocumentRecord, DocumentStatusRecord } from './types';

export async function listDocuments(search = '') { return (await api.get<DocumentPage>('/documents', { params: { limit: 100, search: search || undefined } })).data; }
export async function getDocumentStatus(id: string) { return (await api.get<DocumentStatusRecord>(`/documents/${id}/status`)).data; }
export async function getDocumentPreview(id: string) { return (await api.get<DocumentPreview>(`/documents/${id}/preview`)).data; }
export async function uploadDocument(file: File, onProgress?: (value: number) => void) { const csrf = await loadCsrfToken(); const form = new FormData(); form.append('file', file); return (await api.post<DocumentRecord>('/documents', form, { headers: { 'Content-Type': 'multipart/form-data', 'X-CSRF-Token': csrf }, onUploadProgress: event => { if (event.total) onProgress?.(Math.round((event.loaded / event.total) * 100)); } })).data; }
export async function deleteDocument(id: string) { await api.delete(`/documents/${id}`); }
export async function reprocessDocument(id: string) { return (await api.post<DocumentStatusRecord>(`/documents/${id}/reprocess`)).data; }
export async function attachDocuments(conversationId: string, documentIds: string[]) { return (await api.post(`/conversations/${conversationId}/documents`, { document_ids: documentIds })).data; }
export async function detachDocument(conversationId: string, documentId: string) { await api.delete(`/conversations/${conversationId}/documents/${documentId}`); }
