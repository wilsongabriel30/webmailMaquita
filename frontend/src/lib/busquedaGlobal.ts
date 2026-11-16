/**
 * Búsqueda en todas las carpetas.
 *
 * Dovecot expone el buzón virtual «Virtual.Todo» (todas las carpetas de la persona: entrada,
 * enviados, papelera, no deseado, expurgados y propias). Cuando la persona busca con
 * «Todas las carpetas» activo, el webmail pasa a ese buzón, así que una sola búsqueda IMAP
 * recorre todo el correo; al borrar la búsqueda vuelve a la carpeta en la que estaba.
 */
import { useMailStore } from '../store/mailStore';
import { alCambiarBuzonVirtual, hayBuzonVirtual, useBuzonVirtual } from './buzonVirtual';

export const CARPETA_TODO = 'Virtual.Todo';

/**
 * Interruptor de «buscar en todas las carpetas» (13/11/2026: APAGADO por decisión de Tecnología).
 * En algunos casos el servidor de correo no resuelve esa búsqueda con el índice y recorre el buzón
 * entero leyendo cada correo: hubo 16 búsquedas colgadas durante horas y el disco de buzones al 100 %.
 * Mientras se corrige de fondo, solo se busca dentro de la carpeta abierta. Poner `true` para volver
 * a mostrar el botón, el enlace del aviso y el salto automático cuando la carpeta no tiene resultados.
 */
export const TODO_EL_CORREO_DISPONIBLE = true;

/**
 * ¿Se puede buscar en todas las carpetas AQUÍ? Hace falta el interruptor de arriba y que el
 * servidor tenga el buzón virtual (lib/buzonVirtual.ts; 15/11/2026). Si no, todo lo de este
 * archivo busca en la carpeta abierta, diga lo que diga la preferencia guardada (que no se toca:
 * vuelve a valer el día que el servidor tenga el buzón).
 */
export function hayTodoElCorreo(): boolean {
  return TODO_EL_CORREO_DISPONIBLE && hayBuzonVirtual();
}

/** Lo mismo, para componentes (se actualiza cuando el servidor responde). */
export function useTodoElCorreo(): boolean {
  const hay = useBuzonVirtual();
  return TODO_EL_CORREO_DISPONIBLE && hay;
}
const CLAVE_PREFERENCIA = 'maquita_buscar_en_todo';
/** Valor guardado cuando la persona elige buscar solo en la carpeta abierta. */
const SOLO_CARPETA = 'carpeta';

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
 * Ámbito por defecto: todas las carpetas (13/11/2026, decisión de Tecnología: «todas las carpetas
 * es básico y debe estar siempre activo», como en los demás programas de correo). Solo busca en
 * la carpeta abierta quien lo eligió expresamente («carpeta»). El «0» que guardaba la versión
 * anterior se ponía solo al cambiar de carpeta, no por decisión de la persona: no cuenta.
 */
export function leerPreferenciaTodo(): boolean {
  try { return localStorage.getItem(CLAVE_PREFERENCIA) !== SOLO_CARPETA; } catch { return true; }
}

/**
 * Al elegir una carpeta en la barra lateral ya no se cambia el ámbito de la búsqueda: antes se
 * pasaba a «solo esta carpeta» y la persona perdía «todas las carpetas» sin haberlo pedido.
 * Se conserva la función porque la barra lateral la llama.
 */
export function buscarSoloEnCarpetaActual() {
  /* El ámbito solo lo cambia la persona, con el selector del buscador. */
}

export function guardarPreferenciaTodo(v: boolean) {
  try { localStorage.setItem(CLAVE_PREFERENCIA, v ? '1' : SOLO_CARPETA); } catch { /* sin almacenamiento */ }
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
  if (texto && hayTodoElCorreo() && st.buscarEnTodo && st.currentFolder !== CARPETA_TODO) {
    // Con «todas las carpetas», la primera letra tecleada ya cambiaba de buzón y lanzaba la
    // búsqueda de esa sola letra sobre todo el correo («S», «a», «k»: 20 s cada una y 360 000
    // resultados; 13/11/2026). Ahora se espera a que haya al menos 3 letras (o un operador) y a
    // que la persona deje de escribir, igual que en la búsqueda dentro de una carpeta.
    st.setSearchQuery(q);
    if (esCorta(texto)) return;
    relojTodo = setTimeout(() => {
      const ahora = useMailStore.getState();
      if (ahora.searchQuery !== q || !ahora.buscarEnTodo || ahora.currentFolder === CARPETA_TODO || !hayTodoElCorreo()) return;
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
  if (!hayTodoElCorreo()) return;
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
  if (enTodo && !hayTodoElCorreo()) return;
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

// El servidor dice que no hay buzón virtual (o una petición a él dio 404) estando en «todas las
// carpetas»: se vuelve a la carpeta de antes con la misma búsqueda, en vez de dejar la lista en error.
alCambiarBuzonVirtual(() => {
  if (hayBuzonVirtual()) return;
  clearTimeout(relojTodo);
  const st = useMailStore.getState();
  if (st.currentFolder !== CARPETA_TODO) return;
  origenAmpliacion = null;
  st.setCarpetaYBusqueda(carpetaPrevia || 'INBOX', st.searchQuery);
});
