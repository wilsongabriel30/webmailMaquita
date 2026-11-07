/**
 * Gracia de «No leídos»: el correo que se acaba de abrir sigue visible un rato en el filtro.
 *
 * Pedido muy común (05/11/2026): en la pestaña «No leídos» se abre un correo, pasa a leído y
 * desaparece del listado al instante; la persona ya no puede volver a marcarlo como no leído
 * desde ahí. Ahora, durante `GRACIA_MS` (o hasta recargar la página), el correo abierto se
 * conserva en el listado aunque el servidor ya no lo devuelva como no leído.
 */

import type { MessageSummary } from '../../types';

export const GRACIA_MS = 40_000;

const leidosRecientes = new Map<string, number>();

const clave = (carpeta: string, uid: number) => `${carpeta}:${uid}`;

/** Se llama al abrir un correo (cuando pasa de no leído a leído). */
export function recordarLeido(carpeta: string, uid: number, ahora: number = Date.now()): void {
  leidosRecientes.set(clave(carpeta, uid), ahora);
  // Limpieza de entradas vencidas para que el mapa no crezca.
  for (const [k, t] of leidosRecientes) if (ahora - t > GRACIA_MS) leidosRecientes.delete(k);
}

/** Al marcar «no leído» a mano ya no hace falta la gracia. */
export function olvidarLeido(carpeta: string, uid: number): void {
  leidosRecientes.delete(clave(carpeta, uid));
}

/**
 * Devuelve `nuevos` más los correos de `previos` que se leyeron hace menos de `GRACIA_MS`
 * y el servidor ya no incluye, cada uno en la posición que tenía.
 */
export function conservarLeidosRecientes(
  previos: MessageSummary[],
  nuevos: MessageSummary[],
  carpeta: string,
  ahora: number = Date.now(),
): MessageSummary[] {
  if (leidosRecientes.size === 0 || previos.length === 0) return nuevos;
  const enNuevos = new Set(nuevos.map((m) => m.uid));
  const conservar: Array<{ indice: number; msg: MessageSummary }> = [];
  previos.forEach((m, indice) => {
    if (enNuevos.has(m.uid)) return;
    const t = leidosRecientes.get(clave(carpeta, m.uid));
    if (t !== undefined && ahora - t <= GRACIA_MS) conservar.push({ indice, msg: { ...m, seen: true } });
  });
  if (conservar.length === 0) return nuevos;
  const resultado = [...nuevos];
  for (const { indice, msg } of conservar) resultado.splice(Math.min(indice, resultado.length), 0, msg);
  return resultado;
}
