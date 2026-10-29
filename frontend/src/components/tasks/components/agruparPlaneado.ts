// Grupos de «Planeado» (como en To Do): Vencidas, Hoy, Mañana, Esta semana y Más adelante.
// Los días se cuentan en la hora de Guayaquil, la misma con la que «Mi día» se vacía a medianoche.
// Una tarea sin fecha de vencimiento se ubica por su recordatorio. Las completadas van al final.
import type { Task } from '../types';

const ZONA = 'America/Guayaquil';

/** «AAAA-MM-DD» de un instante, en la hora de Guayaquil. */
export function diaEC(instante: Date): string {
  return instante.toLocaleDateString('en-CA', { timeZone: ZONA });
}

function sumarDias(dia: string, n: number): string {
  const d = new Date(`${dia}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** Día de la tarea: la fecha de vencimiento es un día; el recordatorio, una hora concreta. */
export function diaDeTarea(t: Task): string | null {
  if (t.due_date) return t.due_date.slice(0, 10);
  if (t.reminder) {
    const r = new Date(t.reminder);
    return isNaN(r.getTime()) ? null : diaEC(r);
  }
  return null;
}

export interface GrupoTareas { clave: string; label: string; tasks: Task[] }

export function agruparPlaneado(tareas: Task[], ahora: Date = new Date()): GrupoTareas[] {
  const hoy = diaEC(ahora);
  const manana = sumarDias(hoy, 1);
  const diaSemana = new Date(`${hoy}T12:00:00Z`).getUTCDay(); // 0 = domingo
  const domingo = sumarDias(hoy, diaSemana === 0 ? 0 : 7 - diaSemana);

  const grupos: GrupoTareas[] = [
    { clave: 'vencidas', label: 'Vencidas', tasks: [] },
    { clave: 'hoy', label: 'Hoy', tasks: [] },
    { clave: 'manana', label: 'Mañana', tasks: [] },
    { clave: 'semana', label: 'Esta semana', tasks: [] },
    { clave: 'despues', label: 'Más adelante', tasks: [] },
    { clave: 'completadas', label: 'Completadas', tasks: [] },
  ];
  const [vencidas, deHoy, deManana, semana, despues, completadas] = grupos;
  for (const t of tareas) {
    const dia = diaDeTarea(t);
    if (t.completed) completadas.tasks.push(t);
    else if (!dia) continue;
    else if (dia < hoy) vencidas.tasks.push(t);
    else if (dia === hoy) deHoy.tasks.push(t);
    else if (dia === manana) deManana.tasks.push(t);
    else if (dia <= domingo) semana.tasks.push(t);
    else despues.tasks.push(t);
  }
  return grupos.filter(g => g.tasks.length > 0);
}
