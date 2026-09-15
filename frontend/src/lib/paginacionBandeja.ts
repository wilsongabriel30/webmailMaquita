// Scroll infinito de la bandeja: qué se pide al servidor y cómo se fusiona lo que llega.
//
// Antes cada tanda volvía a pedir la página 1 con un tamaño mayor (50, 100, 150...), con
// un tope de 6 tandas y el backend limitando a 300: en un buzón de miles de correos la
// lista se cortaba «hacia agosto» y lo anterior parecía no existir. Ahora cada tanda pide
// la página siguiente y se añade al final, sin tope; el refresco periódico solo vuelve a
// pedir la cabecera y conserva lo ya cargado por debajo.

import type { MessageSummary } from '../types';

export const TAMANO_MAXIMO_PETICION = 300; // tope del backend (per_page)

export interface ParametrosTanda { page: number; per_page: number }

/** Parámetros de la petición: siguiente página si se está cargando más; si no, la cabecera. */
export function parametrosDeCarga(
  currentPage: number,
  pageSize: number,
  cargandoMas: boolean,
): ParametrosTanda {
  if (cargandoMas && currentPage > 1) {
    return { page: currentPage, per_page: pageSize };
  }
  return { page: 1, per_page: Math.min(pageSize * Math.max(currentPage, 1), TAMANO_MAXIMO_PETICION) };
}

/** Une lo ya cargado con la tanda recibida, sin repetir UIDs. */
export function fusionarTanda(
  existentes: MessageSummary[],
  recibidos: MessageSummary[],
  parametros: ParametrosTanda,
): MessageSummary[] {
  const ids = new Set(recibidos.map((m) => m.uid));
  if (parametros.page > 1) {
    // Tanda siguiente: va al final, sin repetir lo que ya estaba.
    const vistos = new Set(existentes.map((m) => m.uid));
    return [...existentes, ...recibidos.filter((m) => !vistos.has(m.uid))];
  }
  // Cabecera refrescada: reemplaza la parte ya cubierta y conserva el resto por debajo.
  const cubiertos = Math.min(existentes.length, recibidos.length);
  const cola = existentes.slice(cubiertos).filter((m) => !ids.has(m.uid));
  return [...recibidos, ...cola];
}
