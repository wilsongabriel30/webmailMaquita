// Arrastrar una tarea fuera de la lista: a otra lista de la barra (la mueve), a «Mi día» o a «Importante».
// Va con un tipo propio en dataTransfer para no confundirse con el arrastre de listas y grupos de la barra.
import type { DragEvent } from 'react';

const TIPO = 'application/x-maquita-tarea';

export function marcarTarea(e: DragEvent, id: string) {
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData(TIPO, id);
  e.dataTransfer.setData('text/plain', id);
}

/** Durante dragover no se puede leer el dato, pero sí su tipo. */
export function esTarea(e: DragEvent): boolean {
  return Array.from(e.dataTransfer.types || []).includes(TIPO);
}

export function idTarea(e: DragEvent): string {
  return e.dataTransfer.getData(TIPO);
}
