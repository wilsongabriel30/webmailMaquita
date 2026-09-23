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
