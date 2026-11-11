import { create } from 'zustand';

type Theme = 'light' | 'dark';
type ChatUIState = { sidebarOpen: boolean; theme: Theme; setSidebarOpen: (open: boolean) => void; toggleSidebar: () => void; toggleTheme: () => void };
const initialTheme: Theme = localStorage.getItem('pychat-theme') === 'dark' ? 'dark' : 'light';
export const useChatUIStore = create<ChatUIState>((set) => ({
  sidebarOpen: false, theme: initialTheme,
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  toggleTheme: () => set((state) => { const theme = state.theme === 'dark' ? 'light' : 'dark'; localStorage.setItem('pychat-theme', theme); return { theme }; }),
}));
