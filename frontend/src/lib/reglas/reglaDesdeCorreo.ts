import type { MessageSummary } from '../../types';
import { normalizarRegla, type Regla } from './tipos';

/* Regla precargada a partir de un correo: remitente y asunto como condiciones, y la carpeta
   actual (si no es una del sistema) como destino. La persona ajusta lo que quiera antes de guardar. */

const CARPETAS_SISTEMA = new Set(['INBOX', 'Sent', 'Drafts', 'Trash', 'Junk', 'Spam', 'Archive']);

/** La dirección de «Nombre <dir@dominio>» o el texto tal cual si ya es una dirección. */
export function direccionDe(texto: string): string {
  const m = /<([^>]+)>/.exec(texto || '');
  return (m ? m[1] : texto || '').trim().toLowerCase();
}

/** Asunto sin los prefijos de respuesta o reenvío (Re:, RV:, Fwd:, …). */
export function asuntoLimpio(asunto: string): string {
  return (asunto || '').replace(/^(\s*(re|rv|fw|fwd|tr|aw|wg)\s*:\s*)+/i, '').trim();
}

export function reglaDesdeCorreo(msg: Pick<MessageSummary, 'from' | 'subject'>, carpetaActual: string): Regla {
  const remitente = direccionDe(msg.from);
  const asunto = asuntoLimpio(msg.subject);
  const nombre = remitente ? `Correos de ${remitente}` : 'Regla nueva';
  const destino = carpetaActual && !CARPETAS_SISTEMA.has(carpetaActual) && !carpetaActual.startsWith('Compartidos,')
    ? carpetaActual : '';
  return normalizarRegla({
    name: nombre.slice(0, 80),
    match: 'allof',
    conditions: [
      ...(remitente ? [{ field: 'from' as const, operator: 'contains' as const, value: remitente }] : []),
      ...(asunto ? [{ field: 'subject' as const, operator: 'contains' as const, value: asunto }] : []),
    ],
    actions: [{ type: 'move', value: destino }],
    stop: true,
    enabled: true,
  });
}
