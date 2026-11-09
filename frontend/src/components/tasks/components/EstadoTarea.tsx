// Estado de la tarea en el panel de detalle (09/11/2026): Pendiente / En curso / Completada, lo mismo que mover la
// tarjeta de columna en la vista Tablero. Una tarea «En espera» (con seguimiento, aguarda a otra) no se cambia aquí.
import type { Task } from '../types';
import { COLORS } from '../types';
import { DESTINOS, NOMBRE_COLUMNA, estadoDe, type EstadoLista } from './columnasLista';
import { seccion } from './estiloPanel';

const COLOR: Record<EstadoLista, string> = { pendiente: COLORS.primary, en_curso: '#8a6d00', completada: '#107c10' };

export function EstadoTarea({ task, onCambiar }: { task: Task; onCambiar: (estado: EstadoLista) => void }) {
  const actual = estadoDe(task);
  return (
    <div style={seccion}>
      <div id={`estado-${task.id}`} style={{ fontSize: 12, color: COLORS.secondary, marginBottom: 8 }}>Estado</div>
      {actual === 'espera' ? (
        <span style={{ fontSize: 13, color: COLORS.secondary }}>En espera: empieza cuando se complete la tarea anterior.</span>
      ) : (
        <div role="radiogroup" aria-labelledby={`estado-${task.id}`} style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {DESTINOS.map(e => {
            const activo = actual === e;
            return (
              <button key={e} type="button" role="radio" aria-checked={activo} onClick={() => { if (!activo) onCambiar(e); }}
                style={{
                  padding: '5px 12px', fontSize: 13, borderRadius: 14, cursor: activo ? 'default' : 'pointer', fontFamily: 'inherit',
                  border: `1px solid ${activo ? COLOR[e] : COLORS.border}`, background: activo ? COLOR[e] : 'white',
                  color: activo ? 'white' : COLORS.text, fontWeight: activo ? 600 : 400,
                }}>
                {NOMBRE_COLUMNA[e]}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
