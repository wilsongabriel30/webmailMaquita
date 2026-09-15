// Varias cuentas en una sesión: las carpetas de una cuenta delegada llevan un nombre virtual
//   Compartidos/<cuenta>/<carpeta real>
// que el backend traduce al buzón real abierto con el usuario maestro (services/cuentas_delegadas.py).

import { SYSTEM_FOLDER_LABELS } from '../folders';

// Separador «,»: no «/» (la API lleva la carpeta como un solo segmento de ruta) ni «.» (jerarquía IMAP).
export const PREFIJO_COMPARTIDOS = 'Compartidos,';
const SEP = ',';

export interface Cuenta {
  email: string;
  nombre: string;
  propia: boolean;
  puede_enviar: boolean;
}

/** 'Compartidos/ventas@x.com/INBOX' -> 'ventas@x.com'; carpeta propia -> null */
export function cuentaDeCarpeta(folder: string | null | undefined): string | null {
  if (!folder || !folder.startsWith(PREFIJO_COMPARTIDOS)) return null;
  const resto = folder.slice(PREFIJO_COMPARTIDOS.length);
  const cuenta = resto.split(SEP)[0] || '';
  return cuenta.includes('@') ? cuenta.toLowerCase() : null;
}

/** 'Compartidos,ventas@x.com,Sent' -> 'Sent'; carpeta propia -> tal cual */
export function carpetaReal(folder: string): string {
  if (!cuentaDeCarpeta(folder)) return folder;
  const resto = folder.slice(PREFIJO_COMPARTIDOS.length);
  const i = resto.indexOf(SEP);
  return i < 0 ? 'INBOX' : resto.slice(i + 1) || 'INBOX';
}

export function carpetaVirtual(cuenta: string, real: string): string {
  return `${PREFIJO_COMPARTIDOS}${cuenta}${SEP}${real}`;
}

/** Etiqueta corta de una carpeta (propia o de cuenta delegada). */
export function etiquetaCarpeta(folder: string): string {
  const real = carpetaReal(folder);
  if (SYSTEM_FOLDER_LABELS[real]) return SYSTEM_FOLDER_LABELS[real];
  return real.includes('.') ? real.split('.').pop() || real : real;
}
