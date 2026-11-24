/**
 * carpetaSalida.ts — La «Bandeja de salida» como una carpeta virtual del riel (24/11/2026).
 *
 * Antes la bandeja de salida se abría como una ventana emergente que tapaba el correo. Ahora es
 * una carpeta más: se navega a ella con `setCurrentFolder(CARPETA_SALIDA)` y `MailView` muestra la
 * lista en el panel central y el correo en cola en el panel de lectura, como cualquier carpeta.
 *
 * No es una carpeta del servidor (la cola vive en el equipo, en IndexedDB): este identificador
 * nunca se manda al IMAP. `MailView` lo intercepta antes de pedir mensajes al servidor.
 */
export const CARPETA_SALIDA = 'Virtual.BandejaSalida';

/** ¿La carpeta abierta es la bandeja de salida? */
export function esCarpetaSalida(folder: string | null | undefined): boolean {
  return folder === CARPETA_SALIDA;
}
