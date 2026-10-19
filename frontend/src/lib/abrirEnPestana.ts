/**
 * Abrir un correo en una pestaña nueva del navegador.
 *
 * La pestaña carga la ruta /mensaje (ver components/mail/MensajeEnPestana.tsx), que muestra
 * SOLO ese correo. La bandeja de la pestaña original no cambia: no se selecciona el mensaje,
 * no se marca como leído desde aquí ni se mueve la lista.
 */

/** Ruta pública de un correo para abrirlo solo, con la base del webmail (/webmail/). */
export function urlMensajeEnPestana(folder: string, uid: number): string {
  const base = (import.meta.env.BASE_URL || '/').replace(/\/?$/, '/');
  return `${base}mensaje?folder=${encodeURIComponent(folder)}&uid=${encodeURIComponent(String(uid))}`;
}

export function abrirMensajeEnPestana(folder: string, uid: number): void {
  // noopener: la pestaña nueva no puede tocar la original.
  window.open(urlMensajeEnPestana(folder, uid), '_blank', 'noopener,noreferrer');
}
