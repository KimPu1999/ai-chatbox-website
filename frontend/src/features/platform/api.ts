import { api, clearPlatformCsrfToken, loadPlatformCsrfToken } from '../../api/client';
import type { ModelUsage, Overview, PlatformMe, PlatformModel, PlatformSettings, Quota, UsageSummary, UsageTrend, UserPage } from './types';

export async function platformLogin(email: string, password: string) { const csrf = (await api.get<{ token: string }>('/platform/auth/preflight')).data.token; return (await api.post<{ mfa_required: boolean; mfa_enrollment_required: boolean; message: string }>('/platform/auth/login', { email, password }, { headers: { 'X-CSRF-Token': csrf } })).data; }
export async function platformMe() { return (await api.get<PlatformMe>('/platform/auth/me')).data; }
export async function verifyPlatformMfa(code: string) { await loadPlatformCsrfToken(); return (await api.post<PlatformMe>('/platform/auth/mfa/verify', { code })).data; }
export async function enrollPlatformMfa() { await loadPlatformCsrfToken(); return (await api.post<{ secret: string; provisioning_uri: string; recovery_codes: string[] }>('/platform/auth/mfa/enroll')).data; }
export async function platformLogout() { await loadPlatformCsrfToken(); await api.post('/platform/auth/logout'); clearPlatformCsrfToken(); }
export async function getOverview(range = '30d') { return (await api.get<Overview>('/platform/overview', { params: { range } })).data; }
export async function listPlatformUsers(params: { q?: string; role?: string; account_status?: string; page?: number }) { return (await api.get<UserPage>('/platform/users', { params: { page_size: 10, ...params } })).data; }
export async function updateUserStatus(id: string, account_status: string) { await loadPlatformCsrfToken(); return (await api.patch(`/platform/users/${id}/status`, { account_status })).data; }
export async function updateUserRole(id: string, role: string) { await loadPlatformCsrfToken(); return (await api.patch(`/platform/users/${id}/role`, { role })).data; }
export async function revokeUserSessions(id: string) { await loadPlatformCsrfToken(); return (await api.post(`/platform/users/${id}/revoke-sessions`)).data; }
export async function getUsageSummary(range = '30d') { return (await api.get<UsageSummary>('/platform/usage/summary', { params: { range } })).data; }
export async function getUsageTrends(range = '30d') { return (await api.get<UsageTrend[]>('/platform/usage/trends', { params: { range } })).data; }
export async function getModelUsage(range = '30d') { return (await api.get<ModelUsage[]>('/platform/usage/by-model', { params: { range } })).data; }
export async function getCosts(range = '30d') { return (await api.get<{ estimated_cost: string | number; missing_pricing_rows: number; usage_rows: number; reconciliation_available: boolean }>('/platform/costs', { params: { range } })).data; }
export async function listPlatformModels() { return (await api.get<PlatformModel[]>('/platform/models')).data; }
export async function updatePlatformModel(id: string, patch: Partial<PlatformModel>) { await loadPlatformCsrfToken(); return (await api.patch<PlatformModel>(`/platform/models/${id}`, patch)).data; }
export async function listQuotas() { return (await api.get<Quota[]>('/platform/quotas')).data; }
export async function updateQuota(id: string, patch: Partial<Quota>) { await loadPlatformCsrfToken(); return (await api.put<Quota>(`/platform/quotas/${id}`, patch)).data; }
export async function getStorage() { return (await api.get('/platform/storage')).data; }
export async function getAuditLogs() { return (await api.get('/platform/audit-logs', { params: { page_size: 50 } })).data; }
export async function getPlatformHealth() { return (await api.get('/platform/health')).data; }
export async function getPlatformSettings() { return (await api.get<PlatformSettings>('/platform/settings')).data; }
export async function updatePlatformSettings(patch: Partial<PlatformSettings>) { await loadPlatformCsrfToken(); return (await api.patch<PlatformSettings>('/platform/settings', patch)).data; }
