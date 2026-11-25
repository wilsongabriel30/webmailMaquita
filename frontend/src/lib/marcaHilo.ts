/**
 * marcaHilo.ts — Marca de «respondido» (↩) / «reenviado» (↪) en la lista de correos (25/11/2026).
 *
 * Pedido de Gerencia: en Enviados y Recibidos, que un correo muestre un signo de que ya se
 * respondió o se reenvió, como lo hacía Zimbra. Se usan las marcas IMAP estándar:
 *   - Respondido → \Answered   (bandera de sistema; la pone el servidor/cliente al responder).
 *   - Reenviado  → $Forwarded  (palabra clave; así lo dejó la migración de Zimbra).
 *
 * Aquí viven la DETECCIÓN (para pintar el icono) y el MARCADO del correo original al enviar
 * una respuesta o un reenvío desde el webmail, para que el signo aparezca de aquí en adelante.
 */
import { api } from '../api/client';

const FLAG_RESPONDIDO = '\\Answered';
const FLAG_REENVIADO = '$Forwarded';

/** Normaliza una bandera IMAP: sin la barra ni el «$» inicial y en minúsculas. */
function limpia(f: string): string {
  return f.replace(/^[\\$]+/, '').toLowerCase();
}

export function esRespondido(flags?: string[] | null): boolean {
  return !!flags && flags.some((f) => limpia(f) === 'answered');
}

export function esReenviado(flags?: string[] | null): boolean {
  return !!flags && flags.some((f) => limpia(f) === 'forwarded');
}

type RefOriginal = { folder: string; uid: number } | undefined;

/**
 * Pone +FLAGS en el correo ORIGINAL cuando se responde o reenvía desde el webmail, para que la
 * lista muestre ↩/↪ de aquí en adelante. Es una mejora visual: si falla, NUNCA rompe el envío.
 */
export async function marcarOriginalAlEnviar(
  mode: string | null | undefined,
  data: { respuesta_de?: RefOriginal; reenvio_de?: RefOriginal } | undefined | null,
): Promise<void> {
  try {
    if (!data) return;
    let ref: RefOriginal;
    let flag: string;
    if (mode === 'forward') {
      ref = data.reenvio_de;
      flag = FLAG_REENVIADO;
    } else if (mode === 'reply' || mode === 'replyAll') {
      ref = data.respuesta_de;
      flag = FLAG_RESPONDIDO;
    } else {
      return;
    }
    if (!ref || !ref.folder || !ref.uid) return;
    await api.post(`/mail/flags/${encodeURIComponent(ref.folder)}/${ref.uid}`, { flags: flag, add: true });
  } catch {
    /* marcar el original es solo una señal visual: nunca debe afectar al envío */
  }
}
