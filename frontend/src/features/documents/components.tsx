import { useRef, useState } from 'react';
import { FileText, LoaderCircle, Upload, X } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import { getDocumentPreview } from './api';
import { useDocuments, useDocumentStatus } from './hooks';
import type { DocumentRecord } from './types';

function statusLabel(status: DocumentRecord['status']) { return status === 'ocr_required' ? 'OCR required' : status.replace('_', ' '); }

export function DocumentProcessingStatus({ document }: { document: DocumentRecord }) {
  const status = useDocumentStatus(document.id, !['ready', 'failed', 'ocr_required', 'partially_extracted'].includes(document.status));
  const current = status.data;
  return <span className="inline-flex items-center gap-1 text-xs capitalize text-slate-500" role="status">{current && !['ready', 'failed', 'ocr_required', 'partially_extracted'].includes(current.status) && <LoaderCircle size={12} className="animate-spin" />}{statusLabel(current?.status || document.status)}{current && current.progress > 0 && current.progress < 100 ? ` · ${current.progress}%` : ''}</span>;
}

export function DocumentCard({ document, selected, onToggle, onDelete }: { document: DocumentRecord; selected?: boolean; onToggle?: () => void; onDelete?: () => void }) {
  return <article className={`rounded-2xl border p-4 ${selected ? 'border-blue-500 bg-blue-50/60 dark:bg-blue-950/30' : 'border-slate-200 bg-white dark:border-white/10 dark:bg-white/[.03]'}`}><div className="flex items-start gap-3"><FileText className="mt-0.5 text-blue-600" size={20} /><div className="min-w-0 flex-1"><h3 className="truncate font-medium">{document.original_filename}</h3><DocumentProcessingStatus document={document} /><p className="mt-1 text-xs text-slate-400">{Math.ceil(document.size_bytes / 1024)} KB{document.page_count ? ` · ${document.page_count} pages` : ''}</p></div>{onToggle && <input aria-label={`Select ${document.original_filename}`} type="checkbox" checked={Boolean(selected)} onChange={onToggle} />}{onDelete && <button type="button" className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600" onClick={onDelete} aria-label={`Delete ${document.original_filename}`}><X size={16} /></button>}</div></article>;
}

export function DocumentDropzone({ onUpload, pending }: { onUpload: (file: File) => void; pending?: boolean }) {
  const input = useRef<HTMLInputElement>(null); const [dragging, setDragging] = useState(false);
  const accept = '.pdf,.docx,.txt,.csv';
  const choose = (files: FileList | null) => { const file = files?.[0]; if (file) onUpload(file); };
  return <div className={`rounded-2xl border-2 border-dashed p-8 text-center transition ${dragging ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30' : 'border-slate-200 dark:border-white/10'}`} onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); choose(event.dataTransfer.files); }}><Upload className="mx-auto mb-3 text-blue-600" /><p className="font-medium">Drop a document here</p><p className="mt-1 text-sm text-slate-500">PDF, DOCX, TXT or CSV · private to your account</p><input ref={input} className="sr-only" type="file" accept={accept} onChange={event => choose(event.target.files)} /><button type="button" className="mt-4 rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50" onClick={() => input.current?.click()} disabled={pending}>{pending ? 'Uploading…' : 'Choose file'}</button></div>;
}

export function DocumentSelector({ selected, onChange }: { selected: string[]; onChange: (ids: string[]) => void }) {
  const documents = useDocuments();
  const ready = documents.data?.items.filter(item => item.status === 'ready' || item.status === 'partially_extracted') || [];
  return <details className="mx-auto mb-2 w-full max-w-[820px] px-4"><summary className="cursor-pointer text-xs font-medium text-slate-500">Documents {selected.length ? `(${selected.length} attached)` : ''}</summary><div className="mt-2 grid gap-2 sm:grid-cols-2">{ready.length ? ready.map(document => <label key={document.id} className="flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200 p-2 text-xs dark:border-white/10"><input type="checkbox" checked={selected.includes(document.id)} onChange={() => onChange(selected.includes(document.id) ? selected.filter(id => id !== document.id) : [...selected, document.id])} /> <span className="truncate">{document.original_filename}</span></label>) : <span className="text-xs text-slate-400">Upload a ready document from the Documents page.</span>}</div></details>;
}

