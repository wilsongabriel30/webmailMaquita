// Modo «Tablero» de Tareas (09/11/2026): columnas Vencidas / Pendiente / En curso / Completada, como el tablero de
// Seguimiento, para las tareas de cualquier lista. «Completada» sale de `completed` (lo de siempre); «Pendiente» y
// «En curso», del `estado` guardado; «Vencidas» no es un estado: la calcula la fecha. Arrastrar una vencida a
// «En curso» guarda el estado (la tarjeta lo muestra) pero sigue en «Vencidas» hasta completarla o cambiar su fecha.
// «En espera» solo existe en tareas con seguimiento que esperan a otra: se muestra si hay alguna y no se arrastra.
import type { Task } from '../types';
import { diaVencimiento } from './fechaVencimiento';
import { hoyTexto } from './repeticion';

export type EstadoLista = 'pendiente' | 'en_curso' | 'completada';
export type ColumnaLista = 'vencida' | 'espera' | EstadoLista;

export const COLUMNAS: ColumnaLista[] = ['vencida', 'espera', 'pendiente', 'en_curso', 'completada'];
export const DESTINOS: EstadoLista[] = ['pendiente', 'en_curso', 'completada'];
export const NOMBRE_COLUMNA: Record<ColumnaLista, string> = {
  vencida: 'Vencidas', espera: 'En espera', pendiente: 'Pendiente', en_curso: 'En curso', completada: 'Completada',
};

/** Completadas que siguen en el tablero: las de los últimos 30 días (las demás, en la vista Lista). */
export const DIAS_COMPLETADAS = 30;

/** Estado de la tarea sin mirar la fecha. */
export function estadoDe(t: Task): EstadoLista | 'espera' {
  if (t.completed) return 'completada';
  if (t.estado === 'en_curso' || t.estado === 'espera') return t.estado;
  return 'pendiente';
}

export function columnaDe(t: Task, hoy: string = hoyTexto()): ColumnaLista {
  if (t.completed) return 'completada';
  if (t.due_date && diaVencimiento(t.due_date) < hoy) return 'vencida';
  return estadoDe(t);
}

/** Cómo se ve la tarea mientras responde el servidor. */
export function conEstado(t: Task, e: EstadoLista): Task {
  return e === 'completada' ? { ...t, completed: true } : { ...t, completed: false, estado: e };
}

export const sePuedeArrastrar = (t: Task) => estadoDe(t) !== 'espera';

/** ¿Soltar la tarea en esta columna cambia algo? A «Vencidas» y «En espera» no se suelta nada. */
export function destinoValido(t: Task | null | undefined, col: ColumnaLista): col is EstadoLista {
  return !!t && sePuedeArrastrar(t) && (DESTINOS as ColumnaLista[]).includes(col) && estadoDe(t) !== col;
}

export function enTablero(t: Task, ahora: number = Date.now()): boolean {
  if (!t.completed || !t.completed_at) return true;
  return ahora - new Date(t.completed_at).getTime() <= DIAS_COMPLETADAS * 86400000;
}

/** «Vencidas» siempre; «En espera» solo si alguna tarea lo está. */
export function columnasVisibles(tareas: Task[]): ColumnaLista[] {
  return COLUMNAS.filter(c => c !== 'espera' || tareas.some(t => estadoDe(t) === 'espera'));
}
