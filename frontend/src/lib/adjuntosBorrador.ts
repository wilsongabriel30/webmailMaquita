/**
 * Adjuntos en borradores y archivos que no se aceptan.
 *
 * - Un borrador guarda también sus archivos; al reabrirlo se descargan del servidor y
 *   vuelven al redactor como si se acabaran de adjuntar.
 * - Los tipos peligrosos (ejecutables, scripts, .dat, imágenes de disco) se rechazan
 *   al adjuntar, con aviso. El servidor aplica la misma lista al guardar y al enviar.
 */
import type { AttachmentInfo } from '../types';

export interface ArchivoAdjunto { name: string; size: number; type: string; file?: File; }

export const EXTENSIONES_PELIGROSAS = new Set([
  'exe', 'dll', 'com', 'scr', 'pif', 'msi', 'msp', 'cpl', 'sys', 'drv',
  'bat', 'cmd', 'ps1', 'psm1', 'vbs', 'vbe', 'js', 'jse', 'wsf', 'wsh', 'hta',
  'jar', 'reg', 'lnk', 'sh', 'app', 'apk', 'gadget', 'inf', 'scf', 'url',
  'iso', 'img', 'vhd', 'vhdx', 'dat',
]);

export function extensionDe(nombre: string): string {
  const limpio = (nombre || '').trim().toLowerCase().replace(/[. ]+$/, '');
  return limpio.includes('.') ? limpio.slice(limpio.lastIndexOf('.') + 1) : '';
}

export function esPeligroso(nombre: string): boolean {
  return EXTENSIONES_PELIGROSAS.has(extensionDe(nombre));
}

/** Separa los archivos permitidos de los rechazados y arma el texto del aviso. */
export function filtrarPeligrosos(files: File[]): { permitidos: File[]; aviso: string } {
  const permitidos: File[] = [];
  const rechazados: string[] = [];
  for (const f of files) {
    if (esPeligroso(f.name)) rechazados.push(f.name);
    else permitidos.push(f);
  }
  const aviso = rechazados.length
    ? `No se puede adjuntar ${rechazados.map(n => `«${n}»`).join(', ')}: tipo de archivo bloqueado por seguridad. Comprímelo en .zip con contraseña si de verdad hay que enviarlo.`
    : '';
  return { permitidos, aviso };
}

/** Descarga los adjuntos de un borrador guardado y los devuelve como archivos del redactor. */
export function cargarAdjuntosDelBorrador(uid: number, adjuntos: AttachmentInfo[]): Promise<ArchivoAdjunto[]> {
  return cargarAdjuntosDeMensaje('Drafts', uid, adjuntos);
}

/**
 * Adjuntos del correo que se reenvía: vuelven al redactor para que la persona los vea,
 * pueda quitar alguno y salgan con el reenvío. Si no se conoce la lista (menú contextual
 * de la bandeja), se pide el mensaje al servidor.
 */
export async function cargarAdjuntosDelReenvio(origen: { folder: string; uid: number; adjuntos?: AttachmentInfo[] }): Promise<ArchivoAdjunto[]> {
  let adjuntos = origen.adjuntos;
  if (!adjuntos) {
    try {
      const res = await fetch('/api/mail/message/' + encodeURIComponent(origen.folder) + '/' + origen.uid, { credentials: 'include' });
      if (!res.ok) return [];
      adjuntos = ((await res.json()) as { attachments?: AttachmentInfo[] }).attachments || [];
    } catch { return []; }
  }
  return cargarAdjuntosDeMensaje(origen.folder, origen.uid, adjuntos);
}

async function cargarAdjuntosDeMensaje(folder: string, uid: number, adjuntos: AttachmentInfo[]): Promise<ArchivoAdjunto[]> {
  const resultado: ArchivoAdjunto[] = [];
  for (const a of adjuntos || []) {
    if (a.is_inline || !a.filename) continue;
    try {
      const url = '/api/mail/attachment/' + encodeURIComponent(folder) + '/' + uid + '/' + a.part_number + '/' + encodeURIComponent(a.filename);
      const res = await fetch(url, { credentials: 'include' });
      if (!res.ok) continue;
      const blob = await res.blob();
      const file = new File([blob], a.filename, { type: a.content_type || blob.type || 'application/octet-stream' });
      resultado.push({ name: file.name, size: file.size, type: file.type, file });
    } catch { /* si uno falla, se conservan los demás */ }
  }
  return resultado;
}

/** Huella de la lista de adjuntos: si no cambia, el guardado pide conservar los del servidor. */
export function huellaAdjuntos(lista: ArchivoAdjunto[]): string {
  return lista.map(a => `${a.name}|${a.size}`).join('\n');
}
