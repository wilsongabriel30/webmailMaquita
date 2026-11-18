/**
 * colaSalidaLegible.ts — Qué hacer con un correo de la cola de salida que no puede salir (18/11/2026).
 *
 * Caso real: un correo llevaba cinco días en la bandeja de salida. Lo guardado en el equipo va
 * cifrado; si su contenido ya no se puede abrir (cambió la llave del equipo), el registro llega sin
 * destinatarios ni asunto. La cola lo mandaba así, el servidor respondía «Solicitud inválida» y la
 * persona no podía ni abrirlo ni saber qué pasaba.
 *
 * Aquí está lo que no depende del navegador: reconocer ese registro y convertir uno legible en
 * los datos de una redacción, para «Editar y reenviar».
 */
import type { OutboxEmail } from './offlineStore';
import type { ComposeData } from '../types';

export const TEXTO_ILEGIBLE =
  'Este equipo ya no puede leer este correo guardado. No se envió. Búsquelo en Borradores y envíelo desde ahí; después descártelo de aquí.';

/** ¿El contenido no se pudo abrir? Sin destinatarios no hay nada que enviar. */
export function esIlegible(e: Partial<OutboxEmail> & { sobre?: unknown }): boolean {
  if (e.sobre !== undefined && e.sobre !== null) return true;
  return !Array.isArray(e.to) || e.to.filter((d) => typeof d === 'string' && d.trim()).length === 0;
}

/** Los datos del correo en cola, como los espera el redactor. */
export function aRedaccion(e: OutboxEmail): ComposeData {
  return {
    to: e.to || [], cc: e.cc?.length ? e.cc : undefined, bcc: e.bcc?.length ? e.bcc : undefined,
    subject: e.subject || '', html_body: e.html_body || '', text_body: e.text_body || '',
    in_reply_to: e.in_reply_to || undefined, references: e.references || undefined,
    draft_uid: e.draft_uid ?? undefined,
  };
}

/** Los adjuntos en cola (base64) como archivos, para que la redacción reabierta los conserve. */
export function archivosDe(e: OutboxEmail): { file: File }[] {
  const salida: { file: File }[] = [];
  for (const a of e.attachments || []) {
    try {
      const binario = atob(a.content_b64 || '');
      const bytes = new Uint8Array(binario.length);
      for (let i = 0; i < binario.length; i++) bytes[i] = binario.charCodeAt(i);
      salida.push({ file: new File([bytes], a.filename || 'adjunto', { type: a.content_type || 'application/octet-stream' }) });
    } catch { /* un adjunto dañado no impide recuperar el resto del correo */ }
  }
  return salida;
}

/** Aviso corto para la persona cuando el servidor rechaza un correo de la cola. */
export function avisoDeRechazo(asunto: string | undefined, motivo: string | undefined): string {
  const titulo = (asunto || '').trim() || '(sin asunto)';
  const causa = (motivo || '').trim().replace(/\.$/, '');
  return `No se pudo enviar «${titulo.slice(0, 80)}»${causa ? `: ${causa}` : ''}. Está en la Bandeja de salida.`;
}
