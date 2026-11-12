import { useCallback, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { cancelGeneration, getGenerationStatus, streamGeneration } from '../api/chatApi';
import type { GenerationState, StreamEventPayload } from '../types/chat.types';

export function useGeneration(conversationId?: string, model?: string) {
  const client = useQueryClient(); const controller = useRef<AbortController | null>(null); const [state, setState] = useState<GenerationState>('idle'); const [content, setContent] = useState(''); const [runId, setRunId] = useState<string>(); const [error, setError] = useState<string>();
  const start = useCallback(async (prompt?: string, regenerate = false, documentIds: string[] = []) => {
    if (!conversationId || state === 'starting' || state === 'streaming') return false;
    const idempotency_key = crypto.randomUUID(); const abort = new AbortController();
    let succeeded = false; let terminal = false; let activeRunId: string | undefined;
    controller.current = abort; setState('starting'); setContent(''); setError(undefined);
    const refreshMessages = () => {
      void client.invalidateQueries({ queryKey: ['messages', conversationId] });
      void client.invalidateQueries({ queryKey: ['conversations'] });
    };
    try {
      await streamGeneration(conversationId, { content: prompt, model, idempotency_key, document_ids: documentIds }, {
        onEvent: (event: string, payload: StreamEventPayload) => {
          if (event === 'run.started') { activeRunId = payload.run_id; setRunId(payload.run_id); setState('streaming'); }
          else if (event === 'message.delta') setContent((current) => current + (payload.delta || ''));
          else if (event === 'message.completed') setContent(payload.content || '');
          else if (event === 'run.completed') { terminal = true; succeeded = true; setState('completed'); refreshMessages(); }
          else if (event === 'run.cancelled') { terminal = true; setState('cancelled'); refreshMessages(); }
          else if (event === 'run.failed') { terminal = true; setState('failed'); setError(payload.error_code === 'AI_PROVIDER_QUOTA_EXCEEDED' ? 'The AI provider account has no remaining credits.' : String(payload.error_code || 'AI generation failed')); refreshMessages(); }
        },
      }, abort.signal, regenerate);
      if (!succeeded && !terminal && activeRunId) {
        let status;
        for (let attempt = 0; attempt < 3; attempt += 1) {
          status = await getGenerationStatus(activeRunId).catch(() => undefined);
          if (status && !['queued', 'streaming'].includes(status.status)) break;
          await new Promise((resolve) => setTimeout(resolve, 250));
        }
        if (status?.status === 'completed') { succeeded = true; setState('completed'); refreshMessages(); }
        else if (status?.status === 'failed' || status?.status === 'incomplete') { setState('failed'); setError(status.error_code === 'AI_PROVIDER_QUOTA_EXCEEDED' ? 'The AI provider account has no remaining credits.' : status.error_code || 'AI generation failed'); refreshMessages(); }
        else if (status?.status === 'cancelled') setState('cancelled');
        else { setState('failed'); setError('AI stream ended before completion'); refreshMessages(); }
      } else if (!succeeded && !terminal) { setState('failed'); setError('AI stream ended before completion'); refreshMessages(); }
      return succeeded;
    } catch (reason) {
      if (abort.signal.aborted) { setState('cancelled'); return false; }
      setState('failed'); setError(reason instanceof Error ? reason.message : 'AI generation failed'); refreshMessages(); return false;
    } finally { controller.current = null; }
  }, [client, conversationId, model, state]);
  const cancel = useCallback(async () => { const id = runId; if (id) await cancelGeneration(id).catch(() => undefined); controller.current?.abort(); setState('cancelled'); }, [runId]);
  return { state, content, runId, error, start, cancel, isStreaming: state === 'starting' || state === 'streaming' };
}
