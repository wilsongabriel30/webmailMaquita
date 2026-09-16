/**
 * Acciones en lote (mover, eliminar, archivar, limpiar) con actualización optimista.
 *
 * Los mensajes desaparecen de la lista en el mismo instante en que la persona pulsa el botón;
 * el servidor trabaja por detrás y, si fallara, la lista se restaura y se avisa.
 */
import { api } from '../api/client';
import { useMailStore } from '../store/mailStore';
import { showToast } from '../components/common/Toast';

export type AccionLote = 'move' | 'delete' | 'archive' | 'mark_read' | 'mark_unread' | 'flag' | 'unflag';

const SACAN_DE_LA_VISTA: ReadonlySet<string> = new Set(['move', 'delete', 'archive']);

/** Quita los UIDs de la lista actual (todos si la lista de UIDs está vacía) y devuelve cómo deshacerlo. */
export function quitarDeLaLista(uids: number[]): () => void {
  const st = useMailStore.getState();
  const previos = st.messages;
  const totalPrevio = st.totalMessages;
  const pagina = st.currentPage;
  const ids = new Set(uids);
  const restantes = uids.length === 0 ? [] : previos.filter(m => !ids.has(m.uid));
  const quitados = previos.length - restantes.length;
  st.setMessages(restantes, uids.length === 0 ? 0 : Math.max(0, totalPrevio - quitados), pagina);
  if (st.selectedMessage && (uids.length === 0 || ids.has(st.selectedMessage.uid))) {
    st.setSelectedMessage(null);
  }
  st.clearSelection();
  return () => useMailStore.getState().setMessages(previos, totalPrevio, pagina);
}

/**
 * Ejecuta una acción en lote sobre la carpeta actual.
 * Devuelve true si el servidor la confirmó.
 */
export async function accionEnLote(
  carpeta: string,
  uids: number[],
  accion: AccionLote,
  destino = '',
  mensajeOk = '',
  mensajeError = 'No se pudo completar la acción',
): Promise<boolean> {
  const optimista = SACAN_DE_LA_VISTA.has(accion);
  const deshacer = optimista ? quitarDeLaLista(uids) : null;
  if (optimista && mensajeOk) showToast(mensajeOk);
  try {
    await api.post(`/mail/bulk-action/${encodeURIComponent(carpeta)}`, { uids, action: accion, dest_folder: destino });
    if (!optimista) {
      if (mensajeOk) showToast(mensajeOk);
      useMailStore.getState().clearSelection();
    }
    window.dispatchEvent(new CustomEvent('refresh-messages'));
    return true;
  } catch {
    deshacer?.();
    showToast(mensajeError);
    return false;
  }
}
