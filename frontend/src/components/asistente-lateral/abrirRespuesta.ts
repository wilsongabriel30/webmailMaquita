/**
 * Abre la redacción de una respuesta al correo con un texto ya escrito por la IA.
 * Hace lo mismo que «usar respuesta sugerida» en la vista del correo (MessageView.tsx).
 */
import { format } from 'date-fns';
import { es } from 'date-fns/locale';
import { buildQuoteHtml, escapeHtml, extractEmail } from '../../lib/citaRespuesta';
import { useMailStore } from '../../store/mailStore';
import type { MessageFull } from '../../types';

export function abrirRespuestaConTexto(msg: MessageFull, texto: string): void {
  const fecha = msg.date ? format(new Date(msg.date), "d 'de' MMMM 'de' yyyy, HH:mm", { locale: es }) : '';
  const cita = buildQuoteHtml(
    msg.from, fecha, msg.to, msg.cc, msg.subject,
    msg.html_body || `<pre style="white-space:pre-wrap">${escapeHtml(msg.text_body || '')}</pre>`,
    false,
  );
  useMailStore.getState().openCompose('reply', {
    to: [extractEmail(msg.from)],
    subject: msg.subject.startsWith('Re:') ? msg.subject : `Re: ${msg.subject}`,
    text_body: '',
    in_reply_to: msg.message_id || '',
    references: msg.references ? `${msg.references} ${msg.message_id}` : (msg.message_id || ''),
    html_body: cita,
    prefill_body: `<p>${escapeHtml(texto).replace(/\n/g, '<br>')}</p>`,
  });
}
