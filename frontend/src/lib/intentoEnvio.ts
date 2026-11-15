/**
 * intentoEnvio.ts — Un solo identificador por intento de envío (13/11/2026).
 *
 * El servidor no envía dos veces un correo que llega con el mismo identificador
 * (`/api/mail/send-segundo-plano?envio_id=…`, válido 24 h). Para que eso proteja de verdad, el
 * identificador tiene que ser EL MISMO en todos los caminos que puede seguir un correo desde que
 * la persona pulsa «Enviar»:
 *   - la copia retenida en la cola de salida durante los segundos de «Deshacer»;
 *   - el primer intento directo;
 *   - la cola de salida, si el navegador se queda sin respuesta o sin red;
 *   - el reenvío del MISMO correo desde la ventana que se vuelve a abrir cuando no se pudo
 *     confirmar si salió.
 * Antes cada camino generaba el suyo: si la primera petición llegaba al servidor y la respuesta
 * se perdía, la cola lo mandaba otra vez con otro identificador y el correo salía repetido.
 */
import type { OutboxEmail } from './offlineStore';

/** Intento anterior de una ventana que se volvió a abrir sin saber si el correo salió. */
export interface EnvioPrevio { id: string; huella: string }

/** El servidor ya dio un resultado final para ese identificador (error o «no se sabe»). */
export class EnvioTerminado extends Error {}

export function nuevoIdDeEnvio(): string {
  try { return crypto.randomUUID(); } catch { return `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`; }
}

interface Contenido {
  to?: string[]; cc?: string[]; bcc?: string[]; subject?: string; html_body?: string;
  attachments?: Array<{ filename: string; content_b64: string }>;
}

const direcciones = (l?: string[]) => (l || []).map(d => d.trim().toLowerCase()).sort().join(',');

/** Resumen del contenido: dos envíos con la misma huella son el mismo correo. Se compara el
 *  texto (sin etiquetas ni espacios), porque el HTML cambia de forma al reabrir la ventana. */
export function huellaDeEnvio(c: Contenido): string {
  const texto = (c.html_body || '').replace(/<[^>]*>/g, '').replace(/&nbsp;|\s+/g, '');
  const adjuntos = (c.attachments || []).map(a => `${a.filename}:${a.content_b64.length}`).sort().join('|');
  const base = [direcciones(c.to), direcciones(c.cc), direcciones(c.bcc), (c.subject || '').trim(), texto, adjuntos].join('\x1f');
  let h = 2166136261;
  for (let i = 0; i < base.length; i++) { h ^= base.charCodeAt(i); h = Math.imul(h, 16777619); }
  return `${base.length}-${(h >>> 0).toString(16)}`;
}

/** Identificador con el que sale este correo: el del intento anterior si es el mismo correo. */
export function idDeIntento(previo: EnvioPrevio | undefined, huella: string): string {
  return previo && previo.huella === huella ? previo.id : nuevoIdDeEnvio();
}

/**
 * Tras un fallo, lo que debe heredar la ventana que se vuelve a abrir. Si el servidor ya dio un
 * resultado final (rechazo, o «no se sabe» porque se reinició), repetir el identificador solo
 * devolvería ese mismo resultado: el próximo envío lleva uno nuevo. En cualquier otro caso
 * (respuesta perdida, red caída, consultas sin contestar) el correo pudo haber salido: se
 * conserva, y si la persona lo reenvía sin cambios el servidor responde cómo terminó en vez de
 * enviarlo otra vez.
 */
export function envioPrevioSi(err: unknown, id: string, huella: string): EnvioPrevio | undefined {
  return err instanceof EnvioTerminado ? undefined : { id, huella };
}

type ParaCola = Omit<OutboxEmail, 'id' | 'createdAt' | 'status' | 'retries'>;

/** Lo que la cola de salida necesita para enviar el correo igual que el envío directo
 *  (remitente elegido, sensibilidad y el borrador que hay que retirar al salir). */
export function paraCola(p: ParaCola & Record<string, unknown>): ParaCola {
  return {
    from_email: p.from_email, to: p.to, cc: p.cc, bcc: p.bcc, subject: p.subject,
    html_body: p.html_body, text_body: p.text_body, in_reply_to: p.in_reply_to, references: p.references,
    attachments: p.attachments, request_read_receipt: p.request_read_receipt,
    request_delivery_receipt: p.request_delivery_receipt, importance: p.importance,
    sensitivity: p.sensitivity, draft_uid: p.draft_uid, dlp_override: p.dlp_override, dlp_reason: p.dlp_reason,
  };
}
