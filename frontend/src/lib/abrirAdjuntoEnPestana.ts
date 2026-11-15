/**
 * Abre un adjunto en una pestaña aparte del navegador (13/11/2026).
 *
 * Pedido del personal: la vista previa dentro del correo sirve para echar un vistazo, pero quien
 * trabaja con varios documentos a la vez los quiere cada uno en su pestaña. Solo se ofrece para lo
 * que el navegador muestra por sí mismo y sin riesgo: PDF, imágenes y texto. Nunca HTML ni SVG:
 * abiertos así se ejecutarían con los permisos del correo.
 *
 * La pestaña se abre en el mismo clic (si se abriera después de descargar, el navegador la
 * bloquearía como ventana emergente) y se llena cuando termina la descarga.
 */
import { esClienteEscritorio } from './clienteEscritorio';

const TIPOS: Record<string, string> = {
  pdf: 'application/pdf',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  gif: 'image/gif',
  webp: 'image/webp',
  bmp: 'image/bmp',
  txt: 'text/plain;charset=utf-8',
};

function tipoDe(nombre: string): string | undefined {
  return TIPOS[(nombre.split('.').pop() || '').toLowerCase()];
}

export function seAbreEnPestana(nombre: string): boolean {
  return !!tipoDe(nombre);
}

function escribirAviso(pestana: Window, nombre: string, texto: string): void {
  try {
    pestana.document.title = nombre;
    pestana.document.body.style.cssText = 'font-family:Segoe UI,Arial,sans-serif;color:#323130;padding:24px';
    pestana.document.body.textContent = texto;
  } catch {
    /* la pestaña ya navegó o el navegador no deja escribir en ella */
  }
}

/** Dirección que sirve el adjunto para verlo (no para descargarlo), a partir de la de descarga. */
export function urlDeVista(urlDescarga: string): string {
  return urlDescarga.replace('/api/mail/attachment/', '/api/mail/preview/');
}

/** Dentro de la aplicación de escritorio se abre una ventana propia; en el navegador, una pestaña. */
export function rotuloAparte(): string {
  return esClienteEscritorio() ? 'ventana nueva' : 'pestaña nueva';
}

/** Devuelve false si el navegador no dejó abrir la pestaña o la descarga falló. */
export async function abrirAdjuntoEnPestana(url: string, nombre: string): Promise<boolean> {
  const tipo = tipoDe(nombre);
  if (!tipo) return false;
  // Aplicación de escritorio (13/11/2026): abre sus propias ventanas emergentes, y ahí el documento
  // se ve como si estuviera abierto en el equipo. Necesita una dirección real del servidor (la de
  // vista, que lo sirve para mostrarse), no una copia en memoria de esta página.
  if (esClienteEscritorio()) {
    const ancho = Math.min(1200, Math.max(700, Math.round(window.screen.availWidth * 0.7)));
    const alto = Math.min(1000, Math.max(600, Math.round(window.screen.availHeight * 0.9)));
    return !!window.open(urlDeVista(url), '_blank', `popup=yes,width=${ancho},height=${alto},resizable=yes,scrollbars=yes`);
  }
  const pestana = window.open('', '_blank');
  if (!pestana) return false;
  escribirAviso(pestana, nombre, `Abriendo «${nombre}»…`);
  try {
    const res = await fetch(url, { credentials: 'include' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const datos = await res.blob();
    const enlace = URL.createObjectURL(new Blob([datos], { type: tipo }));
    pestana.location.replace(enlace);
    return true;
  } catch {
    escribirAviso(pestana, nombre, `No se pudo abrir «${nombre}». Cierre esta pestaña e inténtelo de nuevo desde el correo.`);
    return false;
  }
}
