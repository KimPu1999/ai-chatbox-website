import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

export function SyntaxCodeBlock({ code, language }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => { await navigator.clipboard?.writeText(code); setCopied(true); window.setTimeout(() => setCopied(false), 1200); };
  return <div className="group relative my-3 overflow-hidden rounded-xl border border-slate-700 bg-[#151923] text-sm"><div className="flex items-center justify-between border-b border-white/10 px-3 py-2 text-xs text-slate-400"><span>{language || 'code'}</span><button onClick={copy} className="inline-flex items-center gap-1 rounded px-2 py-1 hover:bg-white/10 focus-visible:outline focus-visible:outline-2" aria-label="Copy code">{copied ? <Check size={13} /> : <Copy size={13} />}{copied ? 'Copied' : 'Copy'}</button></div><div className="overflow-x-auto"><SyntaxHighlighter language={language || 'text'} style={oneDark} customStyle={{ margin: 0, padding: '1rem', background: 'transparent', minWidth: 'max-content' }} wrapLongLines={false}>{code}</SyntaxHighlighter></div></div>;
}
