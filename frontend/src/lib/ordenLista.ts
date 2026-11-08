/**
 * Orden de la lista de correos (botón «Por fecha ▾» de la cabecera, 07/11/2026, como Outlook).
 * Ordena los correos ya cargados; por defecto, por fecha con los más recientes arriba.
 * Se recuerda POR CARPETA en este navegador (revisión 07/11/2026).
 */
import { useMemo, useSyncExternalStore } from 'react';
import type { MessageSummary } from '../types';
import { fechaParaOrdenar } from './fechaCorreo';

export type CampoOrden = 'fecha' | 'remitente' | 'asunto' | 'tamano';
export interface Orden { campo: CampoOrden; inverso: boolean }
export const ORDEN_POR_DEFECTO: Orden = { campo: 'fecha', inverso: false };
export const NOMBRES_ORDEN: Record<CampoOrden, string> = {
  fecha: 'Fecha', remitente: 'De', asunto: 'Asunto', tamano: 'Tamaño',
};

const CLAVE = 'webmail.ordenLista';
const EVENTO = 'orden-lista';

function leerTodos(): Record<string, Orden> {
  try {
    const v = JSON.parse(localStorage.getItem(CLAVE) || '{}');
    return v && typeof v === 'object' ? v : {};
  } catch { return {}; }
}

export function leerOrden(carpeta: string): Orden {
  const o = leerTodos()[carpeta];
  if (!o || !(o.campo in NOMBRES_ORDEN)) return ORDEN_POR_DEFECTO;
  return { campo: o.campo, inverso: !!o.inverso };
}

export function fijarOrden(carpeta: string, o: Orden): void {
  const todos = leerTodos();
  if (o.campo === ORDEN_POR_DEFECTO.campo && !o.inverso) delete todos[carpeta];
  else todos[carpeta] = o;
  try { localStorage.setItem(CLAVE, JSON.stringify(todos)); } catch { /* sin almacenamiento: no se recuerda */ }
  window.dispatchEvent(new CustomEvent(EVENTO));
}

function suscribir(cb: () => void) {
  window.addEventListener(EVENTO, cb);
  return () => window.removeEventListener(EVENTO, cb);
}
function instantanea(): string {
  try { return localStorage.getItem(CLAVE) || ''; } catch { return ''; }
}

export function useOrdenLista(carpeta: string): Orden {
  const crudo = useSyncExternalStore(suscribir, instantanea, () => '');
  // eslint-disable-next-line react-hooks/exhaustive-deps
  return useMemo(() => leerOrden(carpeta), [carpeta, crudo]);
}

/** Texto del botón de la cabecera: «Por fecha», «Por asunto»… */
export function textoOrden(o: Orden): string {
  return `Por ${NOMBRES_ORDEN[o.campo].toLowerCase()}`;
}

function nombreDe(from: string): string {
  return (from || '').replace(/<[^>]*>/g, '').replace(/"/g, '').trim().toLowerCase();
}
function asuntoLimpio(s: string): string {
  return (s || '').replace(/^\s*((re|rv|fw|fwd|reenviar|resp)\s*:\s*)+/i, '').trim().toLowerCase();
}

/** Ordena en el sitio. Fecha y tamaño: mayor primero; De y Asunto: de la A a la Z. */
export function ordenarCorreos(lista: MessageSummary[], o: Orden): void {
  if (o.campo === 'fecha' && !o.inverso) return; // ya viene así del servidor
  const cmp: Record<CampoOrden, (a: MessageSummary, b: MessageSummary) => number> = {
    fecha: (a, b) => fechaParaOrdenar(b) - fechaParaOrdenar(a),
    remitente: (a, b) => nombreDe(a.from).localeCompare(nombreDe(b.from), 'es'),
    asunto: (a, b) => asuntoLimpio(a.subject).localeCompare(asuntoLimpio(b.subject), 'es'),
    tamano: (a, b) => (b.size || 0) - (a.size || 0),
  };
  const f = cmp[o.campo];
  lista.sort(o.inverso ? (a, b) => f(b, a) : f);
}
