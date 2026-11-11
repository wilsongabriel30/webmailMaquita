import { useEffect } from 'react';
import { useMailStore } from '../store/mailStore';
import { api } from '../api/client';
import type { MessageFull } from '../types';
import { sanitizeHtml } from '../lib/sanitize';
import { destinatariosResponderATodos } from '../lib/destinatariosRespuesta';
import { showToast } from '../components/common/Toast';
import { confirmarBorradoDefinitivo } from '../lib/confirmarBorrado';
import { agruparUidsPorCarpeta } from '../lib/carpetaReal';
import { abrirConFlecha, pedido, sigueVigente } from '../lib/aperturaConFlechas';
import { accionDeshacer, deshacerUltimo, loteDeRespuesta, recordarParaDeshacer, type LoteMovido, type RespuestaMover } from '../lib/deshacerMover';

// Shift + flechas: ancla y selección previa al empezar a extender (como Outlook, 10/11/2026)
let anclaShift = -1;
let seleccionBase: Set<number> | null = null;
// Último correo al que llegó la extensión: si el resaltado ya no está ahí (hubo un clic o cambió la
// lista), la siguiente Shift + flecha empieza de nuevo desde el correo resaltado (11/11/2026).
let ultimoExtendido = -1;

function extenderSeleccionConFlecha(idx: number, newIdx: number, uids: number[]) {
  const st = useMailStore.getState();
  if (anclaShift < 0 || anclaShift >= uids.length || !seleccionBase || idx !== ultimoExtendido) {
    anclaShift = idx >= 0 ? idx : newIdx;
    seleccionBase = new Set(st.selectedUids);
  }
  const desde = Math.min(anclaShift, newIdx), hasta = Math.max(anclaShift, newIdx);
  const s = new Set(seleccionBase);
  for (let i = desde; i <= hasta; i++) s.add(uids[i]);
  useMailStore.setState({ selectedUids: s });
  st.setActiveIndex(newIdx);
  ultimoExtendido = newIdx;
}


function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function buildQuoteHtml(msg: MessageFull, type: 'reply' | 'forward'): string {
  const header = type === 'forward'
    ? '<p style="font-weight:600;margin:0 0 8px">--- Mensaje reenviado ---</p>'
    : '';
  return `<div style="border-top:1px solid #edebe9;padding-top:12px;margin-top:20px">
    ${header}
    <p style="font-size:12px;color:#605e5c;margin:0 0 8px">
      <b>De:</b> ${escapeHtml(msg.from)}<br>
      <b>Para:</b> ${escapeHtml(msg.to)}<br>
      ${msg.cc ? `<b>CC:</b> ${escapeHtml(msg.cc)}<br>` : ''}
      <b>Asunto:</b> ${escapeHtml(msg.subject)}
    </p>
    ${msg.html_body ? sanitizeHtml(msg.html_body) : `<pre style="white-space:pre-wrap;font-family:inherit">${escapeHtml(msg.text_body || '')}</pre>`}
  </div>`;
}

