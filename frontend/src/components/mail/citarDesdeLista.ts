/**
 * citarDesdeLista.ts — «Responder» y «Reenviar» desde el menú contextual de la lista (05/11/2026).
 *
 * El menú de la lista solo tiene el resumen del correo (sin cuerpo), y hasta hoy abría el redactor
 * con html_body vacío: el reenvío salía SIN el contenido del original (solo los adjuntos, si los
 * había) y la respuesta sin cita. Caso real: reenvío «RV: NOTIFICACION DE DEUDA POR VENCER» de
 * serviciosgenerales@ a contabilidadagro@ el 05/11/2026 12:54, cuerpo = <p></p>.
 * Aquí se carga el correo completo y se arma la misma cita que usan la vista del correo y la tecla F.
 */
import { format } from 'date-fns';
import { es } from 'date-fns/locale';
import { api } from '../../api/client';
import { buildQuoteHtml } from '../../lib/citaRespuesta';
import { showToast } from '../common/Toast';
import { useMailStore } from '../../store/mailStore';
import type { MessageFull, MessageSummary } from '../../types';

async function cargarCompleto(folder: string, uid: number): Promise<MessageFull | null> {
  try {
    return await api.get<MessageFull>(`/mail/message/${encodeURIComponent(folder)}/${uid}`);
  } catch {
    return null;
  }
}

function cita(msg: MessageFull, reenvio: boolean): string {
  const fecha = msg.date ? format(new Date(msg.date), "d 'de' MMMM 'de' yyyy, HH:mm", { locale: es }) : '';
  return buildQuoteHtml(
    msg.from, fecha, msg.to, msg.cc, msg.subject,
    msg.html_body || `<pre style="white-space:pre-wrap">${msg.text_body || ''}</pre>`,
    reenvio,
  );
}

export async function responderDesdeLista(resumen: MessageSummary, carpetaActual: string): Promise<void> {
  const folder = resumen.folder || carpetaActual;
  const msg = await cargarCompleto(folder, resumen.uid);
  if (!msg) showToast('No se pudo incluir el correo original en la respuesta');
  useMailStore.getState().openCompose('reply', {
    to: [msg?.from_addr || msg?.from || resumen.from],
    subject: resumen.subject.startsWith('Re:') ? resumen.subject : `Re: ${resumen.subject}`,
    text_body: '',
    html_body: msg ? cita(msg, false) : '',
    in_reply_to: msg?.message_id || '',
    references: msg ? (msg.references ? `${msg.references} ${msg.message_id}` : (msg.message_id || '')) : '',
  });
}

export async function reenviarDesdeLista(resumen: MessageSummary, carpetaActual: string): Promise<void> {
  const folder = resumen.folder || carpetaActual;
  const msg = await cargarCompleto(folder, resumen.uid);
  if (!msg) showToast('No se pudo incluir el contenido del correo original en el reenvío');
  useMailStore.getState().openCompose('forward', {
    to: [],
    subject: resumen.subject.startsWith('RV:') ? resumen.subject : `RV: ${resumen.subject}`,
    text_body: '',
    html_body: msg ? cita(msg, true) : '',
    in_reply_to: msg?.message_id || '',
    references: msg ? (msg.references ? `${msg.references} ${msg.message_id}` : (msg.message_id || '')) : '',
    reenvio_de: { folder, uid: resumen.uid, adjuntos: msg?.attachments },
  });
}
