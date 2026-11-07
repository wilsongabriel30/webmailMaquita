// Fecha de vencimiento de una tarea tal como se muestra en la Lista y en la Cuadrícula (como en To Do):
// «Hoy», «Mañana», «Ayer» o la fecha; en rojo si ya venció, en azul si vence hoy y en gris si está completada.
import type { Task } from '../types';
import { COLORS } from '../types';

export const COLOR_VENCIDA = '#d13438';

const ZONA = 'America/Guayaquil';

/**
 * Día («AAAA-MM-DD») en que vence una tarea, en la hora de Guayaquil.
 * El servidor guarda una fecha sin hora como la medianoche de Guayaquil (05:00 UTC) y una con hora (plazos de
 * Seguimiento) como ese instante: cortar los diez primeros caracteres daba el día UTC, y un plazo de las 19:00 en
 * adelante salía como «Mañana». Una medianoche UTC exacta es una fecha sin hora guardada en UTC: se respeta su día.
 */
export function diaVencimiento(d?: string | null): string {
  if (!d) return '';
  if (d.length === 10 || /T00:00:00(\.0+)?(Z|\+00:00)$/.test(d)) return d.slice(0, 10);
  const instante = new Date(d);
  if (isNaN(instante.getTime())) return d.slice(0, 10);
  return instante.toLocaleDateString('en-CA', { timeZone: ZONA });
}

/** Días desde hoy hasta la fecha (negativo si ya pasó). La fecha llega como «AAAA-MM-DD…». */
function diasHasta(d: string) {
  const fecha = new Date(diaVencimiento(d) + 'T00:00:00');
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
  const fecha = new Date(diaVencimiento(d) + 'T00:00:00');
  const otroAnio = fecha.getFullYear() !== new Date().getFullYear();
  return fecha.toLocaleDateString('es-ES', { day: 'numeric', month: 'short', ...(otroAnio ? { year: 'numeric' } : {}) });
}

/** Fecha completa (dd/mm/aaaa) para la ayuda emergente. */
export function fechaCompleta(d?: string | null) {
  if (!d) return '';
  const [a, m, dia] = diaVencimiento(d).split('-');
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