export function useKeyboardShortcuts() {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Si otro componente ya atendió la tecla, no se repite la acción.
      if (e.defaultPrevented) return;
      const target = e.target as HTMLElement;
      const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable;
      // Con el foco en un botón, enlace o control, Enter y las flechas son de ese control: así un
      // botón enfocado con Tab se activa con Enter. Dentro de un diálogo, las teclas son del diálogo.
      const enControl = !!target.closest?.('button, a[href], select, summary, [role="button"], [role="link"], [role="menuitem"], [role="option"], [role="tab"], [role="checkbox"], [role="switch"], [role="slider"], [role="combobox"]');
      const enDialogo = !!target.closest?.('[role="dialog"], [role="alertdialog"], [aria-modal="true"], dialog');
      if (enDialogo) return;
      const state = useMailStore.getState();

      // Escape always works
      if (e.key === 'Escape') {
        // Las ventanas de redaccion NO se cierran desde aqui. Cerrarlas con closeCompose se
        // llevaba por delante lo escrito: el redactor tiene su propio Escape, que guarda el
        // borrador antes de cerrar, y este atajo se le adelantaba. Las minimizadas tampoco: su
        // redactor ni siquiera esta montado, asi que nadie podria guardar por ellas.
        // Solo un redactor ABIERTO se queda con Escape. Uno minimizado (abrir un correo minimiza
        // todos los redactores) no está montado y dejaba la tecla sin efecto: «Esc no me regresa a
        // la bandeja» (05/11/2026). Con un correo abierto, Esc vuelve al listado antes que nada.
        if (state.composeWindows.some(w => !w.minimized)) {
          return;
        } else if (state.selectedMessage) {
          state.setSelectedMessage(null);
        } else if (state.selectedUids.size > 0) {
          state.clearSelection();
        }
        e.preventDefault();
        return;
      }

      if (isInput || enControl) return;

      // Los atajos de una letra (N, R, F, E, /) solo valen sin Ctrl, Cmd ni Alt: Ctrl+F es
      // «buscar en la página», Ctrl+R recarga y Ctrl+N abre ventana. Antes Ctrl+F abría un
      // reenvío. Ctrl+A se atiende aparte, más abajo.
      if (e.key.length === 1 && (e.ctrlKey || e.metaKey || e.altKey) && !['a', 'z'].includes(e.key.toLowerCase())) return;
      // Sin Shift se olvida el ancla de la selección con flechas
      if (!e.shiftKey && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) { anclaShift = -1; seleccionBase = null; ultimoExtendido = -1; }

      // Se navega la lista VISIBLE (05/11/2026): «Otros» y chinchetas hacen que messages[idx]
      // no sea el correo resaltado. Ver components/mail/listaVisible.ts.
      const uids = state.visibleUids.length ? state.visibleUids : state.messages.map(m => m.uid);
      const idx = state.activeIndex;
      const folder = state.currentFolder;
      // Panel de lectura apagado o a pantalla completa (escritorio) y sin correo abierto: las flechas
      // solo mueven el resaltado por la lista; Enter o doble clic abren (pedido de Gerencia, 05/11/2026).
      const soloResaltar = (state.readingPane === 'off' || state.readingPane === 'fullscreen')
        && !state.selectedMessage && window.innerWidth >= 768;

      switch (e.key) {
        // Flecha mantenida (e.repeat): solo se mueve el resaltado y se abre el último correo al
        // soltar; antes cada repetición pedía un correo completo (bucle de 429, 05/11/2026).
        case 'ArrowDown':
          e.preventDefault();
          if (idx < uids.length - 1) {
            const newIdx = idx + 1;
            if (e.shiftKey) { extenderSeleccionConFlecha(idx, newIdx, uids); break; }
            state.setActiveIndex(newIdx);
            if (!soloResaltar) abrirConFlecha(uids[newIdx], e.repeat, (uid) => selectMessage(uid, folder));
          }
          break;

        case 'ArrowUp':
          e.preventDefault();
          if (idx > 0) {
            const newIdx = idx - 1;
            if (e.shiftKey) { extenderSeleccionConFlecha(idx, newIdx, uids); break; }
            state.setActiveIndex(newIdx);
            if (!soloResaltar) abrirConFlecha(uids[newIdx], e.repeat, (uid) => selectMessage(uid, folder));
          }
          break;

        case 'Enter':
          e.preventDefault();
          if (idx >= 0 && idx < uids.length) {
            selectMessage(uids[idx], folder);
          }
          break;

        case 'Delete':
          e.preventDefault();
          if (state.selectedUids.size > 0) {
            bulkAction(Array.from(state.selectedUids), folder === 'Trash' ? 'delete' : 'move', 'Trash', folder);
          } else if (state.selectedMessage) {
            bulkAction([state.selectedMessage.uid], folder === 'Trash' ? 'delete' : 'move', 'Trash', folder);
          } else if (idx >= 0 && idx < uids.length) {
            // Fila solo resaltada (panel de lectura apagado, 05/11/2026): Supr también la borra.
            bulkAction([uids[idx]], folder === 'Trash' ? 'delete' : 'move', 'Trash', folder);
          }
          break;

        case 'z':
          // Ctrl+Z: deshacer el último movimiento (mover, archivar, enviar a la Papelera) de los últimos 2 min
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            void deshacerUltimo().then(hecho => { if (!hecho) showToast('Nada que deshacer'); });
          }
          break;

        case 'a':
          if (e.ctrlKey || e.metaKey) {
            // Only select all messages if no message is open for reading
            if (!state.selectedMessage) {
              e.preventDefault();
              state.selectAll();
            }
            // Otherwise let browser handle Ctrl+A (select text in message view)
          }
          break;

        case 'n':
        case 'N':
          e.preventDefault();
          state.openCompose('new');
          break;

        case 'r':
          e.preventDefault();
          if (state.selectedMessage) {
            const msg = state.selectedMessage;
            const quoteHtml = buildQuoteHtml(msg, 'reply');
            state.openCompose('reply', {
              to: [msg.from],
              subject: msg.subject.startsWith('Re:') ? msg.subject : `Re: ${msg.subject}`,
              text_body: '',
              html_body: quoteHtml,
              in_reply_to: msg.message_id || '',
              references: msg.references || '',
            });
          }
          break;

        case 'R':
          e.preventDefault();
          if (state.selectedMessage) {
            const msg = state.selectedMessage;
            const quoteHtml = buildQuoteHtml(msg, 'reply');
            const destinatarios = destinatariosResponderATodos({ ...msg, folder: msg.folder || folder });
            state.openCompose('replyAll', {
              to: destinatarios.to,
              cc: destinatarios.cc,
              subject: msg.subject.startsWith('Re:') ? msg.subject : `Re: ${msg.subject}`,
              text_body: '',
              html_body: quoteHtml,
              in_reply_to: msg.message_id || '',
              references: msg.references || '',
            });
          }
          break;

        case 'f':
        case 'F':
          e.preventDefault();
          if (state.selectedMessage) {
            const msg = state.selectedMessage;
            const quoteHtml = buildQuoteHtml(msg, 'forward');
            state.openCompose('forward', {
              to: [],
              subject: msg.subject.startsWith('RV:') ? msg.subject : `RV: ${msg.subject}`,
              text_body: '',
              html_body: quoteHtml,
              reenvio_de: { folder: msg.folder || folder, uid: msg.uid, adjuntos: msg.attachments },
            });
          }
          break;

        case 'e':
          if (!e.ctrlKey && !e.metaKey) {
            e.preventDefault();
            if (state.selectedUids.size > 0) {
              bulkAction(Array.from(state.selectedUids), 'archive', '', folder);
            } else if (state.selectedMessage) {
              bulkAction([state.selectedMessage.uid], 'archive', '', folder);
            }
          }
          // Let Ctrl+E pass through for browser use
          break;

        case '/':
          e.preventDefault();
          document.getElementById('search-input')?.focus();
          break;
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
}

