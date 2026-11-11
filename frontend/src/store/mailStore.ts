import { coloresValidos } from '../lib/coloresCarpetas';
import type { Editor } from '@tiptap/react';
import type { Cuenta } from '../lib/cuentas';
import { create } from 'zustand';
import { olvidarEstadoRedaccion, olvidarTodasLasRedacciones } from '../lib/estadoRedaccion';
import { olvidarRedaccion } from '../lib/redaccionesRecuperables';
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

/** Etiqueta por la que se filtra la lista desde la barra lateral (05/11/2026). */
export interface EtiquetaFiltro { id: number; name: string; color: string }

interface MailState {
  // Cuentas que la persona puede usar (la suya + delegadas)
  cuentas: Cuenta[];
  setCuentas: (c: Cuenta[]) => void;
  // Folders
  folders: Folder[];
  currentFolder: string;
  loadingFolders: boolean;
  // Messages
  messages: MessageSummary[];
  totalMessages: number;
  currentPage: number;
  loadingMessages: boolean;
  loadingMore: boolean;
  // Selected
  selectedMessage: MessageFull | null;
  loadingMessage: boolean;
  selectedUids: Set<number>;
  activeIndex: number; // keyboard nav
  // Lista visible y resaltado por UID (05/11/2026): ver components/mail/listaVisible.ts
  visibleUids: number[];
  activeUid: number | null;
  // Search & filter
  searchQuery: string;
  /** Buscar tambien dentro del texto de los mensajes. Cuesta minuto y medio en un buzon grande
   *  -hay que descifrarlos uno a uno-, asi que solo se activa si la persona lo pide. */
  buscarEnContenido: boolean;
  /** Buscar en todas las carpetas (buzón virtual Virtual.Todo) en vez de solo en la actual. */
  buscarEnTodo: boolean;
  debouncedSearchQuery: string;
  filter: Filter;
  filterChanging: boolean;
  /** Vista «Etiqueta: X» (correos de todas las carpetas con esa etiqueta); null = carpeta normal. */
  etiquetaFiltro: EtiquetaFiltro | null;
  setEtiquetaFiltro: (e: EtiquetaFiltro | null) => void;
  // View
  viewMode: ViewMode;
  readingPane: 'right' | 'bottom' | 'off' | 'fullscreen' | 'popout';
  pageSize: number;
  blockRemoteImages: boolean;
  density: 'compact' | 'medium' | 'full' | 'linea';
  /** Qué va primero en cada fila: el asunto (como siempre) o el nombre de la persona (06/11/2026). */
  ordenFila: OrdenFila;
  setOrdenFila: (o: OrdenFila) => void;
  showMyDay: boolean;
  setShowMyDay: (v: boolean) => void;
  previewLines: 1 | 2 | 3;
  messageListWidth: number;
  setDensity: (d: 'compact' | 'medium' | 'full' | 'linea') => void;
  setPreviewLines: (lines: 1 | 2 | 3) => void;
  setReadingPane: (p: 'right' | 'bottom' | 'off' | 'fullscreen' | 'popout') => void;
  setPageSize: (n: number) => void;
  setBlockRemoteImages: (v: boolean) => void;
  setMessageListWidth: (w: number) => void;
  /** Ancho del panel de carpetas en píxeles (11/11/2026). */
  anchoCarpetas: number;
  setAnchoCarpetas: (w: number) => void;
  /** Color elegido para cada carpeta (clave: nombre completo en el servidor). */
  coloresCarpetas: Record<string, string>;
  setColoresCarpetas: (c: Record<string, string>) => void;
  /** Pedir confirmación de lectura en todo lo que se envía (11/11/2026). */
  pedirLecturaSiempre: boolean;
  setPedirLecturaSiempre: (v: boolean) => void;
  // Compose — multiple drafts
  composeWindows: DraftWindow[];
  // Threading
  threadMessages: MessageFull[]; // messages in current thread
  threadExpanded: Set<number>; // UIDs of expanded messages in thread
  loadingThread: boolean;
  // Compose ribbon sync (Toolbar tabs <-> ComposePanel Ribbon)
  /** El editor del redactor activo, para que la cinta de la barra actue sobre el. Es el Editor
   *  de TipTap; se deja como unknown para no atar el store a la libreria. */
  activeEditor: Editor | null;
  composeRibbonTab: 'message' | 'insert' | 'format' | 'options';
  setActiveEditor: (editor: Editor | null) => void;
  setComposeRibbonTab: (tab: 'message' | 'insert' | 'format' | 'options') => void;
  // Actions
  setFolders: (folders: Folder[]) => void;
  setCurrentFolder: (folder: string) => void;
  setMessages: (messages: MessageSummary[], total: number, page?: number) => void;
  loadMore: () => void;
  setSelectedMessage: (msg: MessageFull | null) => void;
  setLoadingFolders: (v: boolean) => void;
  setLoadingMessages: (v: boolean) => void;
  setLoadingMessage: (v: boolean) => void;
  setSearchQuery: (q: string) => void;
  setBuscarEnContenido: (v: boolean) => void;
  setBuscarEnTodo: (v: boolean) => void;
  /** Cambia de carpeta y fija la búsqueda en un solo paso (una sola carga, sin carrera). */
  setCarpetaYBusqueda: (folder: string, q: string) => void;
  setDebouncedSearchQuery: (q: string) => void;
  setFilter: (f: Filter) => void;
  setViewMode: (m: ViewMode) => void;
  toggleSelection: (uid: number) => void;
  selectAll: () => void;
  clearSelection: () => void;
  setActiveIndex: (i: number) => void;
  setVisibleUids: (uids: number[], activeIndex: number) => void;
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

let ultimaTanda = 0;

// 05/11/2026: la densidad y las líneas de vista previa se guardan (antes se perdían al recargar).
// Sin preferencia guardada, la lista sale en «Una línea» (como Outlook): en las pantallas
// pequeñas de la mayoría de equipos caben el doble de correos.
type Densidad = 'compact' | 'medium' | 'full' | 'linea';
export type OrdenFila = 'asunto' | 'remitente';
function leerOrdenFilaGuardado(): OrdenFila {
  try { const v = localStorage.getItem('maquita_orden_fila'); if (v === 'asunto' || v === 'remitente') return v; } catch { /* ignore */ }
  return 'remitente'; // como Hotmail/Outlook: nombre arriba, asunto debajo con la hora (06/11/2026)
}
function leerDensidadGuardada(): Densidad {
  try {
    const v = localStorage.getItem('maquita_densidad');
    if (v === 'compact' || v === 'medium' || v === 'full' || v === 'linea') return v;
  } catch { /* ignore */ }
  return 'medium'; // con panel a la derecha, dos líneas (Hotmail); sin panel a la derecha la lista va en columnas sola
}
function leerPreviewLinesGuardado(): 1 | 2 | 3 {
  try { const n = Number(localStorage.getItem('maquita_preview_lines')); if (n === 1 || n === 2 || n === 3) return n; } catch { /* ignore */ }
  return 1;
}

/** Ancho normal del panel de carpetas. */
export const ANCHO_CARPETAS_NORMAL = 220;

export const useMailStore = create<MailState>((set, get) => ({
  folders: [],
  currentFolder: 'INBOX',
  loadingFolders: false,
  messages: [],
  totalMessages: 0,
  currentPage: 1,
  loadingMessages: false,
  loadingMore: false,
  selectedMessage: null,
  loadingMessage: false,
  selectedUids: new Set(),
  activeIndex: -1,
  visibleUids: [],
  activeUid: null,
  searchQuery: '',
  buscarEnContenido: false,
  // Por defecto se busca solo en la carpeta actual (misma lectura que lib/busquedaGlobal.ts).
  buscarEnTodo: (() => { try { return localStorage.getItem('maquita_buscar_en_todo') === '1'; } catch { return false; } })(),
  debouncedSearchQuery: '',
  filter: 'all',
  etiquetaFiltro: null,
  filterChanging: false,
  // La vista (mensajes o conversaciones) se recuerda entre cargas (10/11/2026).
  viewMode: (() => { try { return localStorage.getItem('maquita_vista') === 'conversations' ? 'conversations' : 'messages'; } catch { return 'messages'; } })(),
  readingPane: 'right',
  pageSize: 50,
  blockRemoteImages: false,
  density: leerDensidadGuardada(),
  ordenFila: leerOrdenFilaGuardado(),
  setOrdenFila: (o) => { try { localStorage.setItem('maquita_orden_fila', o); } catch { /* ignore */ } set({ ordenFila: o }); },
  showMyDay: false,
  previewLines: leerPreviewLinesGuardado(),
  messageListWidth: (typeof window !== 'undefined' && Number(localStorage.getItem('maquita_list_width'))) || 360,
  setDensity: (d) => { try { localStorage.setItem('maquita_densidad', d); } catch { /* ignore */ } set({ density: d }); },
  setShowMyDay: (v) => set({ showMyDay: v }),
  setPreviewLines: (lines) => { try { localStorage.setItem('maquita_preview_lines', String(lines)); } catch { /* ignore */ } set({ previewLines: lines }); },
  setReadingPane: (p) => set({ readingPane: p }),
  setPageSize: (n) => set({ pageSize: n }),
  cuentas: [],
  setCuentas: (cuentas) => set({ cuentas }),
  setBlockRemoteImages: (v) => set({ blockRemoteImages: v }),
  anchoCarpetas: (typeof window !== 'undefined' && Number(localStorage.getItem('maquita_ancho_carpetas'))) || ANCHO_CARPETAS_NORMAL,
  coloresCarpetas: (() => { try { return coloresValidos(JSON.parse(localStorage.getItem('maquita_colores_carpetas') || '{}')); } catch { return {}; } })(),
  pedirLecturaSiempre: (() => { try { return localStorage.getItem('maquita_pedir_lectura') === '1'; } catch { return false; } })(),
  setPedirLecturaSiempre: (v) => { try { localStorage.setItem('maquita_pedir_lectura', v ? '1' : '0'); } catch { /* ignore */ } set({ pedirLecturaSiempre: v }); },
  setColoresCarpetas: (c) => {
    const limpio = coloresValidos(c);
    try { localStorage.setItem('maquita_colores_carpetas', JSON.stringify(limpio)); } catch { /* ignore */ }
    set({ coloresCarpetas: limpio });
  },
  setAnchoCarpetas: (w: number) => {
    const ajustado = Math.max(180, Math.min(520, Math.round(w)));
    try { localStorage.setItem('maquita_ancho_carpetas', String(ajustado)); } catch { /* ignore */ }
    set({ anchoCarpetas: ajustado });
  },
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
  setActiveEditor: (editor) => set({ activeEditor: editor }),
  setComposeRibbonTab: (tab) => set({ composeRibbonTab: tab }),

  setFolders: (folders) => set({ folders, loadingFolders: false }),
  setCurrentFolder: (folder) => {
    // Con una etiqueta filtrando, pulsar la misma carpeta vuelve a ella (05/11/2026).
    if (folder === get().currentFolder && !get().etiquetaFiltro) return;
    set({
      etiquetaFiltro: null,
      composeWindows: get().composeWindows.map(w => w.minimized ? w : { ...w, minimized: true }),
      currentFolder: folder, messages: [], selectedMessage: null,
      currentPage: 1, selectedUids: new Set(), searchQuery: '', activeIndex: -1, activeUid: null,
      threadMessages: [],
      // Al cambiar de carpeta se quitan también la búsqueda ya aplicada y el filtro
      // «No leídos/Marcados»: si no, la carpeta nueva salía filtrada sin que se notara
      // (el buscador ya estaba vacío) y parecía que faltaban correos.
      debouncedSearchQuery: '', filter: 'all',
    });
  },
  setMessages: (messages, total) => set({ messages, totalMessages: total, loadingMessages: false, loadingMore: false, filterChanging: false }),
  setSelectedMessage: (msg) => set({ selectedMessage: msg, loadingMessage: false, composeWindows: msg ? get().composeWindows.map(w => w.minimized ? w : { ...w, minimized: true }) : get().composeWindows }),
  setLoadingFolders: (v) => set({ loadingFolders: v }),
  setLoadingMessages: (v) => set({ loadingMessages: v }),
  setLoadingMessage: (v) => set({ loadingMessage: v }),
  setSearchQuery: (q) => set({ searchQuery: q, currentPage: 1 }),
  setBuscarEnContenido: (v) => set({ buscarEnContenido: v, currentPage: 1 }),
  setBuscarEnTodo: (v) => set({ buscarEnTodo: v }),
  setCarpetaYBusqueda: (folder, q) => set({
    etiquetaFiltro: null,
    composeWindows: get().composeWindows.map(w => w.minimized ? w : { ...w, minimized: true }),
    currentFolder: folder, messages: [], selectedMessage: null,
    currentPage: 1, selectedUids: new Set(), activeIndex: -1, activeUid: null, threadMessages: [],
    searchQuery: q, debouncedSearchQuery: q,
  }),
  setDebouncedSearchQuery: (q: string) => set({ debouncedSearchQuery: q }),
  setEtiquetaFiltro: (e) => set({
    // totalMessages en 0: la franja «Etiqueta: X» no debe mostrar el total de la carpeta anterior (09/11/2026).
    etiquetaFiltro: e, messages: [], totalMessages: 0, selectedMessage: null, currentPage: 1, selectedUids: new Set(),
    activeIndex: -1, activeUid: null, threadMessages: [], searchQuery: '', debouncedSearchQuery: '', filter: 'all',
    loadingMessages: !!e,
  }),
  setFilter: (f) => { if (f === get().filter) return; set({ filter: f, currentPage: 1, filterChanging: true }); },
  setViewMode: (m) => { try { localStorage.setItem('maquita_vista', m); } catch { /* ignore */ } set({ viewMode: m }); },
  toggleSelection: (uid) => {
    const s = new Set(get().selectedUids);
    if (s.has(uid)) s.delete(uid); else s.add(uid);
    set({ selectedUids: s });
  },
  // Seleccionar todo = lo que se VE (pestaña «Otros», chinchetas), no todo el buzón cargado (05/11/2026).
  selectAll: () => { const v = get().visibleUids; set({ selectedUids: new Set(v.length ? v : get().messages.map(m => m.uid)) }); },
  clearSelection: () => set({ selectedUids: new Set() }),
  setActiveIndex: (i) => set({ activeIndex: i, activeUid: i >= 0 ? (get().visibleUids[i] ?? null) : null }),
  // Al cambiar la lista visible se concilia la selección (05/11/2026): se quitan los UIDs que ya no
  // están (tras Supr, mover, archivar o el refresco de 45 s). Antes quedaban «seleccionados» correos
  // invisibles y, como selectedUids no estaba vacío, un clic simple alternaba la selección en vez de
  // abrir el correo. La selección es por página visible: al cambiar de página se conserva solo lo visible.
  setVisibleUids: (uids, activeIndex) => {
    const sel = get().selectedUids;
    let seleccion = sel;
    if (sel.size > 0) {
      const visibles = new Set(uids);
      seleccion = new Set(Array.from(sel).filter(u => visibles.has(u)));
    }
    set({ visibleUids: uids, activeIndex, activeUid: activeIndex >= 0 ? (uids[activeIndex] ?? null) : null, selectedUids: seleccion });
  },
  setPage: (page) => set({ currentPage: page, loadingMessages: true }),
  loadMore: () => {
    const st = get();
    // Con el tamaño de página elegido (25, 50…): con 50 fijo, a 25 por página se dejaba de cargar
    // a mitad del buzón.
    const maxPages = Math.ceil(st.totalMessages / (st.pageSize || 50));
    if (st.loadingMore || st.loadingMessages) return;
    // Respiro entre tandas: sin él, al llegar al fondo se encadenaban decenas de páginas seguidas.
    const ahora = Date.now();
    if (ahora - ultimaTanda < 600) return;
    ultimaTanda = ahora;
    if (st.currentPage >= maxPages) return;        // ya se cargaron todas las tandas
    // Sin tope de tandas: cada una pide la página siguiente (ver lib/paginacionBandeja.ts).
    if (st.messages.length >= st.totalMessages) return;
    set({ currentPage: st.currentPage + 1, loadingMore: true });
  },

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
  closeCompose: (id) => {
    olvidarEstadoRedaccion(id);
    olvidarRedaccion(id);
    set({ composeWindows: get().composeWindows.filter(w => w.id !== id) });
  },
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
  reset: () => { olvidarTodasLasRedacciones(); set({
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
    visibleUids: [],
    activeUid: null,
    searchQuery: '',
    debouncedSearchQuery: '',
    filter: 'all' as const,
    filterChanging: false,
    etiquetaFiltro: null,
    threadMessages: [],
    threadExpanded: new Set(),
    loadingThread: false,
    composeWindows: [],
  }); },
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
