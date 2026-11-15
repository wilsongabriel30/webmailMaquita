/**
 * copiasEnTodo.ts — El mismo correo en varias carpetas, una sola fila (13/11/2026).
 *
 * Desde que la búsqueda recorre todas las carpetas por defecto, un correo que está en más de una
 * (el que la persona se envía a sí misma queda en «Enviados» y en la Bandeja de entrada; el que
 * una regla copia a una carpeta; el que sigue en la Papelera) salía dos o tres veces en los
 * resultados, idéntico y sin decir de qué carpeta era: parecía que el correo había llegado
 * repetido. El servidor no informa la carpeta real de cada resultado de «todas las carpetas», así
 * que aquí se deja a la vista UNA copia por identificador de mensaje (`Message-ID`) y las demás
 * se ocultan de la lista. No se borra ni se mueve nada: cada copia sigue en su carpeta.
 */
import { CARPETA_TODO } from './busquedaGlobal';

interface Fila { uid: number; message_id?: string | null; seen?: boolean }

/**
 * UID (del buzón de todas las carpetas) de las copias que no hace falta mostrar. De cada grupo se
 * deja la que está sin leer —la recibida— y, si todas están leídas, la primera de la lista.
 * Fuera de «todas las carpetas» no oculta nada. Un correo sin identificador nunca se agrupa.
 */
export function copiasRepetidas(mensajes: Fila[], carpeta: string): Set<number> {
  const ocultas = new Set<number>();
  if (carpeta !== CARPETA_TODO) return ocultas;
  const elegida = new Map<string, Fila>();
  for (const m of mensajes) {
    const id = (m.message_id || '').trim();
    if (!id) continue;
    const previa = elegida.get(id);
    if (!previa) { elegida.set(id, m); continue; }
    if (previa.seen && !m.seen) { ocultas.add(previa.uid); elegida.set(id, m); }
    else ocultas.add(m.uid);
  }
  return ocultas;
}
