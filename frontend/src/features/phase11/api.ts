import { api, loadCsrfToken, loadPlatformCsrfToken } from '../../api/client';

export type Plan = { id: string; code: string; name: string; description: string; enabled: boolean; entitlements: Record<string, Record<string, unknown>> };
export type Usage = { plan_code: string; daily_tokens: number; daily_token_limit: number | null; generation_requests: number; document_count: number; storage_bytes: number; reset_at: string };
export type Ticket = { id: string; ticket_number: string; subject: string; priority: string; status: string; created_at: string; updated_at: string };
export type PrivacyRequest = { id: string; request_type: string; status: string; created_at: string; finished_at: string | null };
export type OperationsSummary = { active_incidents: number; open_support_tickets: number; queued_documents: number; failed_generations_24h: number; estimated_cost_24h: string | null; flags_enabled: number };
export type FeatureFlag = { id: string; key: string; enabled: boolean; admin_only: boolean; rollout_percent: number; plan_codes: string[]; user_allowlist: string[] };

export const getPlans = () => api.get<Plan[]>('/plans').then((response) => response.data);
export const getAccountPlan = () => api.get<{ plan: Plan; subscription_status: string; current_period_end: string | null; billing_enabled: boolean }>('/account/plan').then((response) => response.data);
export const getAccountUsage = () => api.get<Usage>('/account/usage').then((response) => response.data);
export const getTickets = () => api.get<Ticket[]>('/support/tickets').then((response) => response.data);
export const createTicket = async (value: { subject: string; body: string; priority: string }) => { await loadCsrfToken(); return (await api.post<Ticket>('/support/tickets', value)).data; };
export const getPrivacyRequests = () => api.get<PrivacyRequest[]>('/account/privacy').then((response) => response.data);
export const requestExport = async () => { await loadCsrfToken(); return (await api.post<PrivacyRequest>('/account/data-export', { idempotency_key: crypto.randomUUID() })).data; };
export const requestDeletion = async () => { await loadCsrfToken(); return (await api.post<PrivacyRequest>('/account/delete-request', { idempotency_key: crypto.randomUUID() })).data; };
export const getOperationsSummary = () => api.get<OperationsSummary>('/platform/operations/summary').then((response) => response.data);
export const getFeatureFlags = () => api.get<FeatureFlag[]>('/platform/operations/feature-flags').then((response) => response.data);
export const updateFeatureFlag = async (id: string, value: Partial<FeatureFlag>) => { await loadPlatformCsrfToken(); return (await api.patch<FeatureFlag>(`/platform/operations/feature-flags/${id}`, value)).data; };
export const getPlatformPlans = () => api.get<Plan[]>('/platform/operations/plans').then((response) => response.data);
