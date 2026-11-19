/**
 * Abrir un correo en una pestaña nueva del navegador.
 *
 * La pestaña carga la ruta /mensaje (ver components/mail/MensajeEnPestana.tsx), que muestra
 * SOLO ese correo. La bandeja de la pestaña original no cambia: no se selecciona el mensaje,
 * no se marca como leído desde aquí ni se mueve la lista.
 */

import { cuentaActiva } from './cuentaActiva';

/** Ruta pública de un correo para abrirlo solo, con la base del webmail (/webmail/).
 *  Lleva la CUENTA ACTIVA de esta pestaña en la URL (?cuenta=): la ventana nueva se abre en un
 *  contexto propio (y con noopener) donde el sessionStorage no se hereda; sin esto, cuentaActiva()
 *  salía null, la cabecera X-Cuenta-Activa iba como «propia» y el servidor resolvía el uid contra
 *  la cuenta primaria, mostrando el correo de OTRA cuenta (bug multi-cuenta, 19/11/2026). Al
 *  arrancar, instalarCuentaActiva() consume ?cuenta= y fija la cabecera y la cookie correctas. */
export function urlMensajeEnPestana(folder: string, uid: number): string {
  const base = (import.meta.env.BASE_URL || '/').replace(/\/?$/, '/');
  const cuenta = cuentaActiva();
  const extra = cuenta ? `&cuenta=${encodeURIComponent(cuenta)}` : '';
  return `${base}mensaje?folder=${encodeURIComponent(folder)}&uid=${encodeURIComponent(String(uid))}${extra}`;
}

export function abrirMensajeEnPestana(folder: string, uid: number): void {
  // noopener: la pestaña nueva no puede tocar la original.
  window.open(urlMensajeEnPestana(folder, uid), '_blank', 'noopener,noreferrer');
}

/** Doble clic en la lista (07/11/2026, como Outlook): el correo se abre en una ventana emergente
 *  propia, del tamaño de un correo, con la misma página /mensaje. Si el navegador bloquea la
 *  ventana emergente, queda en una pestaña nueva. */
export function abrirMensajeEnVentana(folder: string, uid: number): void {
  const ancho = Math.min(1000, window.screen.availWidth - 40);
  const alto = Math.min(860, window.screen.availHeight - 60);
  const izq = Math.max(0, Math.round((window.screen.availWidth - ancho) / 2));
  const arriba = Math.max(0, Math.round((window.screen.availHeight - alto) / 2));
  window.open(urlMensajeEnPestana(folder, uid), '_blank',
    `popup=yes,width=${ancho},height=${alto},left=${izq},top=${arriba},noopener,noreferrer`);
}
