import { useNavigate } from 'react-router-dom';
import { createConversation } from '../api/chatApi';
import { useChat } from '../hooks/useChat';
import { MessageComposer } from './MessageComposer';
import { MessageList } from './MessageList';
import { WelcomeScreen } from './WelcomeScreen';
export function ChatWorkspace({ conversationId }: { conversationId?: string }) { const navigate = useNavigate(); const chat = useChat(conversationId); const send = async (content: string) => { if (!conversationId) return false; try { await chat.send.mutateAsync(content); return true; } catch { return false; } }; if (!conversationId) return <WelcomeScreen onPrompt={(prompt) => { void (async () => { try { const conversation = await createConversation(prompt.slice(0, 80)); navigate(`/chat/${conversation.id}`); } catch { /* surfaced by sidebar on retry */ } })(); }} />; return <><MessageList messages={chat.data || []} loading={chat.isLoading} /><div className="shrink-0 border-t border-slate-200 bg-[#f8fafc]/90 pt-4 backdrop-blur dark:border-white/10 dark:bg-[#11141a]/90"><MessageComposer pending={chat.send.isPending} error={chat.send.isError ? 'Message could not be saved.' : undefined} onSend={send} /><p className="mx-auto max-w-[820px] px-5 pb-3 text-center text-[11px] text-slate-400 md:px-8">Phase 4 stores your messages. There is no generated AI response until Phase 5.</p></div></>; }
