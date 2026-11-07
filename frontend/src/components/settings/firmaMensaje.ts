/**
 * Mensaje personalizado dentro de una firma.
 *
 * Caso (05/11/2026, Graciela Aguirre): necesita varias firmas, cada una con un texto
 * distinto encima de los datos de contacto (p. ej. «Adjunto el comprobante de pago…»),
 * para elegir la firma y enviar sin escribir nada más. El modo «Datos» del editor de
 * firmas solo tenía nombre, cargo, teléfonos, correo y ciudad.
 *
 * El mensaje se guarda dentro del mismo HTML de la firma, en un bloque marcado con la
 * clase `firma-mensaje`, para que al volver a editar la firma se recupere en su campo.
 */

const CLASE = 'firma-mensaje';
const RE_BLOQUE = /<div class="firma-mensaje"[^>]*>([\s\S]*?)<\/div>\s*/;

function escaparHtml(texto: string): string {
  return texto
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Convierte el texto plano del campo en párrafos (una línea = un salto). */
export function mensajeAHtml(mensaje: string): string {
  const limpio = mensaje.replace(/\r\n/g, '\n').trim();
  if (!limpio) return '';
  const parrafos = limpio
    .split(/\n{2,}/)
    .map((p) => `<p style="margin:0 0 10px 0">${escaparHtml(p).replace(/\n/g, '<br>')}</p>`)
    .join('');
  return `<div class="${CLASE}" style="font-family:Verdana,Geneva,sans-serif;font-size:13px;color:#323130;margin-bottom:14px">${parrafos}</div>`;
}

/** Antepone el mensaje (si lo hay) al HTML de la firma. */
export function envolverMensaje(firmaHtml: string, mensaje: string): string {
  const bloque = mensajeAHtml(mensaje);
  return bloque ? bloque + firmaHtml : firmaHtml;
}

/** Separa el mensaje guardado del resto de la firma. Devuelve el mensaje como texto plano. */
export function extraerMensaje(html: string): { mensaje: string; firma: string } {
  const m = html.match(RE_BLOQUE);
  if (!m) return { mensaje: '', firma: html };
  const mensaje = m[1]
    .replace(/<\/p>\s*<p[^>]*>/g, '\n\n')
    .replace(/<br\s*\/?>/g, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .trim();
  return { mensaje, firma: html.replace(RE_BLOQUE, '') };
}
