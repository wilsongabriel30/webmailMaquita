import { loadOfflineMessagesBuscando } from "../../hooks/useOfflineSync";
import React, { useEffect, useCallback, useRef, useState, useMemo, memo } from 'react';
import { useMailStore } from '../../store/mailStore';
import { fechaMostrada, fechaParaOrdenar } from '../../lib/fechaCorreo';
import { getPinnedSet, isPinned, pinKey, togglePins } from '../../lib/pins';
import { parametrosDeCarga, fusionarTanda } from '../../lib/paginacionBandeja';
import { recordarLeido, olvidarLeido, conservarLeidosRecientes } from './graciaNoLeidos';
import { usePolling } from '../../hooks/usePolling';
import { debeSondearLista } from '../../lib/sondeoLista';
import { api } from '../../api/client';
import { fechaCortaLista } from '../../lib/fechaLegible';
import { ContextMenu, type MenuItem } from '../common/ContextMenu';
import { abrirModalRegla } from '../../lib/reglas/abrirModalRegla';
import { reglaDesdeCorreo } from '../../lib/reglas/reglaDesdeCorreo';
import { ArbolMoverCarpetas } from './ArbolMoverCarpetas';
import { accionDeshacer, loteDeRespuesta, recordarParaDeshacer, type LoteMovido, type RespuestaMover } from '../../lib/deshacerMover';
import { showToast } from '../common/Toast';
import { accionEnLote } from '../../lib/accionesLote';
import { eliminarSeleccion, hayEliminacionDefinitiva } from '../../lib/eliminarSeleccion';
import type { MessagesResponse, MessageFull, MessageSummary } from '../../types';
import { usePriority } from '../../hooks/usePriority';
import { getFolderDisplayName } from '../../folders';
import { cargarEtiquetasDeMensajes, claveEtiquetas } from '../../lib/etiquetasDeMensajes';   // por carpeta real (05/11/2026)
import { cargarCorreosDeEtiqueta } from '../../lib/correosPorEtiqueta';   // vista «Etiqueta: X» (05/11/2026)
import { carpetaDeUid } from '../../lib/carpetaReal';
import { useEtiquetasContextual } from '../labels/useEtiquetasContextual';
import { CabeceraEtiqueta } from '../labels/CabeceraEtiqueta';
import { SinResultados } from './SinResultados';
import { AvisoFiltroSinResultados } from './AvisoFiltroSinResultados';
import { AdelantoCarpetaActual } from './AdelantoCarpetaActual';
import { AvisoBusquedaEnCarpeta } from './AvisoBusquedaEnCarpeta';
import { abrirMensajeEnPestana, abrirMensajeEnVentana } from '../../lib/abrirEnPestana';
import { AVISO_ELIMINAR_CORREO } from '../../lib/deepLinkCorreo';
import { confirmarBorradoDefinitivo } from '../../lib/confirmarBorrado';
import { avisar } from '../../lib/avisosNavegador';   // T-53
import { getCachedMessage } from '../../lib/offlineStore';   // W-7: leer sin conexión lo ya descargado
import { permisoNotificacion, pedirPermisoNotificacion } from '../../lib/notificacionSegura';   // AM-10
import { FilaCorreoLinea } from './FilaCorreoLinea';
import { AvatarFoto } from '../common/AvatarFoto';
import { PuntoLeido } from './PuntoLeido';   // clic en el puntito = leído / no leído (07/11/2026)
import { AvisoOtrosSinLeer } from './AvisoOtrosSinLeer';   // «Otros: N sin leer» (07/11/2026)
import { ChipsAdjuntosFila } from './ChipsAdjuntosFila';   // nombres de adjuntos en la fila (07/11/2026)
import { usePublicarListaVisible } from './listaVisible';   // lista visible y resaltado por UID (05/11/2026)
import { responderDesdeLista, reenviarDesdeLista } from './citarDesdeLista';
import { ICONO_CORREO_ADJUNTO, correosDeSeleccion, reenviarComoAdjunto } from '../../lib/correosComoAdjunto';   // .eml dentro de otro correo (05/11/2026)   // menú contextual con cita (05/11/2026)
import { quienMostrar } from './quienMostrar';   // Enviados/Borradores muestran «Para» (05/11/2026)   // densidad «Una línea» (05/11/2026)
import { useResponsive } from '../../hooks/useResponsive';
import { textoAvisoCorreo, nombreRemitente } from '../../lib/textoAvisoCorreo';
import { EnviosEnCurso } from './EnviosEnCurso';   // «Enviando…» al instante (06/11/2026)   // aviso con remitente y asunto (06/11/2026)
import { pestanaDe, cargarDominiosPropios, AYUDA_PESTANAS } from '../../lib/pestanaPrioritarios';
import { useOrdenLista, ordenarCorreos } from '../../lib/ordenLista';
import { BotonFavoritoCarpeta, BotonOrdenLista } from './CabeceraFavoritoOrden';   // Prioritarios / Otros (06/11/2026)

// Agrupa acciones rápidas consecutivas (eliminar/archivar fila por fila) en UNA
// petición bulk: N clics seguidos generaban N POSTs y disparaban el rate limit (429).
// Ancho mínimo del panel de lista para la fila de UNA línea. Con el panel de lectura al lado la lista
// mide ~400 px y en una sola línea el asunto quedaba sin sitio: «la lista está por nombres de personas»
// (queja general del 06/11/2026). Por debajo se usa la fila normal, con el asunto a la vista.
const ANCHO_MINIMO_UNA_LINEA = 640;
const QUICK_BATCH_MS = 500;
const quickBatches = new Map<string, { uids: number[]; timer: ReturnType<typeof setTimeout> }>();

// Un solo aviso que va contando («Enviados a la papelera: 3») en vez de un aviso por cada correo
// borrado seguido, que apilaba avisos hasta tapar la pantalla (reporte 06/11/2026).
const CONTADOR_AVISO_MS = 20000;
const contadoresAviso = new Map<string, { n: number; desde: number; lotes: LoteMovido[] }>();
function avisoAcumulado(key: string, action: string, dest: string, n: number, lote: LoteMovido | null = null) {
  const ahora = Date.now();
  const previo = contadoresAviso.get(key);
  const sigue = !!previo && ahora - previo.desde < CONTADOR_AVISO_MS;
  const total = sigue ? previo.n + n : n;
  // Los lotes movidos se acumulan con el contador: «Deshacer» devuelve todos los del aviso (10/11/2026)
  const lotes = [...(sigue ? previo.lotes : []), ...(lote ? [lote] : [])];
  contadoresAviso.set(key, { n: total, desde: sigue ? previo.desde : ahora, lotes });
  const destino = getFolderDisplayName(dest);
  const texto =
    action === 'move' ? (total > 1 ? `Enviados a ${destino}: ${total}` : `Movido a ${destino}`)
      : action === 'delete' ? (total > 1 ? `Eliminados: ${total}` : 'Eliminado')
      : action === 'archive' ? (total > 1 ? `Archivados: ${total}` : 'Archivado')
      : 'Hecho';
  const idAviso = showToast(texto, accionDeshacer(lotes), { clave: `rapida:${key}` });
  recordarParaDeshacer(lotes, idAviso);
}

function flushQuickAction(key: string, folder: string, action: string, dest: string) {
  const batch = quickBatches.get(key);
  if (!batch) return;
  quickBatches.delete(key);
  const uids = batch.uids;
  api.post<RespuestaMover>(`/mail/bulk-action/${encodeURIComponent(folder)}`, { uids, action, dest_folder: dest })
    .then((r) => {
      avisoAcumulado(key, action, dest, uids.length, loteDeRespuesta(folder, action === 'archive' ? 'Archive' : dest, r));
      const sel = useMailStore.getState().selectedMessage;
      if (sel && uids.includes(sel.uid)) {
        useMailStore.getState().setSelectedMessage(null);
      }
      window.dispatchEvent(new CustomEvent('refresh-messages'));
    })
    .catch(() => {
      // Fallo del servidor: re-sincroniza para restaurar lo que se quito optimistamente
      showToast('No se pudo completar la accion, reintenta');
      window.dispatchEvent(new CustomEvent('refresh-messages'));
    });
}

function enqueueQuickAction(folder: string, uid: number, action: string, dest = '') {
  const key = `${folder}|${action}|${dest}`;
  const existing = quickBatches.get(key);
  if (existing) {
    if (!existing.uids.includes(uid)) existing.uids.push(uid);
    clearTimeout(existing.timer);
    existing.timer = setTimeout(() => flushQuickAction(key, folder, action, dest), QUICK_BATCH_MS);
  } else {
    quickBatches.set(key, {
      uids: [uid],
      timer: setTimeout(() => flushQuickAction(key, folder, action, dest), QUICK_BATCH_MS),
    });
  }
}

function fmtDate(s: string | null): string {
  if (!s) return '';
  try {
    const d = new Date(s);
    if (isNaN(d.getTime())) return '';
    return fechaCortaLista(d);
  } catch { return ''; }
}

function extractName(from: string, avatarMap?: Record<string, { name: string; initials: string }>): string {
  if (!from) return "?";
  if (avatarMap) {
    const email = extractEmail(from);
    const avatar = avatarMap[email];
    if (avatar && avatar.name) return avatar.name;
  }
  const m = from.match(/^"?([^"<]+)"?\s*</);
  return m ? m[1].trim() : from.replace(/<.*>/, '').trim() || from;
}

function extractEmail(from: string): string {
  const m = from.match(/<([^>]+)>/);
  return m ? m[1].toLowerCase() : from.trim().toLowerCase();
}

function getInitials(from: string, avatarMap?: Record<string, { name: string; initials: string }>): string {
  if (!from) return "?";
  if (avatarMap) {
    const email = extractEmail(from);
    const avatar = avatarMap[email];
    if (avatar && avatar.initials) return avatar.initials;
    if (avatar && avatar.name) {
      const parts = avatar.name.trim().split(/\s+/);
      if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
      return parts[0][0].toUpperCase();
    }
  }
  const name = extractName(from);
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return name.charAt(0).toUpperCase();
}


const palette = ['#0078d4','#107c10','#8764b8','#ca5010','#b4009e','#038387','#4f6bed','#c239b3','#da3b01','#00b7c3'];
function getColor(s: string) { let h=0; for(let i=0;i<s.length;i++) h=s.charCodeAt(i)+((h<<5)-h); return palette[Math.abs(h)%palette.length]; }

