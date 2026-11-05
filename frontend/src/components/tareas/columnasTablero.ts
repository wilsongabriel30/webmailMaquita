// Columnas del tablero de Seguimiento y a cuál va cada tarea.
// «Vencidas» (05/11/2026) junta TODAS las tareas atrasadas sin completar. «Vencida» no es un estado guardado:
// lo calcula el servidor por el plazo. Por eso arrastrar una vencida a «En curso» cambia su estado guardado
// (la tarjeta lo muestra) pero la deja en «Vencidas»; solo sale de ahí al completarla o al cambiar su fecha.
// A «Vencidas» no se puede soltar nada.
import type { Estado, Tarea } from './tipos';

export type Columna = 'vencida' | 'espera' | 'pendiente' | 'en_curso' | 'completada';
type Guardado = Exclude<Estado, 'vencida'>;

export const COLUMNAS: Columna[] = ['vencida', 'espera', 'pendiente', 'en_curso', 'completada'];

/** Columnas a las que se puede soltar una tarea («En espera» depende de otra tarea: no se elige a mano). */
export const DESTINOS: Guardado[] = ['pendiente', 'en_curso', 'completada'];

/** Estado guardado de la tarea (el de una vencida viene aparte, en `estado_guardado`). */
export function estadoGuardado(t: Tarea): Guardado {
  if (t.estado !== 'vencida') return t.estado;
  const g = t.estado_guardado;
  return g === 'en_curso' || g === 'pendiente' || g === 'espera' || g === 'completada' ? g : 'pendiente';
}

export const columnaDe = (t: Tarea): Columna => t.estado;

/** Cómo queda la tarea al cambiarle el estado (mientras responde el servidor): una vencida sigue vencida salvo al completarla. */
export function conEstado(t: Tarea, nuevo: Guardado): Tarea {
  if (t.estado === 'vencida' && nuevo !== 'completada') return { ...t, estado_guardado: nuevo };
  return { ...t, estado: nuevo, estado_guardado: nuevo };
}

/** Una tarea «En espera» aguarda a que se complete otra: no se arrastra. */
export const sePuedeArrastrar = (t: Tarea) => estadoGuardado(t) !== 'espera';

/** ¿Soltar esta tarea en esta columna cambia algo? */
export function destinoValido(t: Tarea | null, col: Columna): col is Guardado {
  return !!t && (DESTINOS as Columna[]).includes(col) && estadoGuardado(t) !== col;
}

/** Columnas visibles: «Vencidas» siempre; «En espera» solo si alguna tarea lo está. */
export function columnasVisibles(tareas: Tarea[]): Columna[] {
  return COLUMNAS.filter(c => c !== 'espera' || tareas.some(t => columnaDe(t) === 'espera'));
}

export type CambioEstado = (t: Tarea, estado: Estado) => void | Promise<void>;
