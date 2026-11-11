import { Folder, FolderOpen, Plus } from 'lucide-react';
import type { Folder as FolderType } from '../types/chat.types';

export function ConversationFolderList({ folders, selectedId, onSelect, onCreate }: { folders: FolderType[]; selectedId?: string; onSelect: (id?: string) => void; onCreate: () => void }) {
  return <section className="mt-5" aria-label="Conversation folders">
    <div className="mb-2 flex items-center justify-between px-2"><h2 className="text-[10px] font-bold uppercase tracking-[.16em] text-slate-400">Folders</h2><button onClick={onCreate} className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-blue-600 dark:hover:bg-white/10" aria-label="Create folder"><Plus size={14} /></button></div>
    <button onClick={() => onSelect(undefined)} className={`mb-1 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm ${!selectedId ? 'bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-200' : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-white/5'}`}><FolderOpen size={15} />Unfiled and all chats</button>
    {folders.map(folder => <button key={folder.id} onClick={() => onSelect(folder.id)} className={`flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm ${selectedId === folder.id ? 'bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-200' : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-white/5'}`}><Folder size={15} /> <span className="truncate">{folder.name}</span></button>)}
  </section>;
}
