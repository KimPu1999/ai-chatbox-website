import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createMessage, listMessages } from '../api/chatApi';

export function useChat(conversationId?: string) {
  const client = useQueryClient();
  const messages = useQuery({ queryKey: ['messages', conversationId], queryFn: () => listMessages(conversationId!), enabled: Boolean(conversationId), staleTime: 10_000 });
  const send = useMutation({ mutationFn: (content: string) => createMessage(conversationId!, content), onSuccess: () => client.invalidateQueries({ queryKey: ['messages', conversationId] }) });
  return { ...messages, send };
}
