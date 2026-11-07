/**
 * Autocompletar con IA: decidir si la sugerencia continúa el texto o lo reescribe entero.
 *
 * El modelo a veces devuelve el correo completo (lo ya escrito, corregido, más el final) en
 * lugar de solo la continuación. Pegar eso detrás del último punto duplicaba el texto; en ese
 * caso la sugerencia REEMPLAZA el cuerpo. Si es una continuación, se agrega al final.
 */

function palabras(texto: string): string[] {
  return texto
    .toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .split(/[^a-z0-9ñ]+/)
    .filter(p => p.length > 2);
}

/** true si la sugerencia repite buena parte de lo que ya estaba escrito (es una reescritura). */
export function esReescritura(original: string, sugerencia: string): boolean {
  const escritas = palabras(original);
  if (escritas.length < 3) return false;
  const enSugerencia = new Set(palabras(sugerencia));
  const repetidas = escritas.filter(p => enSugerencia.has(p)).length;
  return repetidas / escritas.length >= 0.6;
}

/** Texto plano de la IA → HTML de párrafos para el editor. */
export function textoAParrafos(texto: string): string {
  const escapar = (t: string) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return texto
    .trim()
    .split(/\n{2,}/)
    .map(p => `<p>${escapar(p).replace(/\n/g, '<br>')}</p>`)
    .join('');
}

/**
 * Cómo pegar la continuación detrás de lo escrito (04/11/2026).
 *
 * Antes se anteponía SIEMPRE un espacio y una palabra a medias quedaba partida («Estimad as
 * compañeras…»). Ahora:
 * - `continuaPalabra` (lo decide el servidor, que ve la salida cruda del modelo): se une sin
 *   espacio («Estimad» + «as» → «Estimadas»).
 * - Si lo escrito está vacío o termina en espacio o salto de línea, no se agrega espacio.
 * - Si la sugerencia empieza por un signo de cierre («,», «.», «:», «)»…), tampoco.
 * - En cualquier otro caso, un espacio.
 *
 * Devuelve el texto que va en la misma línea (`enLinea`) y los párrafos siguientes (la
 * sugerencia puede traer el saludo y luego «\n\n» con el cuerpo).
 */
export function unirSugerencia(previo: string, sugerencia: string, continuaPalabra = false):
  { enLinea: string; parrafos: string[] } {
  const bloques = sugerencia.replace(/\r\n?/g, '\n').replace(/\s+$/, '').split(/\n{2,}/);
  let primero = bloques[0] ?? '';
  const parrafos = bloques.slice(1).map(p => p.trim()).filter(Boolean);
  if (continuaPalabra) {
    return { enLinea: primero, parrafos };
  }
  primero = primero.replace(/^[ \t]+/, '');
  const terminaEnEspacio = previo === '' || /\s$/.test(previo);
  const empiezaConCierre = /^[,.;:!?)\]}»”’…]/.test(primero);
  const separador = terminaEnEspacio || empiezaConCierre || primero === '' ? '' : ' ';
  return { enLinea: separador + primero, parrafos };
}
