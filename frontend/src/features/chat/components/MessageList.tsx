import { useEffect, useRef, useState } from 'react';
import { MessageBubble } from './MessageBubble';
import type { Message } from '../types/chat.types';

export function MessageList({ messages, loading, streamingContent, streaming }: { messages: Message[]; loading: boolean; streamingContent?: string; streaming?: boolean }) {
  const ref = useRef<HTMLDivElement>(null); const [nearBottom, setNearBottom] = useState(true);
  useEffect(() => { if (nearBottom) ref.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages.length, nearBottom]);
  if (loading) return <div className="flex flex-1 items-center justify-center text-sm text-slate-500" role="status">Loading messages…</div>;
  if (!messages.length) return <div className="flex flex-1 items-center justify-center text-center text-sm text-slate-500">Your saved messages will appear here.</div>;
  const displayMessages = streaming && streamingContent !== undefined ? [...messages, { id: 'streaming', conversation_id: messages[0]?.conversation_id || '', user_id: '', role: 'assistant' as const, content: streamingContent, created_at: new Date().toISOString(), status: 'streaming' }] : messages;
  return <div className="flex-1 overflow-y-auto" onScroll={(event) => { const el = event.currentTarget; setNearBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 80); }}><div className="mx-auto max-w-[820px] px-5 pb-8 md:px-8">{displayMessages.map((message) => <MessageBubble key={message.id} message={message} />)}<div ref={ref} /></div></div>;
}
