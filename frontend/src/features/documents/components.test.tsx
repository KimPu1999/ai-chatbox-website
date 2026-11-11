import { fireEvent, render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { DocumentCard, DocumentDropzone } from './components';
import type { DocumentRecord } from './types';

const documentRecord: DocumentRecord = {
  id: 'doc-1', original_filename: 'guide.pdf', mime_type: 'application/pdf', size_bytes: 2048,
  page_count: 3, status: 'ready', error_code: null, created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z', deleted_at: null,
};

describe('document workspace primitives', () => {
  it('accepts keyboard file selection and reports the selected file', () => {
    const onUpload = vi.fn();
    const view = render(<DocumentDropzone onUpload={onUpload} />);
    const file = new File(['hello'], 'notes.txt', { type: 'text/plain' });
    fireEvent.change(view.container.querySelector('input[type="file"]')!, { target: { files: [file] } });
    expect(onUpload).toHaveBeenCalledWith(file);
  });

  it('renders ready state and accessible selection control', () => {
    const onToggle = vi.fn();
    const view = render(<QueryClientProvider client={new QueryClient()}><DocumentCard document={documentRecord} selected onToggle={onToggle} /></QueryClientProvider>);
    expect(view.getByText('guide.pdf')).toBeDefined();
    fireEvent.click(view.getByRole('checkbox'));
    expect(onToggle).toHaveBeenCalledOnce();
  });
});
