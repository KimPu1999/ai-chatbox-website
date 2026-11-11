import { render, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import App from './App';

vi.mock('./api/client', () => ({
  api: { get: vi.fn().mockRejectedValue({ response: { status: 401 } }) },
  getHealth: vi.fn().mockResolvedValue({ status: 'ok', service: 'test' }),
  loadCsrfToken: vi.fn(),
  clearCsrfToken: vi.fn(),
}));

describe('App', () => { it('renders the auth entry screen when signed out', async () => { const view = render(<App />); await waitFor(() => expect(view.getByText(/PyChat AI/)).toBeDefined()); }); });