async function selectMessage(uid: number, folder: string) {
  const state = useMailStore.getState();
  state.setLoadingMessage(true);
  pedido(uid);
  try {
    const msg = await api.get<MessageFull>(`/mail/message/${encodeURIComponent(folder)}/${uid}`);
    // Si mientras tanto se pidió otro correo, esta respuesta ya no interesa (05/11/2026).
    if (!sigueVigente(uid)) return;
    // Estado FRESCO tras la espera (05/11/2026): con el capturado antes se pisaban los correos
    // llegados mientras se abría este.
    const ahora = useMailStore.getState();
    ahora.setSelectedMessage(msg);
    const updated = ahora.messages.map(m => m.uid === uid ? { ...m, seen: true, flags: m.flags.includes('\\Seen') ? m.flags : [...m.flags, '\\Seen'] } : m);
    ahora.setMessages(updated, ahora.totalMessages, ahora.currentPage);
  } catch {
    if (!sigueVigente(uid)) return;
    // Sin esto la persona pulsa, no se abre nada y no sabe por que.
    showToast('No se pudo abrir el mensaje');
  }
}

async function bulkAction(uids: number[], action: string, dest: string, folder: string) {
  // La tecla Supr en la Papelera borra para siempre: se pregunta antes.
  if (action === 'delete' && !confirmarBorradoDefinitivo(uids.length)) return;
  try {
    // Cada correo en su carpeta real (vista por etiqueta / Todo el correo, 05/11/2026).
    const lotes: LoteMovido[] = [];
    for (const [carpetaReal, lote] of agruparUidsPorCarpeta(uids, folder)) {
      const r = await api.post<RespuestaMover>(`/mail/bulk-action/${encodeURIComponent(carpetaReal)}`, { uids: lote, action, dest_folder: dest });
      const movido = loteDeRespuesta(carpetaReal, action === 'archive' ? 'Archive' : dest, r);
      if (movido) lotes.push(movido);
    }
    // Una tecla suelta (Supr, E) hace desaparecer el correo: se dice siempre adónde fue (y «Deshacer»).
    const idAviso = showToast(action === 'delete' ? 'Eliminado definitivamente'
      : action === 'archive' ? 'Archivado (está en la carpeta Archivo)'
      : action === 'move' && dest === 'Trash' ? 'Movido a la Papelera'
      : 'Hecho', accionDeshacer(lotes));
    if (lotes.length) recordarParaDeshacer(lotes, idAviso);
    useMailStore.getState().setSelectedMessage(null);
    useMailStore.getState().clearSelection();
    window.dispatchEvent(new CustomEvent('refresh-messages'));
  } catch {
    // Archivar, borrar o mover varios correos y que falle en silencio es peor que el fallo:
    // se da por hecho lo que no ocurrio.
    showToast('No se pudo completar la acción sobre los correos seleccionados');
  }
}
