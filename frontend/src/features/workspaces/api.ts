import { api } from '../../api/client';

export type Workspace = { id: string; slug: string; name: string; status: string; role: string };
export type Member = { id: string; user_id: string; email: string; display_name: string | null; role: string; status: string; created_at: string };
export type KnowledgeBase = { id: string; organization_id: string; name: string; description: string | null; status: string; created_by: string; created_at: string; updated_at: string };

export async function getWorkspaces() { return (await api.get<Workspace[]>('/organizations')).data; }
export async function getWorkspace(id: string) { return (await api.get(`/organizations/${id}`)).data as Workspace; }
export async function getMembers(id: string) { return (await api.get<Member[]>(`/organizations/${id}/members`)).data; }
export async function getKnowledgeBases(id: string) { return (await api.get<KnowledgeBase[]>(`/organizations/${id}/knowledge-bases`)).data; }
export async function createKnowledgeBase(id: string, payload: { name: string; description?: string }) { return (await api.post<KnowledgeBase>(`/organizations/${id}/knowledge-bases`, payload)).data; }
