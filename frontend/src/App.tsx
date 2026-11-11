import { useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Bot, Check, ChevronDown, Menu, MessageSquare, Moon, Plus, Send, Settings, Sparkles, Sun } from 'lucide-react';
import { getHealth } from './api/client';
import { AuthProvider } from './auth/AuthProvider';
import { AdminRoute, ProtectedRoute } from './auth/guards';
import { ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage, VerifyEmailPage } from './auth/pages';
import { AccountSecurityPage, AdminUsersPage } from './auth/secure-pages';

const chats = ['Welcome to PyChat', 'Project planning', 'Ideas for the weekend', 'Learn TypeScript'];

function ChatWorkspace() {
  const [dark, setDark] = useState(false);
  const [active, setActive] = useState(chats[0]);
  const [draft, setDraft] = useState('');
  const [apiStatus, setApiStatus] = useState<'loading' | 'connected' | 'offline'>('loading');
  useEffect(() => { getHealth().then(() => setApiStatus('connected')).catch(() => setApiStatus('offline')); }, []);

  return <div className={dark ? 'dark' : ''}>
    <div className="min-h-screen bg-[#f7f7f5] text-slate-900 transition-colors dark:bg-[#171717] dark:text-slate-100">
      <aside className="fixed inset-y-0 left-0 hidden w-[272px] flex-col border-r border-slate-200 bg-white px-4 py-5 dark:border-white/10 dark:bg-[#202020] md:flex">
        <div className="flex items-center gap-3 px-2"><div className="grid h-9 w-9 place-items-center rounded-xl bg-slate-900 text-white dark:bg-white dark:text-slate-900"><Sparkles size={18} /></div><span className="font-semibold tracking-tight">PyChat AI</span></div>
        <button className="mt-8 flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-white dark:text-slate-900"><Plus size={17} /> New chat <span className="ml-auto text-xs opacity-60">⌘ K</span></button>
        <div className="mt-8 flex-1"><p className="mb-3 px-2 text-[11px] font-semibold uppercase tracking-[.16em] text-slate-400">Recent chats</p>{chats.map(chat => <button key={chat} onClick={() => setActive(chat)} className={`mb-1 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm ${active === chat ? 'bg-slate-100 font-medium dark:bg-white/10' : 'text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-white/5'}`}><MessageSquare size={16} /> <span className="truncate">{chat}</span></button>)}</div>
        <div className="border-t border-slate-100 pt-4 dark:border-white/10"><button className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-white/5"><Settings size={17} /> Settings</button><div className="mt-3 flex items-center gap-3 rounded-xl bg-slate-50 p-3 dark:bg-white/5"><div className="grid h-8 w-8 place-items-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">JD</div><div className="min-w-0"><p className="truncate text-sm font-medium">Jordan Davis</p><p className="truncate text-xs text-slate-400">Free plan</p></div><ChevronDown className="ml-auto text-slate-400" size={15} /></div></div>
      </aside>
      <main className="flex min-h-screen flex-col md:ml-[272px]">
        <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white/80 px-5 backdrop-blur dark:border-white/10 dark:bg-[#171717]/80 md:px-10"><div className="flex items-center gap-3"><button className="md:hidden"><Menu size={20} /></button><span className="text-sm font-medium">{active}</span><span className="rounded-md bg-slate-100 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:bg-white/10">GPT-4o</span></div><div className="flex items-center gap-4"><span className={`hidden items-center gap-1.5 text-xs sm:flex ${apiStatus === 'connected' ? 'text-emerald-600' : 'text-slate-400'}`}><span className={`h-1.5 w-1.5 rounded-full ${apiStatus === 'connected' ? 'bg-emerald-500' : 'bg-slate-300'}`} />{apiStatus === 'loading' ? 'Connecting' : apiStatus === 'connected' ? 'API connected' : 'API offline'}</span><button onClick={() => setDark(!dark)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-white/10" aria-label="Toggle theme">{dark ? <Sun size={18} /> : <Moon size={18} />}</button></div></header>
        <section className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-5 py-10 md:px-8"><div className="flex-1"><div className="mb-10 flex items-start gap-4"><div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-slate-900 text-white dark:bg-white dark:text-slate-900"><Bot size={18} /></div><div><p className="mb-1 text-sm font-semibold">PyChat AI</p><p className="leading-7 text-slate-600 dark:text-slate-300">Hello Jordan! I’m ready to help you think, write, plan, or learn. What would you like to work on today?</p></div></div><div className="grid gap-3 sm:grid-cols-2"><Prompt title="Plan a project" text="Help me break down a complex idea" /><Prompt title="Write something" text="Draft a clear, thoughtful message" /><Prompt title="Learn a topic" text="Explain a concept step by step" /><Prompt title="Brainstorm ideas" text="Explore creative possibilities" /></div></div><form onSubmit={e => { e.preventDefault(); setDraft(''); }} className="mt-10"><div className="relative rounded-2xl border border-slate-200 bg-white p-2 shadow-sm focus-within:border-slate-400 dark:border-white/10 dark:bg-[#202020]"><textarea value={draft} onChange={e => setDraft(e.target.value)} placeholder="Message PyChat AI..." rows={2} className="w-full resize-none bg-transparent px-3 py-2 text-sm outline-none placeholder:text-slate-400" /><div className="flex items-center justify-between px-2 pt-1"><span className="text-xs text-slate-400">PyChat can make mistakes. Check important info.</span><button type="submit" disabled={!draft.trim()} className="grid h-8 w-8 place-items-center rounded-lg bg-slate-900 text-white disabled:opacity-30 dark:bg-white dark:text-slate-900" aria-label="Send message"><Send size={15} /></button></div></div></form></section>
      </main>
    </div>
  </div>;
}

function Prompt({ title, text }: { title: string; text: string }) { return <button className="rounded-xl border border-slate-200 bg-white p-4 text-left transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-sm dark:border-white/10 dark:bg-[#202020] dark:hover:border-white/20"><p className="text-sm font-medium">{title}</p><p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{text}</p></button>; }

export default function App() {
  return <BrowserRouter><AuthProvider><Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/register" element={<RegisterPage />} />
    <Route path="/verify-email" element={<VerifyEmailPage />} />
    <Route path="/forgot-password" element={<ForgotPasswordPage />} />
    <Route path="/reset-password" element={<ResetPasswordPage />} />
    <Route element={<ProtectedRoute />}>
      <Route path="/" element={<ChatWorkspace />} />
      <Route path="/account/security" element={<AccountSecurityPage />} />
      <Route element={<AdminRoute />}><Route path="/admin/users" element={<AdminUsersPage />} /></Route>
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></AuthProvider></BrowserRouter>;
}
