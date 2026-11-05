// Columnas del tablero de Seguimiento y a cuál va cada tarea.
// «Vencida» no es columna: es un estado calculado por el plazo (el servidor la devuelve como `estado`) y,
// como columna, arrastrar la tarea a «En curso» no la movía (al recalcular volvía a «Vencida»). Una tarea
// vencida va en la columna de su estado guardado y la marca su semáforo rojo.
import type { Estado, Tarea } from './tipos';

export type Columna = 'espera' | 'pendiente' | 'en_curso' | 'completada';

export const COLUMNAS: Columna[] = ['espera', 'pendiente', 'en_curso', 'completada'];

/** Columnas a las que se puede soltar una tarea («En espera» depende de otra tarea: no se elige a mano). */
export const DESTINOS: Columna[] = ['pendiente', 'en_curso', 'completada'];

export function columnaDe(t: Tarea): Columna {
  if (t.estado !== 'vencida') return t.estado;
  const g = t.estado_guardado;
  return g === 'en_curso' || g === 'pendiente' || g === 'espera' || g === 'completada' ? g : 'pendiente';
}

/** Una tarea «En espera» aguarda a que se complete otra: no se arrastra. */
export const sePuedeArrastrar = (t: Tarea) => columnaDe(t) !== 'espera';

/** ¿Soltar esta tarea en esta columna cambia algo? */
export function destinoValido(t: Tarea | null, col: Columna): boolean {
  return !!t && DESTINOS.includes(col) && columnaDe(t) !== col;
}

/** Columnas visibles: «En espera» solo si alguna tarea lo está. */
export function columnasVisibles(tareas: Tarea[]): Columna[] {
  return COLUMNAS.filter(c => c !== 'espera' || tareas.some(t => columnaDe(t) === 'espera'));
}

export type CambioEstado = (t: Tarea, estado: Estado) => void | Promise<void>;
