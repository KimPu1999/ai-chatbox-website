import axios from 'axios';

export const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

let csrfToken: string | null = null;

export async function loadCsrfToken(): Promise<string> {
  const response = await api.get<{ token: string }>('/auth/csrf');
  csrfToken = response.data.token;
  return csrfToken;
}

api.interceptors.request.use(async (config) => {
  if (['post', 'put', 'patch', 'delete'].includes((config.method ?? '').toLowerCase())) {
    const preAuthEndpoint = ['/auth/login', '/auth/register', '/auth/verify-email', '/auth/resend-verification', '/auth/forgot-password', '/auth/reset-password'].includes(config.url ?? '');
    if (!csrfToken && !preAuthEndpoint) {
      await loadCsrfToken();
    }
    if (csrfToken) config.headers['X-CSRF-Token'] = csrfToken;
  }
  return config;
});

export function clearCsrfToken() { csrfToken = null; }

export async function getHealth() {
  const response = await api.get<{ status: string; service: string }>('/health');
  return response.data;
}