// Icons
const flagIcon = 'M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2z';
const deleteIcon = 'M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16';
// Chincheta de las acciones al pasar el ratón (07/11/2026, como Outlook).
const pinIcon = 'M14.5 3.5l6 6-2.6.9-3.7 3.7.4 4.1-1.6 1.6-3.6-3.6L4.5 21l-1.5-1.5 4.8-4.9-3.6-3.6 1.6-1.6 4.1.4 3.7-3.7z';
const archiveIcon = 'M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4';
const unreadIcon = 'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z';
const replyIcon = 'M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6';
const forwardIcon = 'M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6';
const nuevaPestanaIcon = 'M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14';
const moveIcon = 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z';
const reglaIcon = 'M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z';

/* ---- Thread grouping helper ---- */
interface ThreadGroup {
  thread_id: string;
  messages: MessageSummary[];
  latest: MessageSummary;
  count: number;
  hasUnread: boolean;
  hasFlagged: boolean;
}

function groupByThread(messages: MessageSummary[]): ThreadGroup[] {
  const map = new Map<string, MessageSummary[]>();
  for (const msg of messages) {
    const tid = msg.thread_id || `single-${msg.uid}`;
    if (!map.has(tid)) map.set(tid, []);
    map.get(tid)!.push(msg);
  }
  const groups: ThreadGroup[] = [];
  for (const [tid, msgs] of map) {
    // Sort by date descending within each thread to get latest
    msgs.sort((a, b) => {
      return fechaParaOrdenar(b) - fechaParaOrdenar(a);
    });
    groups.push({
      thread_id: tid,
      messages: msgs,
      latest: msgs[0],
      count: msgs.length,
      hasUnread: msgs.some(m => !m.seen),
      hasFlagged: msgs.some(m => m.flagged),
    });
  }
  // Sort groups: flagged first, then by latest message date
  groups.sort((a, b) => {
    if (a.hasFlagged && !b.hasFlagged) return -1;
    if (!a.hasFlagged && b.hasFlagged) return 1;
    const da = a.latest.date ? new Date(a.latest.date).getTime() : 0;
    const db = b.latest.date ? new Date(b.latest.date).getTime() : 0;
    return db - da;
  });
  return groups;
}

