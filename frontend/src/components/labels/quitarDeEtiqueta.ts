// Quitar correos de la etiqueta que se está viendo, SIN borrarlos (pedido de Dirección, 19/11/2026).
//
// En la vista de una etiqueta, «Eliminar» manda el correo a la Papelera (y como la etiqueta va con
// el correo, seguía saliendo en la etiqueta). Faltaba lo que la persona quería: quitarle solo la
// etiqueta. El correo se queda en su carpeta; únicamente deja de aparecer en esta vista.
import { useMailStore } from '../../store/mailStore';
import { showToast } from '../common/Toast';
import { asignarEtiquetaA, type CorreoRef } from './asignarEtiquetas';

/** Correos sobre los que actuar: los marcados en la lista o, si no hay, el que está abierto. */
export function correosElegidos(): CorreoRef[] {
  const st = useMailStore.getState();
  const abierto = st.selectedMessage as ({ uid: number; folder?: string } | null);
  const uids = st.selectedUids.size > 0 ? Array.from(st.selectedUids) : (abierto ? [abierto.uid] : []);
  const enLista = new Map(st.messages.map((m) => [m.uid, m.folder]));
  return uids.map((uid) => ({ uid, folder: enLista.get(uid) || (abierto && abierto.uid === uid ? abierto.folder : undefined) }));
}

export async function quitarDeEtiquetaActual(correos: CorreoRef[] = correosElegidos()): Promise<void> {
  const st = useMailStore.getState();
  const etiqueta = st.etiquetaFiltro;
  if (!etiqueta) return;
  if (correos.length === 0) { showToast('Seleccione el correo que quiere quitar de la etiqueta'); return; }
  try {
    const r = await asignarEtiquetaA(Number(etiqueta.id), correos, st.currentFolder, true);
    if (!r.hechos) { showToast('No se pudo quitar la etiqueta'); return; }
    const fuera = new Set(correos.map((c) => c.uid));
    useMailStore.setState((s) => ({
      messages: s.messages.filter((m) => !fuera.has(m.uid)),
      totalMessages: Math.max(0, s.totalMessages - r.hechos),
      selectedUids: new Set<number>(),
      selectedMessage: s.selectedMessage && fuera.has(s.selectedMessage.uid) ? null : s.selectedMessage,
    }));
    showToast(r.hechos === 1
      ? `Se quitó la etiqueta «${etiqueta.name}». El correo sigue en su carpeta.`
      : `Se quitó la etiqueta «${etiqueta.name}» de ${r.hechos} correos. Siguen en sus carpetas.`);
  } catch {
    showToast('No se pudo quitar la etiqueta');
  }
}
