/**
 * Resultados de búsqueda por niveles (13/11/2026).
 *
 * En una búsqueda de varias palabras, de un valor o de una frase, el servidor devuelve primero
 * las coincidencias exactas y después las que solo coinciden en el contenido del correo, y marca
 * cada mensaje con `coincidencia`. Aquí se decide dónde va el rótulo que separa los dos grupos.
 * Si el servidor no informa nada (versión anterior, búsqueda de una sola palabra, lista sin
 * búsqueda), no hay rótulo y la lista queda como siempre.
 */
interface ConCoincidencia { uid: number; coincidencia?: 'exacta' | 'contenido' }

export interface RotuloNiveles {
  /** El rótulo va justo antes de este mensaje. */
  uid: number;
  /** No hay ninguna coincidencia exacta entre lo cargado: el rótulo abre la lista. */
  sinExactas: boolean;
}

export function rotuloDeNiveles(visibles: ConCoincidencia[], cargados: ConCoincidencia[]): RotuloNiveles | null {
  const primero = visibles.findIndex(m => m.coincidencia === 'contenido');
  if (primero < 0) return null;
  // Si detrás vuelve a haber una exacta, la lista ya no está por niveles (otro orden elegido, un
  // correo fijado con chincheta…): un rótulo ahí engañaría.
  if (visibles.slice(primero).some(m => m.coincidencia !== 'contenido')) return null;
  return { uid: visibles[primero].uid, sinExactas: !cargados.some(m => m.coincidencia === 'exacta') };
}
