/**
 * Origen de un correo adjuntado como .eml (09/11/2026).
 *
 * Cuando un correo del buzón entra al redactor como adjunto («Reenviar como adjunto», arrastre
 * desde la lista o el selector «Correo como adjunto»), se guarda junto al archivo de dónde salió.
 * Así la lista de adjuntos puede mostrar el asunto legible en vez del nombre crudo y el botón «Ver»
 * puede abrir el correo original en su propia ventana antes de enviar.
 */
/** Tipo MIME de un correo adjunto. */
export const TIPO_EML = 'message/rfc822';

export interface OrigenCorreoAdjunto {
  folder: string;
  uid: number;
  subject: string;
  from?: string;
  date?: string | null;
}

interface AdjuntoBasico { name: string; type: string; correo?: OrigenCorreoAdjunto }

/** Un adjunto es un correo si trae origen, si es message/rfc822 o si el nombre termina en .eml. */
export function esAdjuntoCorreo(adj: AdjuntoBasico): boolean {
  return !!adj.correo || adj.type === TIPO_EML || /\.eml$/i.test(adj.name || '');
}

/** Asunto legible de un adjunto de correo: el del origen o el nombre sin «.eml». */
export function asuntoDeAdjuntoCorreo(adj: AdjuntoBasico): string {
  const asunto = adj.correo?.subject?.trim() || (adj.name || '').replace(/\.eml$/i, '').trim();
  return asunto || '(sin asunto)';
}
