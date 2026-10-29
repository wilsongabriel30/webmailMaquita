// Los cinco órdenes de Tareas (como en To Do). Las completadas siempre van al final.
// En una lista el orden elegido se guarda en la lista (lo ven todas sus personas);
// en las listas inteligentes, en este navegador.
import type { Orden, Task } from '../types';

export const ORDENES: { value: Orden; label: string }[] = [
  { value: 'manual', label: 'Orden personalizado (arrastrar)' },
  { value: 'date', label: 'Fecha de vencimiento' },
  { value: 'important', label: 'Importancia' },
  { value: 'alpha', label: 'Alfabéticamente' },
  { value: 'created', label: 'Fecha de creación' },
];

const comparar: Record<Orden, (a: Task, b: Task) => number> = {
  manual: (a, b) => (a.position ?? 0) - (b.position ?? 0),
  date: (a, b) => {
    if (a.due_date && b.due_date) return a.due_date.localeCompare(b.due_date);
    return a.due_date ? -1 : b.due_date ? 1 : 0;
  },
  important: (a, b) => (b.important ? 1 : 0) - (a.important ? 1 : 0) || (a.position ?? 0) - (b.position ?? 0),
  alpha: (a, b) => a.title.localeCompare(b.title, 'es', { sensitivity: 'base' }),
  created: (a, b) => (b.created_at || '').localeCompare(a.created_at || ''),
};

/** `importantesArriba` (⚙ «Mover las tareas con estrella arriba», F6): las importantes primero entre las pendientes. */
export function ordenarTareas(tareas: Task[], orden: Orden, importantesArriba = false): Task[] {
  const f = comparar[orden] ?? comparar.manual;
  return [...tareas].sort((a, b) => {
    if (a.completed !== b.completed) return a.completed ? 1 : -1;
    if (importantesArriba && !a.completed && a.important !== b.important) return a.important ? -1 : 1;
    return f(a, b);
  });
}

const CLAVE = (vista: string) => `tareas-orden-${vista}`;

export function leerOrdenVista(vista: string): Orden {
  try {
    const v = localStorage.getItem(CLAVE(vista));
    return ORDENES.some(o => o.value === v) ? (v as Orden) : 'date';
  } catch { return 'date'; }
}

export function guardarOrdenVista(vista: string, orden: Orden) {
  try { localStorage.setItem(CLAVE(vista), orden); } catch { /* sin almacenamiento: solo dura esta sesión */ }
}
