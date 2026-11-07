/**
 * Cita del correo original al responder o reenviar.
 *
 * 27/10/2026: extraído de MessageView.tsx (ya superaba las 1900 líneas) para que el
 * panel lateral del asistente pueda abrir una respuesta igual que la vista del correo.
 */
import { sanitizeHtml } from './sanitize';

export function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/** Dirección de un remitente con formato «Nombre <correo>» o solo «correo». */
export function extractEmail(raw: string): string {
  const match = raw.match(/<([^>]+)>/);
  return match ? match[1] : raw.trim();
}

export function buildQuoteHtml(
  from: string,
  date: string,
  to: string,
  cc: string,
  subject: string,
  htmlBody: string,
  isForward: boolean,
): string {
  const header = isForward
    ? '<p style="font-weight:bold;margin:0 0 8px">--- Mensaje reenviado ---</p>'
    : '';

  const ccLine = cc ? `<b>CC:</b> ${escapeHtml(cc)}<br>` : '';

  // Escalar imagenes y tablas de firmas para que no se desborden en compose
  // Bug 2026-04-10: firmas con imagenes grandes ocupaban toda la pantalla
  // Se aplican estilos INLINE porque TipTap elimina <style> tags
  // Imagenes/tablas se escalan via CSS en EditorContent (clase .quoted-content)

  return `
<div class="quoted-content" style="border-top:1px solid #edebe9;padding-top:12px;margin-top:20px;max-width:100%;overflow:hidden">
  ${header}
  <p style="font-size:12px;color:#605e5c;margin:0 0 8px">
    <b>De:</b> ${escapeHtml(from)}<br>
    <b>Enviado:</b> ${escapeHtml(date)}<br>
    <b>Para:</b> ${escapeHtml(to)}<br>
    ${ccLine}
    <b>Asunto:</b> ${escapeHtml(subject)}
  </p>
  <div style="font-size:14px">${sanitizeHtml(htmlBody)}</div>
</div>`.trim();
}
