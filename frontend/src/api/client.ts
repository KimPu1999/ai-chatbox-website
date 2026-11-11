import axios from 'axios';

export const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

let csrfToken: string | null = null;
let platformCsrfToken: string | null = null;

export async function loadCsrfToken(): Promise<string> {
  const response = await api.get<{ token: string }>('/auth/csrf');
  csrfToken = response.data.token;
  return csrfToken;
}

export async function loadPlatformCsrfToken(): Promise<string> {
  const response = await api.get<{ token: string }>('/platform/auth/csrf');
  platformCsrfToken = response.data.token;
  return platformCsrfToken;
}

api.interceptors.request.use(async (config) => {
  if (['post', 'put', 'patch', 'delete'].includes((config.method ?? '').toLowerCase())) {
    const platformEndpoint = (config.url ?? '').startsWith('/platform/');
    const preAuthEndpoint = ['/auth/login', '/auth/register', '/auth/verify-email', '/auth/resend-verification', '/auth/forgot-password', '/auth/reset-password', '/platform/auth/login'].includes(config.url ?? '');
    if (platformEndpoint && config.url !== '/platform/auth/login') {
      if (!platformCsrfToken) await loadPlatformCsrfToken();
      if (platformCsrfToken) config.headers['X-CSRF-Token'] = platformCsrfToken;
      return config;
    }
    if (!csrfToken && !preAuthEndpoint) {
      await loadCsrfToken();
    }
    if (csrfToken) config.headers['X-CSRF-Token'] = csrfToken;
  }
  return config;
});

export function clearCsrfToken() { csrfToken = null; }
export function clearPlatformCsrfToken() { platformCsrfToken = null; }

export async function getHealth() {
  const response = await api.get<{ status: string; service: string }>('/health');
  return response.data;
}
