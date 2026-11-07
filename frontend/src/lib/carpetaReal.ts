// Carpeta real de cada correo (05/11/2026).
//
// En «Todo el correo» (Virtual.Todo) y en la vista por etiqueta la lista mezcla correos de varias
// carpetas: toda acción (abrir, bandera, mover, etiquetar) debe ir a la carpeta REAL del mensaje,
// no a la carpeta «actual» de la lista. Antes se usaba siempre la actual y, por ejemplo, clasificar
// desde Virtual.Todo guardaba la etiqueta con un uid virtual que nunca se volvía a ver.
import { useMailStore } from '../store/mailStore';

export const CARPETA_VIRTUAL = 'Virtual.Todo';

export function carpetaDelMensaje(msg: { folder?: string } | undefined, carpetaActual: string): string {
  return (msg && msg.folder) || carpetaActual;
}

/** Carpeta real del uid según la lista cargada; si no está en la lista, la actual. */
export function carpetaDeUid(uid: number, carpetaActual?: string): string {
  const st = useMailStore.getState();
  const actual = carpetaActual ?? st.currentFolder;
  return carpetaDelMensaje(st.messages.find((m) => m.uid === uid), actual);
}

/** Reparte los uids por su carpeta real (para lanzar una acción en lote por carpeta). */
export function agruparUidsPorCarpeta(uids: number[], carpetaActual?: string): Map<string, number[]> {
  const st = useMailStore.getState();
  const actual = carpetaActual ?? st.currentFolder;
  const porUid = new Map<number, string>(st.messages.map((m) => [m.uid, m.folder || actual]));
  const grupos = new Map<string, number[]>();
  for (const u of uids) {
    const f = porUid.get(u) || actual;
    const lote = grupos.get(f) || [];
    lote.push(u);
    grupos.set(f, lote);
  }
  return grupos;
}

/** Carpeta válida para etiquetar, o null si el correo está en el buzón virtual (uids virtuales,
 *  que no corresponden a ninguna carpeta real). */
export function carpetaEtiquetable(msg: { folder?: string } | undefined, carpetaActual: string): string | null {
  const f = carpetaDelMensaje(msg, carpetaActual);
  return f === CARPETA_VIRTUAL ? null : f;
}

export const AVISO_SIN_ETIQUETAS_EN_TODO = 'En «Todo el correo» no se puede etiquetar: abre la carpeta del correo.';
