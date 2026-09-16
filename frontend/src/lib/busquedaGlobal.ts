/**
 * Búsqueda en todas las carpetas.
 *
 * Dovecot expone el buzón virtual «Virtual.Todo» (todas las carpetas de la persona: entrada,
 * enviados, papelera, no deseado, expurgados y propias). Cuando la persona busca con
 * «Todas las carpetas» activo, el webmail pasa a ese buzón, así que una sola búsqueda IMAP
 * recorre todo el correo; al borrar la búsqueda vuelve a la carpeta en la que estaba.
 */
import { useMailStore } from '../store/mailStore';

export const CARPETA_TODO = 'Virtual.Todo';
const CLAVE_PREFERENCIA = 'maquita_buscar_en_todo';

let carpetaPrevia = 'INBOX';

export function leerPreferenciaTodo(): boolean {
  try { return localStorage.getItem(CLAVE_PREFERENCIA) !== '0'; } catch { return true; }
}

export function guardarPreferenciaTodo(v: boolean) {
  try { localStorage.setItem(CLAVE_PREFERENCIA, v ? '1' : '0'); } catch { /* sin almacenamiento */ }
}

/** Aplica el texto de búsqueda respetando el ámbito elegido (todas las carpetas o la actual). */
export function aplicarBusqueda(q: string) {
  const st = useMailStore.getState();
  const texto = q.trim();
  if (texto && st.buscarEnTodo && st.currentFolder !== CARPETA_TODO) {
    carpetaPrevia = st.currentFolder;
    // Carpeta y búsqueda en un solo cambio: si no, la lista cargaba primero el buzón entero
    // y luego la búsqueda, y ambas respuestas se mezclaban.
    st.setCarpetaYBusqueda(CARPETA_TODO, q);
    return;
  }
  if (!texto && st.currentFolder === CARPETA_TODO) {
    st.setCarpetaYBusqueda(carpetaPrevia || 'INBOX', '');
    return;
  }
  st.setSearchQuery(q);
}

/** Cambia el ámbito y, si hay una búsqueda escrita, la repite en el ámbito nuevo. */
export function cambiarAmbito(enTodo: boolean) {
  const st = useMailStore.getState();
  guardarPreferenciaTodo(enTodo);
  st.setBuscarEnTodo(enTodo);
  const q = st.searchQuery;
  if (!q.trim()) return;
  if (enTodo) {
    aplicarBusqueda(q);
  } else if (st.currentFolder === CARPETA_TODO) {
    st.setCarpetaYBusqueda(carpetaPrevia || 'INBOX', q);
  }
}
