import { useCallback, useState } from 'react';
import type React from 'react';

/* Arrastrar y soltar elementos del Drive entre el listado y el segundo panel.
   El dato viaja con un tipo propio: así no se confunde con archivos que llegan del
   escritorio ni con texto, y soltar fuera de una zona del Drive no hace nada. */

const TIPO = 'application/x-drive-elemento';

export interface Arrastrado { ruta: string; nombre: string; es_carpeta: boolean; }

export function propsArrastrable(item: Arrastrado, activo: boolean) {
  if (!activo) return {};
  return {
    draggable: true,
    onDragStart: (e: React.DragEvent) => {
      e.dataTransfer.setData(TIPO, JSON.stringify({ ruta: item.ruta, nombre: item.nombre, es_carpeta: item.es_carpeta }));
      e.dataTransfer.effectAllowed = 'move';
    },
  };
}

function leer(e: React.DragEvent): Arrastrado | null {
  try {
    const d = JSON.parse(e.dataTransfer.getData(TIPO) || 'null');
    return d && typeof d.ruta === 'string' && typeof d.nombre === 'string' ? d : null;
  } catch { return null; }
}

/** Zonas donde soltar. `propsDe(carpeta)` se pone en cada carpeta destino (o en el fondo
    del listado, con la carpeta que se está viendo); `resaltada` dice cuál pintar. */
export function useSoltar(alSoltar: (a: Arrastrado, carpeta: string) => void, activo: boolean) {
  const [resaltada, setResaltada] = useState<string | null>(null);

  const propsDe = useCallback((carpeta: string) => {
    if (!activo) return {};
    return {
      onDragOver: (e: React.DragEvent) => {
        if (!e.dataTransfer.types.includes(TIPO)) return;
        e.preventDefault();
        e.stopPropagation();
        e.dataTransfer.dropEffect = 'move';
        setResaltada(carpeta);
      },
      onDragLeave: (e: React.DragEvent) => {
        if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
        setResaltada(r => (r === carpeta ? null : r));
      },
      onDrop: (e: React.DragEvent) => {
        if (!e.dataTransfer.types.includes(TIPO)) return;
        e.preventDefault();
        e.stopPropagation();
        setResaltada(null);
        const a = leer(e);
        if (a) alSoltar(a, carpeta);
      },
    };
  }, [activo, alSoltar]);

  return { resaltada, propsDe };
}

export const CLASE_RESALTADA = 'outline outline-2 outline-[#0078d4] -outline-offset-2 bg-[#deecf9] dark:bg-[#004578]';
