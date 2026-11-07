/**
 * correosComoAdjunto.ts — «Reenviar como adjunto» (05/11/2026).
 *
 * En Zimbra se podía adjuntar un correo dentro de otro (.eml) y la gente lo reclamaba como
 * «no se puede adjuntar correos». El correo crudo lo entrega el servidor en
 * /api/mail/message/{carpeta}/{uid}/eml (message/rfc822) y entra al redactor como un adjunto
 * más, con el asunto por nombre. Sirve para uno o varios correos (selección múltiple) y para
 * los correos que se arrastran desde la lista hasta el redactor.
 */
import type { ArchivoAdjunto } from './adjuntosBorrador';
import type { MessageSummary } from '../types';
import { useMailStore } from '../store/mailStore';

export interface CorreoAAdjuntar { folder: string; uid: number; subject: string }

export const TIPO_EML = 'message/rfc822';
/** Tipo que pone la lista al arrastrar correos (MessageList.tsx, `alArrastrar`). */
export const TIPO_ARRASTRE_CORREOS = 'application/x-mail-meta';
/** Icono de clip (ruta SVG) para los menús. */
export const ICONO_CORREO_ADJUNTO = 'M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48';

/** Nombre de archivo seguro a partir del asunto: «Factura 123.eml». */
export function nombreArchivoEml(asunto: string): string {
  const base = (asunto || '').replace(/[\\/:*?"<>|\u0000-\u001f]+/g, '_').replace(/\s+/g, ' ').trim().slice(0, 120);
  return (base || 'correo') + '.eml';
}

export async function descargarCorreoComoEml(c: CorreoAAdjuntar): Promise<ArchivoAdjunto | null> {
  try {
    const res = await fetch('/api/mail/message/' + encodeURIComponent(c.folder) + '/' + c.uid + '/eml', { credentials: 'include' });
    if (!res.ok) return null;
    const blob = await res.blob();
    if (!blob.size) return null;
    const file = new File([blob], nombreArchivoEml(c.subject), { type: TIPO_EML });
    return { name: file.name, size: file.size, type: file.type, file };
  } catch {
    return null;
  }
}

/** Descarga varios correos; devuelve los que entraron y los nombres de los que no se pudieron traer. */
export async function descargarCorreosComoEml(correos: CorreoAAdjuntar[]): Promise<{ cargados: ArchivoAdjunto[]; fallidos: string[] }> {
  const cargados: ArchivoAdjunto[] = [];
  const fallidos: string[] = [];
  for (const c of correos) {
    const adj = await descargarCorreoComoEml(c);
    if (adj) cargados.push(adj);
    else fallidos.push(c.subject || `correo ${c.uid}`);
  }
  return { cargados, fallidos };
}

/** Abre un redactor nuevo con los correos indicados como adjuntos .eml (ComposePanel los descarga). */
export function reenviarComoAdjunto(correos: CorreoAAdjuntar[]): void {
  if (!correos.length) return;
  const asunto = correos.length === 1 ? `RV: ${correos[0].subject || '(sin asunto)'}` : `RV: ${correos.length} correos`;
  useMailStore.getState().openCompose('new', { to: [], subject: asunto, text_body: '', html_body: '', correos_adjuntos: correos });
}

/**
 * Correos a adjuntar según la selección: si el correo pulsado forma parte de una selección múltiple,
 * van todos los seleccionados; si no, solo ese.
 */
export function correosDeSeleccion(msg: MessageSummary | null, uids: number[], carpeta: string): CorreoAAdjuntar[] {
  const lista = useMailStore.getState().messages;
  const elegidos = msg && uids.length > 1 && uids.includes(msg.uid) ? uids : (msg ? [msg.uid] : uids);
  return elegidos
    .map(u => (msg && u === msg.uid ? msg : lista.find(m => m.uid === u)))
    .filter((m): m is MessageSummary => !!m)
    .map(m => ({ folder: m.folder || carpeta, uid: m.uid, subject: m.subject || '' }));
}

/** Correos que vienen en un arrastre desde la lista, o [] si lo arrastrado no son correos. */
export function correosArrastrados(dt: DataTransfer): CorreoAAdjuntar[] {
  if (!Array.from(dt.types).includes(TIPO_ARRASTRE_CORREOS)) return [];
  try {
    const meta = JSON.parse(dt.getData(TIPO_ARRASTRE_CORREOS)) as {
      correos?: { uid: number; folder: string; subject?: string }[];
      uid?: number; folder?: string; subject?: string;
    };
    const lista = meta.correos?.length
      ? meta.correos
      : (meta.uid && meta.folder ? [{ uid: meta.uid, folder: meta.folder, subject: meta.subject || '' }] : []);
    return lista.map(c => ({ folder: c.folder, uid: c.uid, subject: c.subject || '' }));
  } catch {
    return [];
  }
}
