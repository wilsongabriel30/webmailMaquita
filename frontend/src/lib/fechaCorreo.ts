import type { Folder } from '../types';

/**
 * Qué fecha se muestra de un correo (13/10/2026).
 *
 * `date` es la cabecera Date: la escribe el programa del remitente (Outlook, el celular…)
 * con el reloj de SU equipo. Basta cambiar la hora de Windows para que un correo diga que
 * se envió cuando uno quiera. `received_date` es la hora en que llegó a NUESTRO servidor
 * (INTERNALDATE, la pone Dovecot al entregarlo): esa no la controla el remitente.
 *
 * En Enviados y Borradores no se usa: ahí la «llegada» la fija el propio programa que guarda
 * la copia, así que no es más fiable que la fecha del correo.
 */

interface ConFechas {
  folder: string;
  date: string | null;
  received_date?: string | null;
}

/** Diferencias normales entre la hora que pone el remitente y la de llegada: colas, reintentos. */
const ATRASO_TOLERADO_MS = 60 * 60 * 1000;
/** Un correo no puede llegar antes de enviarse: más de unos minutos «en el futuro» es un reloj mal puesto. */
const ADELANTO_TOLERADO_MS = 5 * 60 * 1000;

function esCopiaPropia(folder: string, folders: Folder[]): boolean {
  const tipo = folders.find(f => f.name === folder)?.type;
  return tipo === 'sent' || tipo === 'drafts';
}

/** Fecha a mostrar: la de llegada al servidor si es confiable; si no, la del correo. */
export function fechaMostrada(msg: ConFechas, folders: Folder[]): string | null {
  if (msg.received_date && !esCopiaPropia(msg.folder, folders)) return msg.received_date;
  return msg.date;
}

/** Para ordenar: llegada al servidor y, si no la hay, la fecha del correo. */
export function fechaParaOrdenar(msg: ConFechas): number {
  const f = msg.received_date || msg.date;
  return f ? new Date(f).getTime() : 0;
}

/**
 * Si la fecha que puso el remitente no cuadra con la llegada al servidor, devuelve ambas
 * para avisar. null cuando cuadra, falta alguna o es una copia propia (Enviados, Borradores).
 */
export function fechasQueNoCuadran(
  msg: ConFechas,
  folders: Folder[],
): { remitente: Date; llegada: Date } | null {
  if (!msg.date || !msg.received_date || esCopiaPropia(msg.folder, folders)) return null;
  const remitente = new Date(msg.date);
  const llegada = new Date(msg.received_date);
  if (isNaN(remitente.getTime()) || isNaN(llegada.getTime())) return null;
  const atraso = llegada.getTime() - remitente.getTime();
  if (atraso > ATRASO_TOLERADO_MS || -atraso > ADELANTO_TOLERADO_MS) return { remitente, llegada };
  return null;
}
