/**
 * quienMostrar.ts — A quién se muestra en cada fila de la lista (05/11/2026).
 * En Bandeja de entrada y demás carpetas la fila dice DE QUIÉN viene el correo; en Enviados y
 * Borradores (como Outlook) dice A QUIÉN se envió. Pedido de Gissela Jaya: «cuando vea los
 * enviados quiero que se vea a quién envié y con qué asunto».
 */
import type { Folder } from '../../types';

const NOMBRES_SALIDA = /^(sent|sent items|sent messages|drafts|outbox|enviados|elementos enviados|borradores|bandeja de salida)$/;

export function esCarpetaDeSalida(nombre: string, folders: Folder[]): boolean {
  const f = folders.find(x => x.name === nombre);
  if (f && (f.type === 'sent' || f.type === 'drafts')) return true;
  // Subcarpetas de Enviados/Borradores (p. ej. «Sent/2025», «Sent.Clientes», 05/11/2026, reporte de
  // Gissela Jaya): si alguna carpeta antecesora es de salida, esta también lo es.
  const antecesoras = folders.filter(x => (x.type === 'sent' || x.type === 'drafts') && x.name !== nombre);
  if (antecesoras.some(a => nombre.startsWith(a.name + '/') || nombre.startsWith(a.name + '.'))) return true;
  if (f) return false;
  const n = (nombre || '').toLowerCase();
  const ultimo = n.split(/[/.]/).pop() || n;
  return NOMBRES_SALIDA.test(n) || NOMBRES_SALIDA.test(ultimo);
}

/** Separa «Ana <a@x>, "Pérez, Luis" <l@x>» respetando las comillas. */
export function destinatarios(to: string | null | undefined): string[] {
  if (!to) return [];
  const out: string[] = [];
  let actual = '';
  let entreComillas = false;
  for (const c of to) {
    if (c === '"') entreComillas = !entreComillas;
    if (c === ',' && !entreComillas) { if (actual.trim()) out.push(actual.trim()); actual = ''; continue; }
    actual += c;
  }
  if (actual.trim()) out.push(actual.trim());
  return out;
}

/** Dirección (con nombre si lo trae) que debe encabezar la fila, y cuántos destinatarios más hay. */
export function quienMostrar(
  msg: { from?: string | null; to?: string | null; folder?: string | null },
  carpetaActual: string,
  folders: Folder[],
): { quien: string; otros: number } {
  if (!esCarpetaDeSalida(msg.folder || carpetaActual, folders)) return { quien: msg.from || '', otros: 0 };
  const lista = destinatarios(msg.to);
  if (lista.length === 0) return { quien: msg.from || '', otros: 0 };
  return { quien: lista[0], otros: lista.length - 1 };
}
