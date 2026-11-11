import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createConversation, deleteConversation, listConversations, updateConversation } from '../api/chatApi';

export function useConversations(search: string, filter: 'active' | 'archived' | 'deleted' = 'active', folderId?: string) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['conversations', search, filter, folderId], queryFn: async () => (await listConversations(search, { filter, folderId })).items, staleTime: 20_000 });
  const invalidate = () => client.invalidateQueries({ queryKey: ['conversations'] });
  const create = useMutation({ mutationFn: createConversation, onSuccess: invalidate });
  const update = useMutation({ mutationFn: ({ id, patch }: { id: string; patch: Parameters<typeof updateConversation>[1] }) => updateConversation(id, patch), onSuccess: invalidate });
  const remove = useMutation({ mutationFn: deleteConversation, onSuccess: invalidate });
  return { ...query, create, update, remove };
}
