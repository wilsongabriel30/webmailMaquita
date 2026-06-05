import { create } from 'zustand';
import type { Folder, MessageSummary, MessageFull, ComposeData } from '../types';

type ComposeMode = 'new' | 'reply' | 'replyAll' | 'forward' | null;
type Filter = 'all' | 'unread' | 'flagged';
type ViewMode = 'messages' | 'conversations';

export interface DraftWindow {
  id: string;
  mode: ComposeMode;
  data: ComposeData;
  draftUid: number | null;
  minimized: boolean;
}

interface MailState {
  // Folders
  folders: Folder[];
  currentFolder: string;
  loadingFolders: boolean;
  // Messages
  messages: MessageSummary[];
  totalMessages: number;
  currentPage: number;
  loadingMessages: boolean;
  // Selected
  selectedMessage: MessageFull | null;
  loadingMessage: boolean;
  selectedUids: Set<number>;
  activeIndex: number; // keyboard nav
  // Search & filter
  searchQuery: string;
  debouncedSearchQuery: string;
  filter: Filter;
  filterChanging: boolean;
  // View
  viewMode: ViewMode;
  readingPane: 'right' | 'bottom' | 'off' | 'fullscreen' | 'popout';
  density: 'compact' | 'medium' | 'full';
  showMyDay: boolean;
  setShowMyDay: (v: boolean) => void;
  previewLines: 1 | 2 | 3;
  messageListWidth: number;
  setDensity: (d: 'compact' | 'medium' | 'full') => void;
  setPreviewLines: (lines: 1 | 2 | 3) => void;
  setReadingPane: (p: 'right' | 'bottom' | 'off') => void;
  setMessageListWidth: (w: number) => void;
  // Compose — multiple drafts
  composeWindows: DraftWindow[];
  // Threading
  threadMessages: MessageFull[]; // messages in current thread
  threadExpanded: Set<number>; // UIDs of expanded messages in thread
  loadingThread: boolean;
  // Compose ribbon sync (Toolbar tabs <-> ComposePanel Ribbon)
  activeEditor: any;
  composeRibbonTab: 'message' | 'insert' | 'format' | 'options';
  setActiveEditor: (editor: any) => void;
  setComposeRibbonTab: (tab: 'message' | 'insert' | 'format' | 'options') => void;
  // Actions
  setFolders: (folders: Folder[]) => void;
  setCurrentFolder: (folder: string) => void;
  setMessages: (messages: MessageSummary[], total: number, page: number) => void;
  setSelectedMessage: (msg: MessageFull | null) => void;
  setLoadingFolders: (v: boolean) => void;
  setLoadingMessages: (v: boolean) => void;
  setLoadingMessage: (v: boolean) => void;
  setSearchQuery: (q: string) => void;
  setDebouncedSearchQuery: (q: string) => void;
  setFilter: (f: Filter) => void;
  setViewMode: (m: ViewMode) => void;
  toggleSelection: (uid: number) => void;
  selectAll: () => void;
  clearSelection: () => void;
  setActiveIndex: (i: number) => void;
  setPage: (page: number) => void;
  // Compose
  openCompose: (mode: ComposeMode, data?: ComposeData) => void;
  updateComposeData: (id: string, partial: Partial<ComposeData>) => void;
  closeCompose: (id: string) => void;
  minimizeCompose: (id: string) => void;
  restoreCompose: (id: string) => void;
  updateDraftUid: (id: string, uid: number | null) => void;
  // Reset
  reset: () => void;
  // Thread
  setThreadMessages: (msgs: MessageFull[]) => void;
  toggleThreadExpand: (uid: number) => void;
  setLoadingThread: (v: boolean) => void;
  clearThread: () => void;
}

let composeCounter = 0;

