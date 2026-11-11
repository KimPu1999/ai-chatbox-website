import { useState } from 'react';
import { Check, Copy, UserRound } from 'lucide-react';
import type { Message } from '../types/chat.types';
import { MarkdownRenderer } from './MarkdownRenderer';
import { DocumentSourceCard } from '../../documents/components';

export function MessageBubble({ message }: { message: Message }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => { await navigator.clipboard?.writeText(message.content); setCopied(true); window.setTimeout(() => setCopied(false), 1200); };
  const user = message.role === 'user';
  return <article className={`group flex gap-3 py-5 ${user ? 'justify-end' : ''}`} aria-label={`${user ? 'Your' : 'PyChat'} message`}><div className={`max-w-[min(100%,720px)] ${user ? 'order-first rounded-2xl rounded-br-md bg-blue-600 px-4 py-3 text-white' : 'flex-1'}`}><div className="flex items-center gap-2 text-xs opacity-70"><span className="font-semibold">{user ? 'You' : 'PyChat AI'}</span><time dateTime={message.created_at}>{new Date(message.created_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</time></div><div className={`mt-2 ${user ? '[&_*]:text-white' : ''}`}><MarkdownRenderer content={message.content} /></div>{!user && message.citations?.length ? <div className="mt-3 grid gap-2" aria-label="Document sources">{message.citations.map(citation => <DocumentSourceCard key={citation.chunk_id} documentId={citation.document_id} documentName={citation.document_name} pageNumber={citation.page_number} snippet={citation.snippet} />)}</div> : null}<button onClick={copy} className="mt-2 inline-flex items-center gap-1 rounded px-1.5 py-1 text-xs opacity-0 transition group-hover:opacity-100 hover:bg-black/10 focus-visible:opacity-100 focus-visible:outline focus-visible:outline-2" aria-label="Copy message">{copied ? <Check size={13} /> : <Copy size={13} />}{copied ? 'Copied' : 'Copy'}</button></div>{!user && <div className="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-blue-600 text-white"><UserRound size={16} /></div>}</article>;
}
