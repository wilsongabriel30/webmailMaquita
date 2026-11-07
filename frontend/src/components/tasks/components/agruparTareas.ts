// «Grupo» de la cabecera (como en Outlook, F6): agrupar las pendientes por lista, fecha de vencimiento o categoría.
// La elección se guarda por vista en este navegador. «Planeado» agrupa por fecha si no se eligió otra cosa.
import type { Task } from '../types';
import { agruparPlaneado, diaDeTarea, type GrupoTareas } from './agruparPlaneado';
import { CATEGORIAS } from './categorias';

export type Agrupacion = 'ninguno' | 'lista' | 'fecha' | 'categoria';

export const AGRUPACIONES: { valor: Agrupacion; etiqueta: string }[] = [
  { valor: 'ninguno', etiqueta: 'Sin agrupar' },
  { valor: 'lista', etiqueta: 'Lista' },
  { valor: 'fecha', etiqueta: 'Fecha de vencimiento' },
  { valor: 'categoria', etiqueta: 'Categoría' },
];

const CLAVE = (vista: string) => `tareas-grupo-${vista}`;

export function leerAgrupacion(vista: string): Agrupacion {
  try {
    const v = localStorage.getItem(CLAVE(vista));
    if (AGRUPACIONES.some(a => a.valor === v)) return v as Agrupacion;
  } catch { /* sin almacenamiento: se usa el valor por defecto */ }
  return vista === 'planned' ? 'fecha' : 'ninguno';
}

export function guardarAgrupacion(vista: string, a: Agrupacion) {
  try { localStorage.setItem(CLAVE(vista), a); } catch { /* solo dura esta sesión */ }
}

function porClave(tareas: Task[], claves: (t: Task) => string[], orden: string[], sinClave: string): GrupoTareas[] {
  const grupos = new Map<string, Task[]>();
  for (const t of tareas) {
    const ks = claves(t);
    for (const k of ks.length ? ks : [sinClave]) grupos.set(k, [...(grupos.get(k) || []), t]);
  }
  const nombres = [...grupos.keys()].sort((a, b) => {
    const ia = orden.indexOf(a), ib = orden.indexOf(b);
    if (a === sinClave || b === sinClave) return a === sinClave ? 1 : -1;
    if (ia >= 0 || ib >= 0) return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    return a.localeCompare(b, 'es');
  });
  return nombres.map(n => ({ clave: n, label: n, tasks: grupos.get(n)! }));
}

export function agruparTareas(pendientes: Task[], a: Agrupacion): GrupoTareas[] {
  if (a === 'fecha') {
    const sinFecha = pendientes.filter(t => !diaDeTarea(t));
    const grupos = agruparPlaneado(pendientes);
    return sinFecha.length ? [...grupos, { clave: 'sin-fecha', label: 'Sin fecha', tasks: sinFecha }] : grupos;
  }
  if (a === 'lista') return porClave(pendientes, t => (t.list_name ? [t.list_name] : []), ['Tareas'], 'Sin lista');
  if (a === 'categoria') {
    return porClave(pendientes, t => t.labels || [], CATEGORIAS.map(c => c.nombre), 'Sin categoría');
  }
  return [{ clave: 'todas', label: '', tasks: pendientes }];
}
