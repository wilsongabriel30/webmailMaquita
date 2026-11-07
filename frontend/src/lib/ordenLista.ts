/**
 * Orden de la lista de correos (botón ↑↓ de la cabecera, 07/11/2026, como Outlook).
 * Ordena los correos ya cargados; por defecto, por fecha con los más recientes arriba.
 */
import { useEffect, useState } from 'react';
import type { MessageSummary } from '../types';
import { fechaParaOrdenar } from './fechaCorreo';

export type CampoOrden = 'fecha' | 'remitente' | 'asunto' | 'tamano';
export interface Orden { campo: CampoOrden; inverso: boolean }
export const ORDEN_POR_DEFECTO: Orden = { campo: 'fecha', inverso: false };
export const NOMBRES_ORDEN: Record<CampoOrden, string> = {
  fecha: 'Fecha', remitente: 'De', asunto: 'Asunto', tamano: 'Tamaño',
};

const EVENTO = 'orden-lista';
let ordenActual: Orden = ORDEN_POR_DEFECTO;

export function fijarOrden(o: Orden): void {
  ordenActual = o;
  window.dispatchEvent(new CustomEvent(EVENTO));
}

export function useOrdenLista(): Orden {
  const [o, setO] = useState<Orden>(ordenActual);
  useEffect(() => {
    const al = () => setO(ordenActual);
    window.addEventListener(EVENTO, al);
    return () => window.removeEventListener(EVENTO, al);
  }, []);
  return o;
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
