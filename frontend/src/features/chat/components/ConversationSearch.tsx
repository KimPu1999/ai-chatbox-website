import { Search } from 'lucide-react';
export function ConversationSearch({ value, onChange, onOpen }: { value: string; onChange: (value: string) => void; onOpen: () => void }) {
  return <label className="relative mt-5 block"><span className="sr-only">Search conversations</span><Search className="absolute left-3 top-2.5 text-slate-400" size={16} /><input value={value} onFocus={onOpen} onChange={event => onChange(event.target.value)} placeholder="Search chats" className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 dark:border-white/10 dark:bg-white/5 dark:focus:ring-blue-900" /></label>;
}
