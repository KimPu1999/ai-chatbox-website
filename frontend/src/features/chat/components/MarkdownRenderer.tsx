import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { SyntaxCodeBlock } from './SyntaxCodeBlock';

const safeUrl = (url: string) => /^(https?:|mailto:|\/|#)/i.test(url) ? url : '';
export function MarkdownRenderer({ content }: { content: string }) {
  return <div className="prose prose-slate max-w-none break-words dark:prose-invert prose-headings:font-semibold prose-a:text-blue-600 dark:prose-a:text-blue-400"><ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]} urlTransform={safeUrl} components={{ code({ className, children, ...props }) { const match = /language-(\w+)/.exec(className || ''); const text = String(children).replace(/\n$/, ''); return match ? <SyntaxCodeBlock code={text} language={match[1]} /> : <code className="rounded bg-slate-200 px-1 py-0.5 text-[.9em] dark:bg-white/10" {...props}>{children}</code>; }, a({ href, children }) { return <a href={safeUrl(href || '')} target="_blank" rel="noreferrer">{children}</a>; } }}>{content}</ReactMarkdown></div>;
}