export const useMailStore = create<MailState>((set, get) => ({
  folders: [],
  currentFolder: 'INBOX',
  loadingFolders: false,
  messages: [],
  totalMessages: 0,
  currentPage: 1,
  loadingMessages: false,
  selectedMessage: null,
  loadingMessage: false,
  selectedUids: new Set(),
  activeIndex: -1,
  searchQuery: '',
  debouncedSearchQuery: '',
  filter: 'all',
  filterChanging: false,
  viewMode: "messages",
  readingPane: 'right',
  density: 'compact' as const,
  showMyDay: false,
  previewLines: 1,
  messageListWidth: (typeof window !== 'undefined' && Number(localStorage.getItem('maquita_list_width'))) || 360,
  setDensity: (d: any) => set({ density: d }),
  setShowMyDay: (v) => set({ showMyDay: v }),
  setPreviewLines: (lines: any) => set({ previewLines: lines }),
  setReadingPane: (p: any) => set({ readingPane: p }),
  setMessageListWidth: (w: number) => {
    const clamped = Math.max(260, Math.min(720, Math.round(w)));
    try { localStorage.setItem('maquita_list_width', String(clamped)); } catch { /* ignore */ }
    set({ messageListWidth: clamped });
  },
  composeWindows: [],
  threadMessages: [],
  threadExpanded: new Set(),
  loadingThread: false,
  activeEditor: null,
  composeRibbonTab: 'message' as const,
  setActiveEditor: (editor: any) => set({ activeEditor: editor }),
  setComposeRibbonTab: (tab: any) => set({ composeRibbonTab: tab }),

  setFolders: (folders) => set({ folders, loadingFolders: false }),
  setCurrentFolder: (folder) => {
    if (folder === get().currentFolder) return;
    set({
      composeWindows: get().composeWindows.map(w => w.minimized ? w : { ...w, minimized: true }),
      currentFolder: folder, messages: [], selectedMessage: null,
      currentPage: 1, selectedUids: new Set(), searchQuery: '', activeIndex: -1,
      threadMessages: [],
    });
  },
  setMessages: (messages, total, page) => set({ messages, totalMessages: total, currentPage: page, loadingMessages: false, filterChanging: false }),
  setSelectedMessage: (msg) => set({ selectedMessage: msg, loadingMessage: false, composeWindows: msg ? get().composeWindows.map(w => w.minimized ? w : { ...w, minimized: true }) : get().composeWindows }),
  setLoadingFolders: (v) => set({ loadingFolders: v }),
  setLoadingMessages: (v) => set({ loadingMessages: v }),
  setLoadingMessage: (v) => set({ loadingMessage: v }),
  setSearchQuery: (q) => set({ searchQuery: q, currentPage: 1 }),
  setDebouncedSearchQuery: (q: string) => set({ debouncedSearchQuery: q }),
  setFilter: (f) => { if (f === get().filter) return; set({ filter: f, currentPage: 1, filterChanging: true }); },
  setViewMode: (m) => set({ viewMode: m }),
  toggleSelection: (uid) => {
    const s = new Set(get().selectedUids);
    if (s.has(uid)) s.delete(uid); else s.add(uid);
    set({ selectedUids: s });
  },
  selectAll: () => set({ selectedUids: new Set(get().messages.map(m => m.uid)) }),
  clearSelection: () => set({ selectedUids: new Set() }),
  setActiveIndex: (i) => set({ activeIndex: i }),
  setPage: (page) => set({ currentPage: page, loadingMessages: true }),

  // Compose — multiple windows
  openCompose: (mode, data) => {
    const id = `compose-${++composeCounter}`;
    const win: DraftWindow = {
      id,
      mode,
      data: data || { to: [], subject: '', text_body: '', html_body: '' },
      draftUid: data?.draft_uid || null,
      minimized: false,
    };
    // Minimize all existing compose windows before opening new one
    const existing = get().composeWindows.map(w => ({ ...w, minimized: true }));
    set({ composeWindows: [...existing, win] });
  },
  closeCompose: (id) => set({ composeWindows: get().composeWindows.filter(w => w.id !== id) }),
  minimizeCompose: (id) => set({
    composeWindows: get().composeWindows.map(w => w.id === id ? { ...w, minimized: true } : w),
  }),
  restoreCompose: (id) => set({
    composeWindows: get().composeWindows.map(w => w.id === id ? { ...w, minimized: false } : { ...w, minimized: true }),
  }),
  updateDraftUid: (id, uid) => set({
    composeWindows: get().composeWindows.map(w => w.id === id ? { ...w, draftUid: uid } : w),
  }),
  // Sincroniza datos editados (asunto, destinatarios) al store para que la
  // pestana minimizada muestre el titulo/asunto ACTUAL del borrador.
  updateComposeData: (id, partial) => set({
    composeWindows: get().composeWindows.map(w => w.id === id ? { ...w, data: { ...w.data, ...partial } } : w),
  }),

  // Reset all state (on account/session change)
  reset: () => set({
    folders: [],
    currentFolder: 'INBOX',
    loadingFolders: false,
    messages: [],
    totalMessages: 0,
    currentPage: 1,
    loadingMessages: false,
    selectedMessage: null,
    loadingMessage: false,
    selectedUids: new Set(),
    activeIndex: -1,
    searchQuery: '',
    debouncedSearchQuery: '',
    filter: 'all' as const,
    filterChanging: false,
    threadMessages: [],
    threadExpanded: new Set(),
    loadingThread: false,
    composeWindows: [],
  }),
  // Thread
  setThreadMessages: (msgs) => set({ threadMessages: msgs }),
  toggleThreadExpand: (uid) => {
    const s = new Set(get().threadExpanded);
    if (s.has(uid)) s.delete(uid); else s.add(uid);
    set({ threadExpanded: s });
  },
  setLoadingThread: (v) => set({ loadingThread: v }),
  clearThread: () => set({ threadMessages: [], threadExpanded: new Set(), loadingThread: false }),
}));
