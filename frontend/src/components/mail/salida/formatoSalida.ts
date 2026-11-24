/**
 * formatoSalida.ts — Textos de tiempo para la bandeja de salida (24/11/2026).
 */

/** Antigüedad corta para la fila de la lista: «ahora», «5 min», «3 h», «2 d». */
export function antiguedadCorta(createdAt: number): string {
  const ms = Date.now() - createdAt;
  if (ms < 60_000) return 'ahora';
  const min = Math.floor(ms / 60_000);
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h} h`;
  const d = Math.floor(h / 24);
  return `${d} d`;
}

/** Fecha y hora completas para el panel de lectura. */
export function fechaHoraLarga(createdAt: number): string {
  return new Date(createdAt).toLocaleString('es-EC', { dateStyle: 'full', timeStyle: 'short' });
}
