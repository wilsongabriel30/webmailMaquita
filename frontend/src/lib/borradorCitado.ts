/**
 * Un borrador de respuesta se guarda como [texto de la persona] + [contenido citado]
 * (sin la firma). Al reabrirlo hay que volver a separar las dos partes: el texto va
 * al editor y la cita se muestra aparte, para que la firma quede entre ambos y la
 * cita no pase por el editor (que la reformatea y la deforma).
 */
const MARCA_CITA = /<div class="quoted-content"/i;

export function separarCitado(html: string): { cuerpo: string; citado: string } {
  const m = MARCA_CITA.exec(html || '');
  if (!m) return { cuerpo: html || '', citado: '' };
  return { cuerpo: html.slice(0, m.index), citado: html.slice(m.index) };
}
