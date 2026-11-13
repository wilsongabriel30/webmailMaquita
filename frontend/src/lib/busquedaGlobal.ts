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
/** Pausa tras la última tecla antes de buscar en todo el correo (algo menor que la de la lista, 800 ms). */
const PAUSA_AL_ESCRIBIR_MS = 600;
let relojTodo: ReturnType<typeof setTimeout> | undefined;

/** Menos de 3 letras y sin operador («de:», «es:»…): todavía no se busca. */
function esCorta(texto: string): boolean {
  return texto.length < 3 && !texto.includes(':');
}
/** Carpeta desde la que la búsqueda se amplió sola a todo el correo (null si no ocurrió). */
let origenAmpliacion: string | null = null;
/** Búsqueda que la persona pidió ver en su carpeta: no se vuelve a ampliar sola. */
let noAmpliar = '';

/** Carpeta en la que estaba la persona al empezar a buscar en todas las carpetas. */
export function carpetaAnterior(): string {
  return carpetaPrevia || 'INBOX';
}

/**
 * Ámbito por defecto: la carpeta en la que está la persona (19/10/2026, pedido del equipo:
 * «cuando el usuario seleccione una carpeta y utilice el buscador, la búsqueda debe realizarse
 * exclusivamente dentro de esa carpeta»). «Todas las carpetas» queda como opción a un clic.
 */
export function leerPreferenciaTodo(): boolean {
  try { return localStorage.getItem(CLAVE_PREFERENCIA) === '1'; } catch { return false; }
}

/**
 * Al elegir una carpeta en la barra lateral, la búsqueda se limita a esa carpeta.
 * No repite ninguna búsqueda: cambiar de carpeta ya borra el texto buscado.
 */
export function buscarSoloEnCarpetaActual() {
  const st = useMailStore.getState();
  if (!st.buscarEnTodo) return;
  guardarPreferenciaTodo(false);
  st.setBuscarEnTodo(false);
}

export function guardarPreferenciaTodo(v: boolean) {
  try { localStorage.setItem(CLAVE_PREFERENCIA, v ? '1' : '0'); } catch { /* sin almacenamiento */ }
}

/** Aplica el texto de búsqueda respetando el ámbito elegido (todas las carpetas o la actual). */
export function aplicarBusqueda(q: string) {
  const st = useMailStore.getState();
  const texto = q.trim();
  // Una búsqueda nueva mira todos los correos, no solo los «no leídos» o «con bandera» que
  // estuvieran filtrados: con el filtro puesto, el correo ya leído que se buscaba no aparecía
  // («barry» con «No leídos» activo daba cero; 13/11/2026). El filtro se puede volver a poner después.
  if (texto && st.filter !== 'all') st.setFilter('all');
  if (!texto) origenAmpliacion = null;
  clearTimeout(relojTodo);
  if (texto && st.buscarEnTodo && st.currentFolder !== CARPETA_TODO) {
    // Con «todas las carpetas», la primera letra tecleada ya cambiaba de buzón y lanzaba la
    // búsqueda de esa sola letra sobre todo el correo («S», «a», «k»: 20 s cada una y 360 000
    // resultados; 13/11/2026). Ahora se espera a que haya al menos 3 letras (o un operador) y a
    // que la persona deje de escribir, igual que en la búsqueda dentro de una carpeta.
    st.setSearchQuery(q);
    if (esCorta(texto)) return;
    relojTodo = setTimeout(() => {
      const ahora = useMailStore.getState();
      if (ahora.searchQuery !== q || !ahora.buscarEnTodo || ahora.currentFolder === CARPETA_TODO) return;
      carpetaPrevia = ahora.currentFolder;
      // Carpeta y búsqueda en un solo cambio: si no, la lista cargaba primero el buzón entero
      // y luego la búsqueda, y ambas respuestas se mezclaban.
      ahora.setCarpetaYBusqueda(CARPETA_TODO, q);
    }, PAUSA_AL_ESCRIBIR_MS);
    return;
  }
  if (!texto && st.currentFolder === CARPETA_TODO) {
    st.setCarpetaYBusqueda(carpetaPrevia || 'INBOX', '');
    return;
  }
  st.setSearchQuery(q);
}

/** Carpeta en la que no había resultados y desde la que se amplió la búsqueda, o null. */
export function ampliadaDesde(): string | null {
  return useMailStore.getState().currentFolder === CARPETA_TODO ? origenAmpliacion : null;
}

/**
 * En la carpeta no hay nada y en el resto del correo sí: se muestran los resultados de todas las
 * carpetas. No cambia la preferencia de la persona: su próxima búsqueda vuelve a ser en la carpeta.
 */
export function ampliarPorFaltaDeResultados(q: string) {
  const st = useMailStore.getState();
  if (!q.trim() || st.currentFolder === CARPETA_TODO || st.searchQuery !== q || q === noAmpliar) return;
  carpetaPrevia = st.currentFolder;
  origenAmpliacion = st.currentFolder;
  st.setCarpetaYBusqueda(CARPETA_TODO, q);
}

/** Deshace la ampliación automática: vuelve a la carpeta, con la misma búsqueda. */
export function volverALaCarpeta() {
  const st = useMailStore.getState();
  const destino = origenAmpliacion || carpetaPrevia || 'INBOX';
  origenAmpliacion = null;
  noAmpliar = st.searchQuery;
  st.setCarpetaYBusqueda(destino, st.searchQuery);
}

/** Cambia el ámbito y, si hay una búsqueda escrita, la repite en el ámbito nuevo. */
export function cambiarAmbito(enTodo: boolean) {
  const st = useMailStore.getState();
  origenAmpliacion = null;
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