export function MessageList() {
  const currentFolder = useMailStore(s => s.currentFolder);
  const messages = useMailStore(s => s.messages);
  const totalMessages = useMailStore(s => s.totalMessages);
  const currentPage = useMailStore(s => s.currentPage);
  const pageSize = useMailStore(s => s.pageSize);
  const searchQuery = useMailStore(s => s.searchQuery);
  const filter = useMailStore(s => s.filter);
  const debouncedSearchQuery = useMailStore(s => s.debouncedSearchQuery);
  const buscarEnContenido = useMailStore(s => s.buscarEnContenido);
  const loadingMessages = useMailStore(s => s.loadingMessages);
  const filterChanging = useMailStore(s => s.filterChanging);
  const setMessages = useMailStore(s => s.setMessages);
  const setLoadingMessages = useMailStore(s => s.setLoadingMessages);
  const setSelectedMessage = useMailStore(s => s.setSelectedMessage);
  const setLoadingMessage = useMailStore(s => s.setLoadingMessage);
  const selectedMessage = useMailStore(s => s.selectedMessage);
  const selectedUids = useMailStore(s => s.selectedUids);
  const toggleSelection = useMailStore(s => s.toggleSelection);
  const etiquetaFiltro = useMailStore(s => s.etiquetaFiltro);
  const openCompose = useMailStore(s => s.openCompose);
  const density = useMailStore(s => s.density);
  const asuntoPrimero = useMailStore(s => s.ordenFila) !== 'remitente';
  const setOrdenFila = useMailStore(s => s.setOrdenFila);
  // Cabecera de columnas arrastrable (06/11/2026): soltar «De» sobre «Asunto» (o al revés) intercambia el orden.
  const [columnaArrastrada, setColumnaArrastrada] = useState<'de' | 'asunto' | null>(null);
  const celdaCabecera = (col: 'de' | 'asunto', texto: string, clase: string) => (
    <div
      draggable
      title="Arrastra esta columna para cambiar el orden"
      onDragStart={(e) => { e.dataTransfer.setData('text/columna', col); e.dataTransfer.effectAllowed = 'move'; setColumnaArrastrada(col); }}
      onDragEnd={() => setColumnaArrastrada(null)}
      onDragOver={(e) => { if (e.dataTransfer.types.includes('text/columna')) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; } }}
      onDrop={(e) => {
        const origen = e.dataTransfer.getData('text/columna');
        if (origen && origen !== col) { e.preventDefault(); setOrdenFila(asuntoPrimero ? 'remitente' : 'asunto'); }
        setColumnaArrastrada(null);
      }}
      className={`${clase} cursor-move rounded px-1 -mx-1 hover:bg-[#edebe9] ${columnaArrastrada && columnaArrastrada !== col ? 'outline-dashed outline-1 outline-[#0078d4]' : ''}`}
    >{texto}</div>
  );
  const { isMobile: pantallaEstrecha } = useResponsive();
  // En celular la fila de una línea no cabe: se usa la fila de siempre.
  const [anchoLista, setAnchoLista] = useState(0);
  // Sin panel de lectura a la derecha (abajo, apagado, pantalla completa o emergentes) la lista va en columnas
  // De | Asunto | Recibido, como Hotmail (06/11/2026); con panel a la derecha solo si la densidad es «Una línea».
  const panelDerecha = useMailStore(s => s.readingPane) === 'right';
  const unaLinea = (density === 'linea' || !panelDerecha) && !pantallaEstrecha && (anchoLista === 0 || anchoLista >= ANCHO_MINIMO_UNA_LINEA);
  // Panel de lectura apagado o a pantalla completa (escritorio): un clic solo resalta la fila,
  // doble clic o Enter abren el correo y las flechas recorren la lista (pedido de Gerencia, 05/11/2026).
  // Antes un clic cargaba el correo y tapaba la lista. En celular un toque sigue abriendo.
  const panelLectura = useMailStore(s => s.readingPane);
  const soloSeleccionar = (panelLectura === 'off' || panelLectura === 'fullscreen') && !pantallaEstrecha;
  const activeIndex = useMailStore(s => s.activeIndex);
  const setActiveIndex = useMailStore(s => s.setActiveIndex);
  const previewLines = useMailStore(s => s.previewLines);
  const viewMode = useMailStore(s => s.viewMode);
  const setThreadMessages = useMailStore(s => s.setThreadMessages);
  const setLoadingThread = useMailStore(s => s.setLoadingThread);
  const clearThread = useMailStore(s => s.clearThread);
  const folders = useMailStore(s => s.folders);
  const messageListWidth = useMailStore(s => s.messageListWidth);
  const loadingMore = useMailStore(s => s.loadingMore);
  // Mensajes fijados con chincheta (localStorage): se muestran al inicio.
  const [pinnedSet, setPinnedSet] = useState<Set<string>>(() => getPinnedSet());
  useEffect(() => {
    const h = () => setPinnedSet(getPinnedSet());
    window.addEventListener('pins-changed', h);
    return () => window.removeEventListener('pins-changed', h);
  }, []);
  const readingPane = useMailStore(s => s.readingPane);

  const [ctxMenu, setCtxMenu] = useState<{ x: number; y: number; msg: MessageSummary } | null>(null);
  const [activeTab, setActiveTab] = useState<'focused' | 'other'>('focused');
  // La carga falló y no hay nada que mostrar: se dice, en vez de «No hay mensajes» (que hacía
  // creer a la persona que había perdido su correo).
  const [errorCarga, setErrorCarga] = useState(false);
  const [avatarMap, setAvatarMap] = useState<Record<string, { name: string; initials: string; photo_url?: string }>>({});
  const [expandedThreads, setExpandedThreads] = useState<Set<string>>(new Set());
  const [spamScanning, setSpamScanning] = useState(false);
  const [spamResults, setSpamResults] = useState<{ uid: number; score: number; reasons: string[] }[]>([]);
  const lastClickIdx = useRef<number>(-1);
  const prevTotalRef = useRef<number>(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  // Mide el ancho real del panel de lista (cambia al mover el separador o al abrir/cerrar el panel de lectura).
  useEffect(() => {
    const el = scrollRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver((entradas) => {
      const w = Math.round(entradas[0]?.contentRect.width || 0);
      setAnchoLista((prev) => (prev === w ? prev : w));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  // Con el teclado, la fila resaltada se mantiene a la vista.
  useEffect(() => {
    if (activeIndex < 0) return;
    const el = scrollRef.current?.querySelector(`[data-idx="${activeIndex}"]`) as HTMLElement | null;
    el?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);
  const { priorityMap, fetchPriority } = usePriority();
  // Dominios de la casa para la pestaña Prioritarios; al llegar, se vuelve a pintar la lista.
  const [, setDominiosListos] = useState(false);
  useEffect(() => { cargarDominiosPropios().then(() => setDominiosListos(true)); }, []);

  // Initialize notification sound
  useEffect(() => {
    try {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;
      const audioCtx = new AudioCtx();
      const createBeep = () => {
        try {
          const osc = audioCtx.createOscillator();
          const gain = audioCtx.createGain();
          osc.connect(gain);
          gain.connect(audioCtx.destination);
          osc.frequency.value = 880;
          osc.type = 'sine';
          gain.gain.value = 0.08;
          osc.start();
          gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.3);
          osc.stop(audioCtx.currentTime + 0.3);
        } catch { /* audio not available */ }
      };
      (window as unknown as { __maquitaBeep?: () => void }).__maquitaBeep = createBeep;
      return () => { audioCtx.close(); };
    } catch {
      // AudioContext not supported
    }
  }, []);

  const fetch_ = useCallback(() => {
    if (!currentFolder) return;
    if (etiquetaFiltro) {
      // Vista «Etiqueta: X»: correos de todas las carpetas con esa etiqueta (05/11/2026).
      const st0 = useMailStore.getState();
      if (st0.messages.length === 0 && !st0.loadingMessages) setLoadingMessages(true);
      const tandaE = parametrosDeCarga(currentPage, pageSize, st0.loadingMore);
      const sigueVigente = () => useMailStore.getState().etiquetaFiltro?.id === etiquetaFiltro.id;
      cargarCorreosDeEtiqueta(etiquetaFiltro.id, tandaE.page, tandaE.per_page)
        .then((r) => {
          if (!sigueVigente()) return;
          setErrorCarga(false);
          setMessages(fusionarTanda(useMailStore.getState().messages, r.messages, tandaE), r.total, r.page);
        })
        .catch(() => {
          if (!sigueVigente()) return;
          const st = useMailStore.getState();
          st.setMessages(st.messages, st.totalMessages, st.currentPage);
          if (st.messages.length === 0) setErrorCarga(true);
        });
      return;
    }
    // Show loading skeleton on first load or when messages are empty (folder change)
    const state = useMailStore.getState();
    if (state.messages.length === 0 && !state.loadingMessages) setLoadingMessages(true);
    // Tanda siguiente (scroll) o cabecera (primera carga / refresco), ver lib/paginacionBandeja.ts
    const tanda = parametrosDeCarga(currentPage, pageSize, state.loadingMore);
    const p = new URLSearchParams({ page: String(tanda.page), per_page: String(tanda.per_page) });
    if (debouncedSearchQuery) p.set('search', debouncedSearchQuery);
    // Solo si se ha pedido: entrar en el texto de los mensajes cuesta minuto y medio.
    if (debouncedSearchQuery && buscarEnContenido) p.set('buscar_en_contenido', 'true');
    // Send filter to backend so IMAP does server-side SEARCH UNSEEN/FLAGGED
    if (filter === 'unread') p.set('is_unread', 'true');
    if (filter === 'flagged') p.set('is_flagged', 'true');
    // Respuesta tardía: si mientras llegaba la persona cambió de carpeta, de búsqueda o de filtro,
    // se descarta. Si no, se pintaban los correos de la carpeta anterior bajo el nombre de la nueva
    // (y borrar o mover desde esa lista actuaba con UIDs de otra carpeta).
    const vigente = () => {
      const st = useMailStore.getState();
      return st.currentFolder === currentFolder && st.debouncedSearchQuery === debouncedSearchQuery && st.filter === filter;
    };
    api.get<MessagesResponse>(`/mail/messages/${encodeURIComponent(currentFolder)}?${p}`)
      .then(r => {
      if (!vigente()) return;
      setErrorCarga(false);
      if (filter === 'all' && prevTotalRef.current > 0 && r.total > prevTotalRef.current && currentFolder === 'INBOX') {
        const newCount = r.total - prevTotalRef.current;
        try { (window as unknown as { __maquitaBeep?: () => void }).__maquitaBeep?.(); } catch { /* sin sonido */ }
        if (permisoNotificacion() === 'granted') {
          // MISMO texto que el aviso en tiempo real (lib/textoAvisoCorreo.ts): remitente y asunto
          // del correo sin leer más reciente (06/11/2026; antes solo «N correos nuevos»).
          const reciente = r.messages.find(x => !x.seen) ?? r.messages[0];
          const aviso = textoAvisoCorreo(newCount, nombreRemitente(reciente?.from), reciente?.subject);
          avisar(aviso.titulo, {
            cuerpo: aviso.cuerpo,
            tipo: 'correo', etiqueta: 'new-mail', respaldo: true, uid: reciente?.uid, carpeta: 'INBOX',
          });
        } else if (permisoNotificacion() !== 'denied') {
          void pedirPermisoNotificacion();
        }
        // Update tab badge with actual unseen count from INBOX folder
        const inboxFolder = useMailStore.getState().folders.find(f => f.name === 'INBOX');
        const unseenCount = inboxFolder?.unseen ?? 0;
        const base = document.title.replace(/^\(\d+\)\s*/, '');
        document.title = unseenCount > 0 ? `(${unseenCount}) ${base}` : base;
      }
      if (filter === 'all') prevTotalRef.current = r.total;
      const previos = useMailStore.getState().messages;
      let lista = fusionarTanda(previos, r.messages, tanda);
      // En «No leídos», el correo recién abierto sigue 40 s en la lista (ver graciaNoLeidos.ts).
      if (filter === 'unread') lista = conservarLeidosRecientes(previos, lista, currentFolder);
      setMessages(lista, r.total, r.page);
    }).catch(async (err) => {
      console.error(err);
      if (!vigente()) return;
      if (/429|Too Many/i.test(String(err?.message || err)) && useMailStore.getState().loadingMore) {
        // Límite de peticiones del servidor: se espera y se vuelve a pedir la misma tanda.
        // eslint-disable-next-line react-hooks/immutability -- reintento diferido: fetch_ ya existe cuando corre el callback
        setTimeout(() => fetch_(), 5000);
        return;
      }
      // Offline fallback: load from IndexedDB cache (T-35: también si el servidor no responde: 503/red)
      if (!navigator.onLine || /503|502|504|Sin conexion|Failed to fetch|NetworkError/i.test(String(err?.message || err))) {
        try {
          // T-73: con texto buscado se filtra lo descargado (y una lista vacía es un resultado).
          const cached = await loadOfflineMessagesBuscando(currentFolder, debouncedSearchQuery);
          if (cached.length > 0 || debouncedSearchQuery.trim()) {
            setMessages(cached, cached.length, 1);
            return;
          }
        } catch { /* se ignora: no es crítico */ }
      }
      useMailStore.getState().setMessages(useMailStore.getState().messages, useMailStore.getState().totalMessages, useMailStore.getState().currentPage);
      if (useMailStore.getState().messages.length === 0) setErrorCarga(true);
    });
  }, [currentFolder, currentPage, pageSize, debouncedSearchQuery, buscarEnContenido, filter, etiquetaFiltro]);

  // Limpiar selección al cambiar de carpeta
  useEffect(() => {
    useMailStore.getState().setSelectedMessage(null);
    useMailStore.getState().clearThread();
    lastClickIdx.current = -1; // el ancla del Shift+clic no vale en otra carpeta (05/11/2026)
  }, [currentFolder]);

  // Pausa tras dejar de escribir y minimo de 3 letras (salvo que haya un operador con «:»):
  // antes cada letra lanzaba una busqueda sobre todo el correo («P», «PO», «POS»...).
  useEffect(() => {
    if (!searchQuery) {
      useMailStore.getState().setDebouncedSearchQuery('');
      return;
    }
    const corta = searchQuery.trim().length < 3 && !searchQuery.includes(':');
    // Texto corto: se retira la búsqueda larga anterior; si no, al borrar «factura» hasta «fa»
    // seguían saliendo los resultados de «factura» (05/11/2026).
    if (corta) { useMailStore.getState().setDebouncedSearchQuery(''); return; }
    const timer = setTimeout(() => {
      useMailStore.getState().setDebouncedSearchQuery(searchQuery);
    }, 800);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  useEffect(() => { fetch_(); }, [fetch_]);
  useEffect(() => { const h=()=>fetch_(); window.addEventListener('refresh-messages',h); return ()=>window.removeEventListener('refresh-messages',h); }, [fetch_]);
  // Scroll infinito: cuando el centinela del final entra en vista, cargamos la
  // siguiente tanda (fetch_ recarga con per_page mayor, manteniendo el scroll).
  useEffect(() => {
    const sentinel = loadMoreRef.current;
    const root = scrollRef.current;
    if (!sentinel || !root) return;
    const obs = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) useMailStore.getState().loadMore();
    }, { root, rootMargin: '300px' });
    obs.observe(sentinel);
    return () => obs.disconnect();
  }, [messages.length, totalMessages, loadingMessages]);
  // 45 s: con 2 min el correo recien llegado tardaba en aparecer (21/09/2026).
  // Con una búsqueda activa no se repite la búsqueda en cada sondeo (10/11/2026).
  usePolling(() => {
    if (debeSondearLista(useMailStore.getState().debouncedSearchQuery)) fetch_();
  }, 45000, true);

  // Fetch priority classification for INBOX
  useEffect(() => {
    if (currentFolder === 'INBOX' && messages.length > 0 && messages.length <= pageSize) {
      fetchPriority(currentFolder);
    }
  }, [currentFolder, messages.length, fetchPriority, pageSize]);

  // Spam scan function — context-aware: si hay mensaje seleccionado escanea solo ese, si no escanea la carpeta
  const scanSpam = useCallback(async (autoMove = false) => {
    if (!currentFolder) return;
    const sel = useMailStore.getState().selectedMessage;
    // El escudo, sin texto, movía hasta 50 correos a Correo no deseado de un clic. Se pregunta.
    if (autoMove && !window.confirm(sel?.uid
      ? 'Se revisará este correo y, si parece correo no deseado, se moverá a «Correo no deseado». ¿Continuar?'
      : 'Se revisarán los últimos 50 correos de esta carpeta y los que parezcan correo no deseado se moverán a «Correo no deseado». ¿Continuar?')) return;
    setSpamScanning(true);
    try {
      let url = `/mail/spam/scan?folder=${encodeURIComponent(currentFolder)}`;
      if (sel?.uid) {
        // Escaneo individual del mensaje seleccionado
        url += `&uid=${sel.uid}&auto_move=${autoMove}`;
      } else {
        // Escaneo de toda la carpeta
        url += `&limit=50&auto_move=${autoMove}`;
      }
      const res = await api.get<{ scanned: number; spam_found: number; moved: number; details: { uid: number; score: number; reasons: string[]; is_spam?: boolean }[] }>(url);
      setSpamResults(res.details || []);
      if (sel?.uid) {
        // Resultado individual
        const det = res.details?.[0];
        if (det?.is_spam) {
          if (autoMove && res.moved > 0) {
            showToast(`Spam confirmado — movido a Spam (score: ${det.score})`);
            window.dispatchEvent(new CustomEvent("refresh-messages"));
          } else {
            showToast(`⚠ Spam detectado (score: ${det.score}): ${(det.reasons || []).join(', ')}`);
          }
        } else {
          showToast(`Este mensaje parece legítimo (score: ${det?.score || 0})`);
        }
      } else {
        if (res.spam_found > 0) {
          if (autoMove && res.moved > 0) {
            showToast(`${res.moved} correo${res.moved > 1 ? "s" : ""} de spam movido${res.moved > 1 ? "s" : ""} a Spam`);
            window.dispatchEvent(new CustomEvent("refresh-messages"));
          } else if (!autoMove) {
            showToast(`${res.spam_found} posible${res.spam_found > 1 ? "s" : ""} spam detectado${res.spam_found > 1 ? "s" : ""}`);
          }
        } else {
          showToast("No se detectó spam");
        }
      }
    } catch {
      showToast("Error al escanear spam");
    }
    setSpamScanning(false);
  }, [currentFolder]);

  // Fetch avatar data — use stable messageIds to avoid re-fetching on every render
  const messageIds = useMemo(() => messages.map(m => m.uid).join(','), [messages]);

  // Categorias/etiquetas por mensaje — INLINE (sin hook externo) para que el
  // empaquetador no pueda eliminar la definicion y romper el correo.
  type EtiquetaMsg = { id: number | string; name: string; color?: string };
  const [msgLabelsMap, setMsgLabelsMap] = useState<Record<string, EtiquetaMsg[]>>({});
  // Incremental: con el scroll infinito cada tanda añade correos; solo se piden las
  // etiquetas de los NUEVOS (pedir las de todos otra vez disparaba decenas de peticiones
  // por tanda y nginx respondía 429). Se recuerda qué UID ya se pidieron por carpeta.
  const etiquetasPedidasRef = useRef<{ carpeta: string; uids: Set<number> }>({ carpeta: '', uids: new Set() });
  useEffect(() => {
    let cancelled = false;
    const load = async (todos: boolean) => {
      if (!currentFolder) { if (!cancelled) setMsgLabelsMap({}); return; }
      // La «vista» cambia con la carpeta o con la etiqueta filtrada (05/11/2026).
      const vista = etiquetaFiltro ? `etiqueta:${etiquetaFiltro.id}` : currentFolder;
      const ref = etiquetasPedidasRef.current;
      if (ref.carpeta !== vista || todos) {
        etiquetasPedidasRef.current = { carpeta: vista, uids: new Set() };
        if (ref.carpeta !== vista && !cancelled) setMsgLabelsMap({});
      }
      const pedidos = etiquetasPedidasRef.current.uids;
      const nuevos = messages.map((m) => m.uid).filter((u) => !pedidos.has(u));
      if (nuevos.length === 0) return;
      nuevos.forEach((u) => pedidos.add(u));
      try {
        // Por tandas: con miles de correos cargados una sola URL era rechazada (503).
        // Por carpeta REAL de cada correo: en «Todo el correo» no se piden (uids virtuales).
        const nuevosSet = new Set(nuevos);
        const mapa = await cargarEtiquetasDeMensajes<EtiquetaMsg>(messages.filter((m) => nuevosSet.has(m.uid)), currentFolder);
        if (!cancelled) setMsgLabelsMap((prev) => (todos ? mapa : { ...prev, ...mapa }));
      } catch { /* sin etiquetas en esta tanda */ }
    };
    load(false);
    const handler = () => load(true);
    window.addEventListener('refresh-message-labels', handler);
    return () => { cancelled = true; window.removeEventListener('refresh-message-labels', handler); };
  }, [currentFolder, messageIds, etiquetaFiltro]);
  useEffect(() => {
    if (!messages.length) return;
    const emails = [...new Set(messages.map(m => extractEmail(m.from)))];
    const missing = emails.filter(e => !avatarMap[e]);
    if (!missing.length) return;
    const batch = missing.slice(0, 200).join(',');
    api.get<Record<string, { name: string; initials: string; photo_url?: string }>>(`/contacts/avatars?emails=${encodeURIComponent(batch)}`)
      .then(data => { setAvatarMap(prev => ({ ...prev, ...data })); })
      .catch(() => {});
  }, [messageIds]);

  const handleFlag = async (uid: number, flagged: boolean) => {
    try {
      await api.post(`/mail/flags/${encodeURIComponent(carpetaDeUid(uid, currentFolder))}/${uid}`, { flags: '\\Flagged', add: !flagged });
      const updated = useMailStore.getState().messages.map(m => m.uid === uid ? { ...m, flagged: !flagged } : m);
      useMailStore.getState().setMessages(updated, totalMessages, currentPage);
    } catch { /* se ignora: no es crítico */ }
  };

  const handleRowClick = (uid: number, idx: number, e: React.MouseEvent) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      toggleSelection(uid);
      lastClickIdx.current = idx;
      return;
    }
    if (e.shiftKey) {
      e.preventDefault();
      handleShiftClick(idx, e);
      return;
    }
    if (selectedUids.size > 0) {
      toggleSelection(uid);
      lastClickIdx.current = idx;
      setActiveIndex(idx);
      return;
    }
    // Ancla del rango (05/11/2026): un clic normal también vale como inicio para el
    // siguiente Shift+clic, como en Outlook. Antes solo lo guardaban Ctrl y la casilla.
    lastClickIdx.current = idx;
    setActiveIndex(idx);
    if (soloSeleccionar) return;   // resaltar; abre con doble clic o Enter
    handleSelect(uid);
  };

  /** Explica por que no se abrio el correo. Sin esto, el clic no producia NADA visible.
   *  Si el mensaje ya no existe (lo archivo o borro otra pantalla, o este mismo dispositivo hace
   *  un segundo), ademas se refresca la lista: dejar la fila fantasma invita a volver a pulsarla. */
  const avisarMensajeNoAbierto = (err: unknown) => {
    const texto = err instanceof Error ? err.message : String(err ?? '');
    const yaNoEsta = /404|not found|no encontrado/i.test(texto);
    if (yaNoEsta) {
      showToast('Ese correo ya no está en esta carpeta. Se actualizó la lista.');
      window.dispatchEvent(new CustomEvent('refresh-messages'));
      return;
    }
    if (/reinici/i.test(texto) || /^HTTP 50[234]$/.test(texto)) {
      showToast('El servidor se está reiniciando. Inténtalo de nuevo en unos segundos.');
      return;
    }
    // Solo cuando el cliente confirmó que el refresco fue rechazado (no por un fallo temporal).
    if (texto === 'Session expired') {
      showToast('Tu sesión caducó. Cierra sesión y vuelve a entrar.');
      return;
    }
    if (!navigator.onLine || /sin conexi[oó]n/i.test(texto)) {
      showToast('Sin conexión: este correo no está descargado. Se abrirá cuando vuelva el internet.');
      return;
    }
    showToast('No se pudo abrir el correo. Inténtalo de nuevo.');
  };

  const handleSelect = async (uid: number) => {
    // Carpeta real del correo (vista por etiqueta / Todo el correo, 05/11/2026).
    const carpeta = carpetaDeUid(uid, currentFolder);
    // If in Drafts folder, open in compose for editing
    if (carpeta === 'Drafts') {
      setLoadingMessage(true);
      try {
        const msg = await api.get<MessageFull>(`/mail/message/${encodeURIComponent(carpeta)}/${uid}`);
        setLoadingMessage(false);
        const toList = msg.to ? msg.to.split(',').map(s => s.trim()).filter(Boolean) : [];
        const ccList = msg.cc ? msg.cc.split(',').map(s => s.trim()).filter(Boolean) : [];
        openCompose('new', {
          to: toList,
          cc: ccList,
          subject: msg.subject || '',
          text_body: '',
          html_body: msg.html_body || msg.text_body || '',
          in_reply_to: msg.in_reply_to || '',
          references: msg.references || '',
          draft_uid: uid,
          adjuntos_borrador: msg.attachments || [],
        });
        return;
      } catch (err) {
        console.error('Error loading draft for edit:', err);
        setLoadingMessage(false);
        avisarMensajeNoAbierto(err);
        return;
      }
    }
    setLoadingMessage(true);
    clearThread();
    try {
      // W-7: sin red se abre la copia descargada (últimos días en IndexedDB); si la petición falla
      // por conexión, también se intenta la copia antes de avisar que no se pudo abrir.
      const desdeCache = async () => (await getCachedMessage(carpeta, uid)) as unknown as MessageFull | null;
      let msg: MessageFull;
      if (!navigator.onLine) {
        const local = await desdeCache();
        if (!local) throw new Error('Sin conexión y este correo no está descargado');
        msg = local;
      } else {
        try {
          msg = await api.get<MessageFull>(`/mail/message/${encodeURIComponent(carpeta)}/${uid}`);
        } catch (errRed) {
          const local = /404|not found|no encontrado|401|sesi/i.test(String((errRed as Error)?.message || errRed)) ? null : await desdeCache();
          if (!local) throw errRed;
          msg = local;
        }
      }
      // Modo «Solo elementos emergentes»: el correo se abre en su ventana propia (/mensaje), con todos
      // los botones (Responder, Reenviar…). Antes era una copia estática sin acciones (09/11/2026).
      if (useMailStore.getState().readingPane === 'popout') {
        abrirMensajeEnVentana(carpeta, uid);
        setLoadingMessage(false);
        return;
      }
      setSelectedMessage(msg);
      // If in conversations mode and message has a thread_id, fetch thread
      if (useMailStore.getState().viewMode === 'conversations' && msg.thread_id) {
        fetchThreadMessages(msg.thread_id, msg.uid);
      }
      const wasUnseen = useMailStore.getState().messages.some(m => m.uid === uid && !m.seen);
      const updated = useMailStore.getState().messages.map(m => m.uid === uid ? { ...m, seen: true, flags: m.flags.includes('\\Seen') ? m.flags : [...m.flags, '\\Seen'] } : m);
      useMailStore.getState().setMessages(updated, totalMessages, currentPage);
      if (wasUnseen) {
        recordarLeido(carpeta, uid);
        const flds = useMailStore.getState().folders.map(f => f.name === carpeta && f.unseen > 0 ? { ...f, unseen: f.unseen - 1 } : f);
        useMailStore.getState().setFolders(flds);
      }
    } catch (err) {
      console.error(err);
      useMailStore.getState().setLoadingMessage(false);
      avisarMensajeNoAbierto(err);
    }
  };

  const fetchThreadMessages = async (threadId: string, currentUid: number) => {
    setLoadingThread(true);
    try {
      const res = await api.get<{ messages: MessageFull[]; count: number }>(
        `/mail/threads/${encodeURIComponent(currentFolder)}/${encodeURIComponent(threadId)}`
      );
      if (res.messages && res.messages.length > 1) {
        setThreadMessages(res.messages);
        // Expand only the latest message (highest uid or latest date)
        const latestUid = currentUid;
        useMailStore.setState({ threadExpanded: new Set([latestUid]) });
      } else {
        clearThread();
      }
    } catch {
      clearThread();
    }
    setLoadingThread(false);
  };

  const handleThreadHeaderClick = (group: ThreadGroup) => {
    const newExpanded = new Set(expandedThreads);
    if (newExpanded.has(group.thread_id)) {
      newExpanded.delete(group.thread_id);
    } else {
      newExpanded.add(group.thread_id);
    }
    setExpandedThreads(newExpanded);
  };

  const handleShiftClick = (idx: number, e: React.MouseEvent) => {
    if (e.shiftKey && lastClickIdx.current >= 0) {
      const start = Math.min(lastClickIdx.current, idx);
      const end = Math.max(lastClickIdx.current, idx);
      const uidsToSelect = filtered.slice(start, end + 1).map(m => m.uid);
      const s = new Set(useMailStore.getState().selectedUids);
      uidsToSelect.forEach(u => s.add(u));
      useMailStore.setState({ selectedUids: s });
    } else {
      toggleSelection(filtered[idx].uid);
    }
    lastClickIdx.current = idx;
  };

  const quickAction = (uid: number, action: string, dest?: string) => {
    if (action === 'mark_unread') olvidarLeido(currentFolder, uid);
    // Borrar desde la Papelera es definitivo: el icono al pasar el ratón y el menú
    // contextual preguntan igual que la barra de selección.
    if (action === 'delete' && !confirmarBorradoDefinitivo()) return;
    // Si la fila forma parte de una selección (Shift/Ctrl), el icono al pasar el ratón y el menú
    // contextual actúan sobre TODOS los seleccionados, como en Outlook (06/11/2026: antes solo
    // borraba esa fila y había que ir uno por uno).
    const seleccion = useMailStore.getState().selectedUids;
    const enLote = seleccion.size > 1 && seleccion.has(uid) && (action === 'delete' || action === 'move' || action === 'archive' || action === 'mark_read' || action === 'mark_unread');
    const objetivos = enLote ? Array.from(seleccion) : [uid];
    // UI optimista: para acciones que sacan el correo de la vista actual, lo
    // quitamos de la lista de inmediato (se siente instantaneo). El servidor
    // trabaja por detras; si falla, el .catch de flushQuickAction re-sincroniza.
    if (action === 'delete' || action === 'move' || action === 'archive') {
      const st = useMailStore.getState();
      const fuera = new Set(objetivos);
      const restantes = st.messages.filter(m => !fuera.has(m.uid));
      if (restantes.length !== st.messages.length) {
        st.setMessages(restantes, Math.max(0, st.totalMessages - (st.messages.length - restantes.length)), st.currentPage);
      }
      if (st.selectedMessage && fuera.has(st.selectedMessage.uid)) {
        st.setSelectedMessage(null);
      }
    }
    for (const u of objetivos) {
      if (action === 'mark_unread' && u !== uid) olvidarLeido(currentFolder, u);
      enqueueQuickAction(carpetaDeUid(u, currentFolder), u, action, dest || '');
    }
    if (enLote) useMailStore.getState().clearSelection();
  };

  // Note: unread/flagged filtering is done server-side via IMAP SEARCH
  // Do NOT re-filter here — backend results are already correct
  // Check if there are any high-priority messages before filtering

  // Pestañas Prioritarios / Otros: regla en lib/pestanaPrioritarios.ts (06/11/2026).
  // Con «No leídos» o «Marcados» se ven TODOS los que cumplen, sean de Prioritarios o de Otros:
  // antes los de Otros salían un instante y desaparecían al llegar la clasificación (07/11/2026).
  const ordenLista = useOrdenLista(currentFolder);
  const filtered = messages.filter(m => {
    // Vista por etiqueta: «No leídos»/«Marcados» se aplican aquí (el servidor devuelve todos) y las
    // pestañas Prioritarios/Otros no intervienen (09/11/2026).
    if (etiquetaFiltro) {
      if (filter === 'unread') return !m.seen;
      if (filter === 'flagged') return m.flagged;
      return true;
    }
    if (currentFolder !== 'INBOX' || filter !== 'all') return true;
    return pestanaDe(m, priorityMap[m.uid]) === activeTab;
  });
  // La lista respeta el orden de llegada (como Outlook y Zimbra): la prioridad
  // y la bandera se muestran como marcas, no reordenan. Solo la chincheta fija arriba.

  // Orden elegido con ↑↓ (por defecto, fecha: no toca nada). La chincheta sigue mandando arriba.
  ordenarCorreos(filtered, ordenLista);
  // Los mensajes fijados con chincheta van primero (sort estable, ES2019+).
  if (pinnedSet.size > 0) {
    filtered.sort((a, b) =>
      (pinnedSet.has(pinKey(currentFolder, b.uid)) ? 1 : 0) - (pinnedSet.has(pinKey(currentFolder, a.uid)) ? 1 : 0)
    );
  }

  // Sin leer que están en «Otros» (aviso arriba de Prioritarios y número en la pestaña, 07/11/2026).
  const otrosSinLeer = currentFolder === 'INBOX'
    ? messages.filter(m => !m.seen && pestanaDe(m, priorityMap[m.uid]) === 'other')
    : [];
  // Publica en el store los UIDs visibles en su orden real y mantiene el resaltado por UID.
  usePublicarListaVisible(filtered);

  const isConversationMode = viewMode === 'conversations';
  const threadGroups = isConversationMode ? groupByThread(filtered) : null;

  const folderLabel = etiquetaFiltro ? `Etiqueta: ${etiquetaFiltro.name}` : getFolderDisplayName(currentFolder);

  // Clic derecho: marcar como no deseado / no es spam y bloquear remitente (mismos endpoints que la
  // barra del mensaje). UI optimista: se quita de la lista y el servidor trabaja por detras.
  const quitarDeLista = (uid: number) => {
    const st = useMailStore.getState();
    st.setMessages(st.messages.filter(m => m.uid !== uid), Math.max(0, st.totalMessages - 1), st.currentPage);
    if (st.selectedMessage?.uid === uid) st.setSelectedMessage(null);
  };
  const marcarNoDeseadoCtx = async (msg: MessageSummary, esNoDeseado: boolean) => {
    quitarDeLista(msg.uid);
    try {
      await api.post(esNoDeseado ? '/mail/spam/not-spam' : '/mail/spam/report', { folder: currentFolder, uid: msg.uid });
      showToast(esNoDeseado ? 'Movido a la Bandeja de entrada — no es spam' : 'Marcado como spam y movido a Correo no deseado — el filtro aprendió');
    } catch { showToast('No se pudo completar la acción'); }
    window.dispatchEvent(new CustomEvent('refresh-messages'));
  };
  const confiarRemitenteCtx = async (msg: MessageSummary) => {
    const from = msg.from || '';
    const m = from.match(/<([^>]+)>/);
    const correo = (m ? m[1] : from).trim().toLowerCase();
    if (!correo.includes('@')) { showToast('No se pudo leer el remitente'); return; }
    try {
      await api.post('/mail/remitentes-confiables', { correo });
      if (currentFolder === 'Junk' || currentFolder === 'Spam') {
        quitarDeLista(msg.uid);
        await api.post('/mail/spam/not-spam', { folder: currentFolder, uid: msg.uid }).catch(() => { });
      }
      showToast(`${correo} en confianza — sus correos iran siempre a la Bandeja`);
    } catch (e) { showToast(e instanceof Error && e.message ? e.message : 'No se pudo confiar en el remitente'); }
    window.dispatchEvent(new CustomEvent('refresh-messages'));
  };
  const bloquearRemitenteCtx = async (msg: MessageSummary) => {
    const from = msg.from || '';
    const m = from.match(/<([^>]+)>/);
    const correo = (m ? m[1] : from).trim().toLowerCase();
    if (!correo.includes('@')) { showToast('No se pudo leer el remitente'); return; }
    if (!window.confirm(`Bloquear a ${correo}?\n\nSus proximos correos iran a Correo no deseado. Puedes deshacerlo en Configuración → Remitentes bloqueados.`)) return;
    quitarDeLista(msg.uid);
    try {
      await api.post('/mail/remitentes-bloqueados', { correo });
      await api.post('/mail/spam/report', { folder: currentFolder, uid: msg.uid }).catch(() => { /* bloqueo ya creado */ });
      showToast(`${correo} bloqueado — sus correos iran a Correo no deseado`);
    } catch (e) { showToast(e instanceof Error && e.message ? e.message : 'No se pudo bloquear el remitente'); }
    window.dispatchEvent(new CustomEvent('refresh-messages'));
  };

  const etiquetasCtx = useEtiquetasContextual(currentFolder);   // submenú «Etiquetas» (05/11/2026)
  const getCtxItems = (msg: MessageSummary): MenuItem[] => [
    // Con el correo completo y su cita (05/11/2026): antes el reenvío salía sin el contenido original.
    { label: 'Responder', icon: replyIcon, onClick: () => { void responderDesdeLista(msg, currentFolder); } },
    { label: 'Reenviar', icon: forwardIcon, onClick: () => { void reenviarDesdeLista(msg, currentFolder); } },
    // El correo (o toda la selección si este forma parte de ella) viaja como .eml dentro de uno nuevo.
    { label: 'Reenviar como adjunto', icon: ICONO_CORREO_ADJUNTO, onClick: () => reenviarComoAdjunto(correosDeSeleccion(msg, Array.from(selectedUids), currentFolder)) },
    // Solo ese correo en otra pestaña; la bandeja de esta no cambia (lib/abrirEnPestana.ts).
    { label: 'Abrir en una nueva pestaña', icon: nuevaPestanaIcon, onClick: () => abrirMensajeEnPestana(msg.folder || currentFolder, msg.uid) },
    { label: '', icon: '', onClick: () => {}, divider: true },
    { label: msg.seen ? 'Marcar como no leído' : 'Marcar como leído', icon: unreadIcon, onClick: () => quickAction(msg.uid, msg.seen ? 'mark_unread' : 'mark_read') },
    { label: msg.flagged ? 'Quitar marca' : 'Marcar con bandera', icon: flagIcon, onClick: () => handleFlag(msg.uid, msg.flagged) },
    etiquetasCtx.itemMenu(msg, msgLabelsMap[claveEtiquetas(msg, currentFolder)] || []),
    { label: '', icon: '', onClick: () => {}, divider: true },
    { label: 'Archivar', icon: archiveIcon, onClick: () => quickAction(msg.uid, 'archive') },
    {
      label: 'Mover a...',
      icon: moveIcon,
      onClick: () => {},
      // Árbol madre → hijas con buscador: con 60 carpetas la lista plana no cabía ni se entendía (10/11/2026)
      contenido: (
        <ArbolMoverCarpetas carpetas={folders || []} carpetaActual={currentFolder}
          onElegir={(nombre) => { quickAction(msg.uid, 'move', nombre); setCtxMenu(null); }} />
      ),
    },
    // Ventana de regla precargada con el remitente y el asunto de este correo (10/11/2026)
    { label: 'Crear regla con este correo...', icon: reglaIcon, onClick: () => abrirModalRegla({ regla: reglaDesdeCorreo(msg, currentFolder) }) },
    { label: '', icon: '', onClick: () => {}, divider: true },
    (currentFolder === 'Junk' || currentFolder === 'Spam')
      ? { label: 'No es spam', icon: moveIcon, onClick: () => marcarNoDeseadoCtx(msg, true) }
      : { label: 'Marcar como spam', icon: moveIcon, onClick: () => marcarNoDeseadoCtx(msg, false) },
    ...(currentFolder === 'Junk' || currentFolder === 'Spam'
      ? [{ label: 'Confiar en este remitente', icon: moveIcon, onClick: () => confiarRemitenteCtx(msg) }]
      : []),
    { label: 'Bloquear remitente', icon: deleteIcon, onClick: () => bloquearRemitenteCtx(msg) },
    { label: '', icon: '', onClick: () => {}, divider: true },
    { label: 'Eliminar', icon: deleteIcon, onClick: () => quickAction(msg.uid, currentFolder === 'Trash' ? 'delete' : 'move', 'Trash'), danger: true },
  ];

  /* ---- Render a single message row (memoized) ---- */
  const renderMessageRow = useCallback((msg: MessageSummary, idx: number, threadCount?: number) => {
    const active = selectedMessage?.uid === msg.uid || (soloSeleccionar && activeIndex === idx);
    const checked = selectedUids.has(msg.uid);
    const snippetStyle = previewLines === 1
      ? undefined
      : {
          display: '-webkit-box',
          WebkitBoxOrient: 'vertical' as const,
          WebkitLineClamp: previewLines,
          overflow: 'hidden',
          whiteSpace: 'normal' as const,
        };
    const snippetMinHeight = previewLines === 1 ? undefined : `${previewLines * 16}px`;
    const alArrastrar = (e: React.DragEvent) => {
          const uids = selectedUids.has(msg.uid) && selectedUids.size > 0
            ? Array.from(selectedUids) : [msg.uid];
          e.dataTransfer.setData('application/x-mail-uids', JSON.stringify(uids));
          e.dataTransfer.setData('application/x-mail-folder', currentFolder);
          // `correos`: todos los arrastrados, para crear una tarea por cada uno al soltarlos en Tareas.
          const arrastrados = uids
            .map(u => (u === msg.uid ? msg : useMailStore.getState().messages.find(m => m.uid === u)))
            .filter((m): m is typeof msg => !!m);
          e.dataTransfer.setData('application/x-mail-meta', JSON.stringify({
            subject: msg.subject || '', from: msg.from || '', date: msg.date || '',
            uid: msg.uid, folder: currentFolder,
            correos: arrastrados.map(m => ({
              uid: m.uid, folder: currentFolder, subject: m.subject || '', from: m.from || '',
              message_id: m.message_id || '',
            })),
          }));
          // Mover a una carpeta o copiar al Calendario/Tareas (NavRail pide 'copy'): con solo 'move'
          // el navegador rechazaba el soltado en esos íconos sin avisar.
          e.dataTransfer.effectAllowed = 'copyMove';
          const badge = document.createElement('div');
          badge.textContent = uids.length > 1 ? `${uids.length} mensajes` : msg.subject || '1 mensaje';
          badge.style.cssText = 'padding:4px 10px;background:#0078d4;color:#fff;border-radius:4px;font-size:12px;position:absolute;top:-9999px';
          document.body.appendChild(badge);
          e.dataTransfer.setDragImage(badge, 0, 0);
          setTimeout(() => document.body.removeChild(badge), 0);
    };
    // En Enviados y Borradores la fila dice a quién se envió, no quién lo envió (como Outlook)
    const { quien, otros } = quienMostrar(msg, currentFolder, folders);
    const nombreQuien = extractName(quien, avatarMap) + (otros > 0 ? ` y ${otros} más` : '');
    const fecha = fmtDate(fechaMostrada({ ...msg, folder: msg.folder || currentFolder }, folders));
    if (unaLinea) {
      const spam = spamResults.find(s => s.uid === msg.uid);
      return (
        <FilaCorreoLinea key={msg.uid} msg={msg} threadCount={threadCount} idx={idx} asuntoPrimero={asuntoPrimero} onDoubleClick={() => soloSeleccionar ? handleSelect(msg.uid) : abrirMensajeEnVentana(msg.folder || currentFolder, msg.uid)}
          nombre={nombreQuien} iniciales={getInitials(quien, avatarMap)} fotoUrl={avatarMap[extractEmail(quien)]?.photo_url}
          color={getColor(quien)} fecha={fecha} activo={active} marcado={checked}
          fijado={pinnedSet.has(pinKey(currentFolder, msg.uid))} esSpam={!!spam} motivoSpam={spam?.reasons?.join(', ')}
          etiquetas={msgLabelsMap[claveEtiquetas(msg, currentFolder)] || []}
          onClick={(e) => handleRowClick(msg.uid, idx, e)}
          onContextMenu={(e) => { e.preventDefault(); setCtxMenu({ x: e.clientX, y: e.clientY, msg }); }}
          onDragStart={alArrastrar}
          onMarcar={(e) => { e.stopPropagation(); handleShiftClick(idx, e); }}
          onBandera={(e) => { e.stopPropagation(); handleFlag(msg.uid, msg.flagged); }}
          onEliminar={(e) => { e.stopPropagation(); quickAction(msg.uid, currentFolder === 'Trash' ? 'delete' : 'move', 'Trash'); }}
          onArchivar={(e) => { e.stopPropagation(); quickAction(msg.uid, 'archive'); }}
          onLeido={(e) => { e.stopPropagation(); quickAction(msg.uid, msg.seen ? 'mark_unread' : 'mark_read'); }}
          onFijar={(e) => { e.stopPropagation(); showToast(togglePins(currentFolder, [msg.uid]) ? 'Anclado arriba de la lista' : 'Desanclado'); }}
        />
      );
    }
    return (
      <div key={msg.uid}
        draggable
        onDragStart={alArrastrar}
        onClick={(e) => handleRowClick(msg.uid, idx, e)}
        onDoubleClick={() => soloSeleccionar ? handleSelect(msg.uid) : abrirMensajeEnVentana(msg.folder || currentFolder, msg.uid)}
        data-idx={idx}
        onContextMenu={(e) => { e.preventDefault(); setCtxMenu({ x: e.clientX, y: e.clientY, msg }); }}
        className={`group relative flex gap-2.5 pl-2 pr-3 ${density === "full" ? "py-[10px]" : density === "medium" ? "py-[7px]" : "py-[4px]"} cursor-pointer border-b border-[#f3f2f1] transition-all ${
          checked ? 'bg-[#deecf9]' : active ? 'bg-[#eff6fc]' : 'hover:bg-[#f3f2f1]'
        } ${!msg.seen ? "before:content-[''] before:absolute before:left-0 before:top-0 before:-bottom-px before:w-[3px] before:bg-[#0078d4] before:z-[1]" : ''}`}>

        {/* Unread dot + spam indicator */}
        <div className="w-[4px] shrink-0 flex items-start pt-2">
          <PuntoLeido noLeido={!msg.seen} esSpam={spamResults.some(s => s.uid === msg.uid)}
            motivoSpam={spamResults.find(s => s.uid === msg.uid)?.reasons?.join(', ')}
            onAlternar={() => quickAction(msg.uid, msg.seen ? 'mark_unread' : 'mark_read')} />
        </div>

        {/* Checkbox / Avatar */}
        <div className="shrink-0 pt-0.5" title={checked ? 'Quitar de la selección' : 'Seleccionar'}
          onClick={e => { e.stopPropagation(); handleShiftClick(idx, e); }}>
          {/* Como Outlook (07/11/2026): al pasar el ratón el círculo se cambia por una casilla cuadrada blanca;
              marcado = casilla azul con visto. Varias marcadas → la cinta actúa sobre todas o se arrastran juntas. */}
          <div className={`w-[32px] h-[32px] rounded-full flex items-center justify-center text-[11px] font-semibold text-white cursor-pointer ${
            checked ? '' : 'group-hover:!bg-transparent'
          }`} style={checked ? {} : { backgroundColor: getColor(quien) }}>
            {checked ? (
              <span className="w-[18px] h-[18px] rounded-[3px] bg-[#0078d4] flex items-center justify-center">
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>
              </span>
            ) : (<>
              {/* Foto del directorio si la hay; si no, iniciales (09/11/2026). Al pasar el ratón sigue saliendo la casilla. */}
              <span className="group-hover:hidden flex">
                <AvatarFoto url={avatarMap[extractEmail(quien)]?.photo_url} initials={getInitials(quien, avatarMap)} size={32} color={getColor(quien)} fontSize={11} />
              </span>
              <span className="hidden group-hover:block w-[18px] h-[18px] rounded-[3px] bg-white border-[1.5px] border-[#605e5c] hover:border-[#0078d4]" />
            </>)}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            {/* Primera línea: asunto o nombre según la preferencia de la persona (06/11/2026) */}
            <div className="flex items-center gap-1.5 min-w-0 flex-1">
              {/* No leído como Outlook (07/11/2026): el asunto en azul y negrita */}
              <span className={`text-[13px] truncate ${!msg.seen ? (asuntoPrimero ? 'font-semibold text-[#0078d4]' : 'font-semibold text-[#323130]') : 'text-[#605e5c]'}`}>
                {asuntoPrimero ? (msg.subject || '(Sin asunto)') : nombreQuien}
              </span>
              {asuntoPrimero && (msgLabelsMap[claveEtiquetas(msg, currentFolder)] || []).map((lbl) => (
                <span key={lbl.id} title={lbl.name}
                  className="shrink-0 inline-flex items-center px-1.5 h-[15px] rounded-[3px] text-[10px] font-medium text-white capitalize leading-none"
                  style={{ backgroundColor: lbl.color }}>
                  {String(lbl.name).replace(/^Categor[ií]a\s+/i, '') || lbl.name}
                </span>
              ))}
              {/* Thread count badge */}
              {threadCount && threadCount > 1 && (
                <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-[#0078d4] text-white text-[10px] font-semibold shrink-0">
                  {threadCount}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1 shrink-0 ml-2">
              {isPinned(currentFolder, msg.uid) && (
                <svg className="w-[12px] h-[12px] text-[#0078d4]" fill="currentColor" viewBox="0 0 20 20">
                  <title>Fijado</title>
                  <path d="M9 2a1 1 0 00-1 1v4.586L5.707 9.879A1 1 0 006.414 11.5H9V17a1 1 0 002 0v-5.5h2.586a1 1 0 00.707-1.621L12 7.586V3a1 1 0 00-1-1H9z" />
                </svg>
              )}
              {msg.has_attachments && (
                <svg className="w-[12px] h-[12px] text-[#605e5c]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                </svg>
              )}
              {msg.importance === 'high' && (
                <svg className="w-[12px] h-[12px] text-[#d13438]" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              )}
              {asuntoPrimero && <span className="text-[11px] text-[#605e5c] group-hover:hidden">{fecha}</span>}
            </div>
          </div>
          <div className="flex items-center gap-1.5 min-w-0">
            <p className={`text-[13px] truncate leading-[18px] ${!msg.seen ? (asuntoPrimero ? 'font-medium text-[#323130]' : 'font-semibold text-[#0078d4]') : 'text-[#605e5c]'}`}>
              {asuntoPrimero ? nombreQuien : (msg.subject || '(Sin asunto)')}
            </p>
            {!asuntoPrimero && (msgLabelsMap[claveEtiquetas(msg, currentFolder)] || []).map((lbl) => (
              <span key={lbl.id} title={lbl.name}
                className="shrink-0 inline-flex items-center px-1.5 h-[15px] rounded-[3px] text-[10px] font-medium text-white capitalize leading-none"
                style={{ backgroundColor: lbl.color }}>
                {String(lbl.name).replace(/^Categor[ií]a\s+/i, '') || lbl.name}
              </span>
            ))}
            {/* Hora de recibido junto al asunto, como Hotmail (06/11/2026) */}
            {!asuntoPrimero && <span className={`ml-auto pl-2 text-[11px] shrink-0 group-hover:hidden ${!msg.seen ? 'text-[#0078d4] font-semibold' : 'text-[#605e5c]'}`}>{fecha}</span>}
          </div>
          <p
            className={`text-[12px] text-[#605e5c] leading-[16px] ${previewLines === 1 ? 'truncate' : ''}`}
            style={{ ...snippetStyle, minHeight: snippetMinHeight }}
          >
            {msg.snippet || '\u00A0'}
          </p>
          <ChipsAdjuntosFila nombres={msg.adjuntos} />
        </div>

        {/* Chincheta (si está anclado) y bandera */}
        <div className="flex flex-col items-center justify-between shrink-0 py-0.5">
          {pinnedSet.has(pinKey(currentFolder, msg.uid)) && (
            <svg className="w-[13px] h-[13px] text-[#0078d4] mb-1" fill="currentColor" viewBox="0 0 24 24"><title>Anclado arriba</title><path d={pinIcon} /></svg>
          )}
          <button onClick={e => { e.stopPropagation(); handleFlag(msg.uid, msg.flagged); }}
            className={`transition-colors ${msg.flagged ? 'text-[#d13438]' : 'text-transparent group-hover:text-[#a19f9d] hover:!text-[#d13438]'}`}
            title={msg.flagged ? 'Quitar marca' : 'Marcar'}>
            <svg className="w-[14px] h-[14px]" fill={msg.flagged ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={flagIcon} />
            </svg>
          </button>
        </div>

        {/* Quick actions on hover */}
        <div className="hidden group-hover:flex max-md:hidden items-start gap-0.5 absolute right-2 top-1 bg-[#f3f2f1] rounded shadow-sm border border-[#e1dfdd] p-0.5">
          {/* Orden de Outlook (07/11/2026): leído, bandera, chincheta, archivar y eliminar */}
          <QA icon={unreadIcon} title={msg.seen ? 'Marcar como no leído' : 'Marcar como leído'}
            onClick={e => { e.stopPropagation(); quickAction(msg.uid, msg.seen ? 'mark_unread' : 'mark_read'); }} />
          <QA icon={flagIcon} title={msg.flagged ? 'Quitar la bandera' : 'Marcar con bandera'} filled={msg.flagged}
            onClick={e => { e.stopPropagation(); handleFlag(msg.uid, msg.flagged); }} />
          <QA icon={pinIcon} title={pinnedSet.has(pinKey(currentFolder, msg.uid)) ? 'Desanclar' : 'Anclar arriba'} filled={pinnedSet.has(pinKey(currentFolder, msg.uid))}
            onClick={e => { e.stopPropagation(); showToast(togglePins(currentFolder, [msg.uid]) ? 'Anclado arriba de la lista' : 'Desanclado'); }} />
          <QA icon={archiveIcon} title="Archivar" onClick={e => { e.stopPropagation(); quickAction(msg.uid, 'archive'); }} />
          <QA icon={deleteIcon} title="Eliminar" onClick={e => { e.stopPropagation(); quickAction(msg.uid, currentFolder === 'Trash' ? 'delete' : 'move', 'Trash'); }} />
        </div>
      </div>
    );
  // msgLabelsMap: sin él la fila leía las etiquetas de un cierre viejo y el chip no se repintaba
  // al asignar o quitar desde el menú (prueba Playwright, 05/11/2026).
  }, [selectedMessage?.uid, selectedUids, previewLines, density, unaLinea, asuntoPrimero, soloSeleccionar, activeIndex, currentFolder, avatarMap, folders, spamResults, filter, activeTab, priorityMap, msgLabelsMap, pinnedSet]);

  /* ---- Render thread group (conversation mode) ---- */
  const renderThreadGroup = (group: ThreadGroup, gIdx: number) => {
    const isExpanded = expandedThreads.has(group.thread_id);
    const msg = group.latest;

    if (group.count === 1) {
      // Single message thread - render normally
      return renderMessageRow(msg, gIdx);
    }

    return (
      <div key={group.thread_id}>
        {/* Thread header - shows latest message with count */}
        {renderMessageRow(msg, gIdx, group.count)}

        {/* Expanded thread children */}
        {isExpanded && (
          <div className="border-l-2 border-[#0078d4] ml-3">
            {group.messages.slice(1).map((childMsg, cIdx) => (
              <div key={childMsg.uid} className="pl-2">
                {renderMessageRow(childMsg, gIdx + cIdx + 1)}
              </div>
            ))}
          </div>
        )}

        {/* Expand/collapse button for threads with multiple messages */}
        {group.count > 1 && (
          <button
            onClick={(e) => { e.stopPropagation(); handleThreadHeaderClick(group); }}
            className="w-full flex items-center justify-center py-0.5 text-[11px] text-[#0078d4] hover:bg-[#f3f2f1] transition-colors border-b border-[#f3f2f1]"
          >
            {isExpanded ? (
              <span className="flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" /></svg>
                Ocultar {group.count - 1} mensaje{group.count - 1 > 1 ? 's' : ''} anterior{group.count - 1 > 1 ? 'es' : ''}
              </span>
            ) : (
              <span className="flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                Ver {group.count - 1} mensaje{group.count - 1 > 1 ? 's' : ''} anterior{group.count - 1 > 1 ? 'es' : ''}
              </span>
            )}
          </button>
        )}
      </div>
    );
  };

  return (
    <div
      style={readingPane === "right" ? { width: messageListWidth } : undefined}
      className={`message-list-container flex flex-col bg-white ${
        readingPane === "off" || readingPane === "fullscreen" || readingPane === "popout"
          ? "w-full min-w-0"
          : "min-w-[260px] shrink-0 border-r border-[#edebe9]"
      } max-md:w-full max-md:min-w-0 max-md:border-r-0`}>
      {/* Header with tabs */}
      <div className="border-b border-[#edebe9]">
        <div className="flex flex-wrap items-center px-3 pt-2 gap-1.5">
          <input type="checkbox"
            checked={selectedUids.size > 0 && selectedUids.size === filtered.length}
            ref={(el) => { if (el) el.indeterminate = selectedUids.size > 0 && selectedUids.size < filtered.length; }}
            onChange={(e) => {
              if (e.target.checked) {
                const s = new Set(filtered.map(m => m.uid));
                useMailStore.setState({ selectedUids: s });
              } else {
                useMailStore.getState().clearSelection();
              }
            }}
            className="w-4 h-4 shrink-0 rounded border-[#c8c6c4] text-[#0078d4] cursor-pointer accent-[#0078d4]"
            title="Seleccionar todos" aria-label="Seleccionar todos" />
          <h2 className="text-[14px] font-semibold text-[#323130] cursor-pointer hover:text-[#0078d4] transition-colors truncate max-w-[120px] sm:max-w-none sm:whitespace-nowrap" onClick={() => { const s = useMailStore.getState(); if (s.filter !== 'all') s.setFilter('all'); setActiveTab('focused'); }}>{searchQuery ? `Buscando «${searchQuery}»${currentFolder === 'Virtual.Todo' ? ' en todo el correo' : ''}` : folderLabel}</h2>
                    {!searchQuery && <BotonFavoritoCarpeta carpeta={currentFolder} />}
          <div className="flex-1" />
          <BotonOrdenLista carpeta={currentFolder} />
          <div className="flex items-center bg-[#f3f2f1] rounded-md p-0.5">
            {(['all','unread','flagged'] as const).map(f => (
              <button key={f} onClick={() => useMailStore.getState().setFilter(f)}
                className={`px-2 py-0.5 text-[11px] rounded cursor-pointer transition-colors whitespace-nowrap ${
                  filter === f ? 'bg-white text-[#323130] font-medium shadow-sm' : 'text-[#605e5c] hover:text-[#323130]'
                }`}>{f === 'all' ? 'Todos' : f === 'unread' ? 'No leídos' : 'Marcados'}</button>
            ))}
          </div>
        </div>
        {/* Focused / Other tabs + action icons (no en la vista por etiqueta: mezcla carpetas) */}
        {currentFolder === 'INBOX' && !etiquetaFiltro && (
          <div className="flex items-center px-3 mt-1">
            {(['focused','other'] as const).map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)} title={AYUDA_PESTANAS[tab]}
                className={`px-3 py-1.5 text-[13px] border-b-2 transition-colors ${
                  activeTab === tab ? 'border-[#0078d4] text-[#0078d4] font-medium' : 'border-transparent text-[#605e5c] hover:text-[#323130]'
                }`}>{tab === 'focused' ? 'Prioritarios' : 'Otros'}{tab === 'other' && otrosSinLeer.length > 0 && (
                  <span className="ml-1 text-[11px] font-semibold text-[#0078d4]">{otrosSinLeer.length}</span>
                )}</button>
            ))}
            <div className="flex-1" />
            <button
              onClick={() => scanSpam(true)}
              disabled={spamScanning}
              className={`p-1 rounded transition-colors ${
                spamScanning ? 'text-[#ca5010] animate-pulse' : 'text-[#a19f9d] hover:text-[#ca5010] hover:bg-[#fde7e9]'
              }`}
              title={spamScanning ? 'Escaneando...' : selectedMessage ? 'Escanear este mensaje con IA' : 'Escanear carpeta por spam'}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
            </button>
            {spamResults.length > 0 && (
              <span className="text-[10px] text-[#ca5010] font-bold" title="Spam detectado">
                {spamResults.length}!
              </span>
            )}
            <button
              onClick={() => useMailStore.getState().setViewMode(isConversationMode ? 'messages' : 'conversations')}
              className={`p-1 rounded transition-colors ${
                isConversationMode ? 'text-[#0078d4]' : 'text-[#a19f9d] hover:text-[#605e5c]'
              }`}
              title={isConversationMode ? 'Conversaciones (clic → mensajes)' : 'Mensajes (clic → conversaciones)'}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {isConversationMode ? (
                  <g strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}>
                    <path d="M19 7H5a2 2 0 00-2 2v8a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2z" />
                    <path d="M5 7V5a2 2 0 012-2h10a2 2 0 012 2v2" />
                  </g>
                ) : (
                  <g strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}>
                    <path d="M4 6h16M4 12h16M4 18h16" />
                  </g>
                )}
              </svg>
            </button>
          </div>
        )}
        {currentFolder === 'INBOX' && activeTab === 'focused' && filter === 'all' && (
          <AvisoOtrosSinLeer correos={otrosSinLeer} onVer={() => setActiveTab('other')} />
        )}
        {/* Action icons for non-INBOX folders */}
        {currentFolder !== 'INBOX' && (
          <div className="flex items-center px-3 pb-1">
            <div className="flex-1" />
            <button
              onClick={() => scanSpam(true)}
              disabled={spamScanning}
              className={`p-1 rounded transition-colors ${
                spamScanning ? 'text-[#ca5010] animate-pulse' : 'text-[#a19f9d] hover:text-[#ca5010] hover:bg-[#fde7e9]'
              }`}
              title={spamScanning ? 'Escaneando...' : selectedMessage ? 'Escanear este mensaje con IA' : 'Escanear carpeta por spam'}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
            </button>
          </div>
        )}
      </div>

      {/* Bulk actions bar */}
      {selectedUids.size > 0 && (
        <div className="flex items-center gap-0.5 px-2 py-1 bg-[#deecf9] border-b border-[#c7e0f4] shrink-0">
          <span className="text-[11px] text-[#0078d4] font-semibold mr-1 whitespace-nowrap shrink-0">
            {selectedUids.size}
          </span>
          <button onClick={() => { const uids = Array.from(selectedUids); if (hayEliminacionDefinitiva(uids, currentFolder) && !window.confirm(AVISO_ELIMINAR_CORREO)) return; eliminarSeleccion(uids, currentFolder).then(() => { showToast(`${uids.length} eliminado${uids.length > 1 ? 's' : ''}`); useMailStore.getState().clearSelection(); useMailStore.getState().setSelectedMessage(null); window.dispatchEvent(new CustomEvent('refresh-messages')); }).catch(() => showToast('No se pudieron eliminar los correos')); }}
            className="px-1.5 py-1 text-[11px] text-[#d13438] hover:bg-[#fde7e9] rounded flex items-center gap-1 shrink-0" title="Eliminar">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={deleteIcon} /></svg>
            <span>Eliminar</span>
          </button>
          <button onClick={() => { const uids = Array.from(selectedUids); accionEnLote(currentFolder, uids, 'archive', '', `${uids.length} archivado${uids.length > 1 ? 's' : ''}`); }}
            className="px-1.5 py-1 text-[11px] text-[#323130] hover:bg-[#c7e0f4] rounded flex items-center gap-1 shrink-0" title="Archivar">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={archiveIcon} /></svg>
            <span>Archivar</span>
          </button>
          <button onClick={() => { const uids = Array.from(selectedUids); accionEnLote(currentFolder, uids, 'mark_read', '', 'Marcados como leídos'); }}
            className="p-1.5 text-[#323130] hover:bg-[#c7e0f4] rounded shrink-0" title="Marcar como leídos">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21.75 9v.906a2.25 2.25 0 01-1.183 1.981l-6.478 3.488M2.25 9v.906a2.25 2.25 0 001.183 1.981l6.478 3.488m8.839 0l.415.223a.75.75 0 00.882-.264l2.197-2.989M2.25 15.577l.415.223a.75.75 0 01.882-.264l2.197-2.989" /></svg>
          </button>
          <button onClick={() => { const uids = Array.from(selectedUids); accionEnLote(currentFolder, uids, 'move', 'Junk', 'Movidos a Correo no deseado'); }}
            className="p-1.5 text-[#323130] hover:bg-[#c7e0f4] rounded shrink-0" title="Marcar como spam">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>
          </button>
          <div className="flex-1" />
          <button onClick={() => useMailStore.getState().clearSelection()}
            className="p-1.5 text-[#605e5c] hover:bg-[#c7e0f4] rounded shrink-0" title="Deseleccionar">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
      )}

      {/* Aviso: la búsqueda se limita a la carpeta elegida */}
      <AvisoBusquedaEnCarpeta />
      <CabeceraEtiqueta />

      {/* List */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto relative" style={{ overflowAnchor: 'none' }}>
        <EnviosEnCurso />
        {unaLinea && filtered.length > 0 && (
          /* Cabecera de columnas (06/11/2026): los anchos siguen a FilaCorreoLinea */
          <div className="sticky top-0 z-10 flex items-center gap-2 pl-1.5 pr-2 h-[28px] text-[12px] font-semibold text-[#605e5c] bg-[#faf9f8] border-b border-[#e1dfdd] select-none">
            <div className="w-[32px] shrink-0" />
            {asuntoPrimero ? (
              <>{celdaCabecera('asunto', 'Asunto', 'flex-1 min-w-0')}{celdaCabecera('de', 'De', 'w-[150px] lg:w-[190px] xl:w-[220px] shrink-0')}</>
            ) : (
              <>{celdaCabecera('de', 'De', 'w-[150px] lg:w-[190px] xl:w-[220px] shrink-0')}{celdaCabecera('asunto', 'Asunto', 'flex-1 min-w-0')}</>
            )}
            <div className="w-[72px] text-right shrink-0">Recibido</div>
            <div className="w-[13px] shrink-0" />
          </div>
        )}
        {loadingMessages && !filterChanging && debouncedSearchQuery ? (
          <>
          <div className="flex flex-col items-center justify-center h-48 px-6 text-center">
            <div className="w-6 h-6 border-2 border-[#0078d4] border-t-transparent rounded-full animate-spin" />
            <p className="text-[13px] font-semibold text-[#323130] mt-3">Buscando «{debouncedSearchQuery}»{currentFolder === 'Virtual.Todo' ? ' en todo tu correo' : ''}…</p>
            <p className="text-[12px] text-[#605e5c] mt-1">Un momento, por favor. La primera búsqueda en un buzón grande puede tardar unos segundos; las siguientes son inmediatas.</p>
          </div>
          {currentFolder === 'Virtual.Todo' && <AdelantoCarpetaActual consulta={debouncedSearchQuery} />}
          </>
        ) : loadingMessages && !filterChanging ? (
          Array.from({length:12}).map((_,i) => (
            <div key={i} className="animate-pulse flex gap-2.5 px-4 py-[6px] border-b border-[#f3f2f1]">
              <div className="w-[32px] h-[32px] bg-[#e1dfdd] rounded-full shrink-0 mt-0.5" />
              <div className="flex-1 space-y-1 py-0.5">
                <div className="h-[10px] bg-[#e1dfdd] rounded w-2/3" />
                <div className="h-[10px] bg-[#e1dfdd] rounded w-4/5" />
                <div className="h-[8px] bg-[#f3f2f1] rounded w-full" />
              </div>
            </div>
          ))
        ) : filterChanging ? (
          <div className="flex flex-col items-center justify-center h-40">
            <div className="w-5 h-5 border-2 border-[#0078d4] border-t-transparent rounded-full animate-spin" />
            <p className="text-[12px] text-[#a19f9d] mt-2">Cargando...</p>
          </div>
        ) : filtered.length === 0 && errorCarga ? (
          <div className="flex flex-col items-center justify-center h-40 px-4 text-center text-[#323130]" role="alert">
            <p className="text-[14px] font-semibold">No se pudo cargar el correo</p>
            <p className="text-[13px] text-[#605e5c] mt-1">Sus correos siguen guardados en el servidor. Revise la conexión e inténtelo de nuevo.</p>
            <button onClick={() => { setErrorCarga(false); fetch_(); }}
              className="mt-3 px-4 py-2 text-[14px] font-semibold text-white bg-[#0078d4] hover:bg-[#106ebe] rounded">
              Reintentar
            </button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-[#605e5c]">
            <svg className="w-10 h-10 mb-2 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
            </svg>
            {/* Pestaña «No leídos»/«Marcados» activa (05/11/2026): avisar antes de las sugerencias,
                con «Ver todos»; si no, la gente cree que el buscador no encuentra nada. */}
            {(filter === 'unread' || filter === 'flagged') && (
              <AvisoFiltroSinResultados filtro={filter} consulta={searchQuery} carpeta={currentFolder} buscarEnContenido={buscarEnContenido} />
            )}
            {searchQuery ? (
              <SinResultados consulta={searchQuery} enTodo={currentFolder === 'Virtual.Todo'} carpeta={folderLabel} />
            ) : filter === 'all' ? (
              <p className="text-[13px]">No hay mensajes</p>
            ) : null}
            {!searchQuery && filter === 'flagged' && <p className="text-[11px] mt-1 text-[#a19f9d]">Usa el icono de bandera en un correo para marcarlo</p>}
          </div>
        ) : isConversationMode && threadGroups ? (
          threadGroups.map((group, gIdx) => renderThreadGroup(group, gIdx))
        ) : (
          filtered.map((msg, idx) => renderMessageRow(msg, idx))
        )}
        {/* Centinela de scroll infinito */}
        {!loadingMessages && filtered.length > 0 && messages.length < totalMessages && (
          <div ref={loadMoreRef} className="py-4 flex justify-center">
            {!navigator.onLine
              ? <p className="text-[11px] text-[#a19f9d] text-center px-4">Sin conexión: estos son los correos descargados (últimos {Math.min(60, Math.max(7, parseInt(localStorage.getItem('offline.dias') || '30', 10) || 30))} días). Con internet verás el resto; en Configuración puedes descargar más días.</p>
              : loadingMore && <div className="w-4 h-4 border-2 border-[#0078d4] border-t-transparent rounded-full animate-spin" />}
          </div>
        )}
      </div>

      {ctxMenu && <ContextMenu x={ctxMenu.x} y={ctxMenu.y} items={getCtxItems(ctxMenu.msg)} onClose={() => setCtxMenu(null)} />}
      {etiquetasCtx.dialogo}
    </div>
  );
}

const QA = memo(function QA({ icon, title, onClick, filled }: {
  icon: string; title: string; onClick: (e: React.MouseEvent) => void; filled?: boolean;
}) {
  return (
    <button onClick={onClick} title={title}
      className="w-[26px] h-[26px] rounded flex items-center justify-center text-[#605e5c] hover:bg-[#e1dfdd] hover:text-[#323130] transition-colors">
      <svg className="w-[14px] h-[14px]" fill={filled ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={icon} />
      </svg>
    </button>
  );
});