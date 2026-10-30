// Fecha de vencimiento de una tarea tal como se muestra en la Lista y en la Cuadrícula (como en To Do):
// «Hoy», «Mañana», «Ayer» o la fecha; en rojo si ya venció, en azul si vence hoy y en gris si está completada.
import type { Task } from '../types';
import { COLORS } from '../types';

export const COLOR_VENCIDA = '#d13438';

/** Días desde hoy hasta la fecha (negativo si ya pasó). La fecha llega como «AAAA-MM-DD…». */
function diasHasta(d: string) {
  const fecha = new Date(d.slice(0, 10) + 'T00:00:00');
  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  return Math.round((fecha.getTime() - hoy.getTime()) / 86400000);
}

export function textoVencimiento(d?: string | null) {
  if (!d) return '';
  const dias = diasHasta(d);
  if (dias === 0) return 'Hoy';
  if (dias === 1) return 'Mañana';
  if (dias === -1) return 'Ayer';
  const fecha = new Date(d.slice(0, 10) + 'T00:00:00');
  const otroAnio = fecha.getFullYear() !== new Date().getFullYear();
  return fecha.toLocaleDateString('es-ES', { day: 'numeric', month: 'short', ...(otroAnio ? { year: 'numeric' } : {}) });
}

/** Fecha completa (dd/mm/aaaa) para la ayuda emergente. */
export function fechaCompleta(d?: string | null) {
  if (!d) return '';
  const [a, m, dia] = d.slice(0, 10).split('-');
  return `${dia}/${m}/${a}`;
}

export function colorVencimiento(task: Pick<Task, 'due_date' | 'completed'>, normal: string = COLORS.secondary) {
  if (!task.due_date) return normal;
  if (task.completed) return COLORS.muted;
  const dias = diasHasta(task.due_date);
  if (dias < 0) return COLOR_VENCIDA;
  if (dias === 0) return COLORS.primary;
  return normal;
}