export function DocumentSourceCard({ documentId, documentName, pageNumber, snippet }: { documentId: string; documentName: string; pageNumber?: number | null; snippet: string }) {
  const navigate = useNavigate();
  return <button type="button" className="block w-full rounded-xl border border-slate-200 p-3 text-left text-xs hover:border-blue-400 dark:border-white/10" onClick={() => navigate(`/documents/${documentId}`)}><span className="font-medium text-blue-700 dark:text-blue-300">{documentName}{pageNumber ? ` · page ${pageNumber}` : ''}</span><span className="mt-1 block line-clamp-2 text-slate-500">{snippet}</span></button>;
}

export function DocumentViewerPage() {
  const { documentId = '' } = useParams();
  const preview = useQuery({ queryKey: ['document-preview', documentId], queryFn: () => getDocumentPreview(documentId), enabled: Boolean(documentId) });
  if (preview.isLoading) return <main className="p-8 text-sm text-slate-500">Loading document…</main>;
  if (preview.isError || !preview.data) return <main className="p-8 text-sm text-red-600">This document could not be loaded.</main>;
  return <main className="min-h-screen bg-slate-50 px-4 py-8 dark:bg-[#11141a] sm:px-8"><div className="mx-auto max-w-4xl"><p className="text-sm text-blue-600">Private document</p><h1 className="mt-2 text-2xl font-semibold">{preview.data.document.original_filename}</h1><p className="mt-1 text-sm capitalize text-slate-500">{preview.data.document.status.replace('_', ' ')}</p><div className="mt-6 space-y-3">{preview.data.chunks.length ? preview.data.chunks.map(chunk => <article key={chunk.id} className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-white/10 dark:bg-white/[.03]"><p className="mb-2 text-xs font-medium text-slate-400">Chunk {chunk.chunk_index + 1}{chunk.page_number ? ` · page ${chunk.page_number}` : ''}</p><p className="whitespace-pre-wrap text-sm leading-6 text-slate-700 dark:text-slate-200">{chunk.content}</p></article>) : <p className="text-sm text-slate-500">No indexed preview is available yet.</p>}</div></div></main>;
}

export function DocumentLibraryPage() {
  const [search, setSearch] = useState(''); const documents = useDocuments(search);
  return <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900 dark:bg-[#11141a] dark:text-slate-100 sm:px-8"><div className="mx-auto max-w-5xl"><div className="mb-8 flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm font-semibold uppercase tracking-[.18em] text-blue-600">Private knowledge</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Documents</h1><p className="mt-2 text-sm text-slate-500">Upload files, wait for indexing, then attach them to a chat.</p></div><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search files" aria-label="Search documents" className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-white/10 dark:bg-white/[.04]" /></div><div className="grid gap-6 lg:grid-cols-[320px_1fr]"><DocumentUploadPanel documents={documents} /><section aria-label="Document list" className="grid content-start gap-3 sm:grid-cols-2">{documents.isLoading ? <p className="text-sm text-slate-500">Loading documents…</p> : documents.data?.items.length ? documents.data.items.map(document => <DocumentCard key={document.id} document={document} onDelete={() => { if (window.confirm(`Delete ${document.original_filename}?`)) documents.remove.mutate(document.id); }} />) : <p className="text-sm text-slate-500">No documents yet.</p>}</section></div></div></main>;
}

function DocumentUploadPanel({ documents }: { documents: ReturnType<typeof useDocuments> }) { return <DocumentDropzone pending={documents.upload.isPending} onUpload={file => documents.upload.mutate(file)} />; }
