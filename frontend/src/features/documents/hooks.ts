import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { deleteDocument, getDocumentStatus, listDocuments, reprocessDocument, uploadDocument } from './api';

export function useDocuments(search = '') {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['documents', search], queryFn: () => listDocuments(search), staleTime: 15_000 });
  const upload = useMutation({ mutationFn: (file: File) => uploadDocument(file), onSuccess: () => client.invalidateQueries({ queryKey: ['documents'] }) });
  const remove = useMutation({ mutationFn: deleteDocument, onSuccess: () => client.invalidateQueries({ queryKey: ['documents'] }) });
  const reprocess = useMutation({ mutationFn: reprocessDocument, onSuccess: () => client.invalidateQueries({ queryKey: ['documents'] }) });
  return { ...query, upload, remove, reprocess };
}

export function useDocumentStatus(id: string, enabled = true) {
  return useQuery({ queryKey: ['document-status', id], queryFn: () => getDocumentStatus(id), enabled, refetchInterval: result => result.state.data && ['ready', 'failed', 'ocr_required', 'partially_extracted', 'cancelled'].includes(result.state.data.status) ? false : 1500 });
}
