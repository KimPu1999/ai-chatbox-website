export type ConversationFilter = 'active' | 'archived' | 'deleted';
export function ConversationFilterTabs({ value, onChange }: { value: ConversationFilter; onChange: (value: ConversationFilter) => void }) {
  return <div className="mt-3 flex gap-1 rounded-lg bg-slate-100 p-1 dark:bg-white/5" role="tablist" aria-label="Conversation filters">
    {([['active', 'Active'], ['archived', 'Archived'], ['deleted', 'Deleted']] as const).map(([id, label]) => <button key={id} role="tab" aria-selected={value === id} onClick={() => onChange(id)} className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium ${value === id ? 'bg-white text-blue-700 shadow-sm dark:bg-white/10 dark:text-blue-200' : 'text-slate-500'}`}>{label}</button>)}
  </div>;
}
