// Tarjeta del panel para una tarea que me asignaron: quién la asignó y cuándo, el plazo, las indicaciones y el
// botón «Marcar como realizada». Al marcarla, a quien la asignó le llegan un aviso y un correo.
import type { Task } from '../types';
import { COLORS } from '../types';
import { seccion } from './estiloPanel';

function dia(iso: string): string {
  const d = new Date(iso.length === 10 ? iso + 'T00:00:00' : iso);
  return d.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
}

export function TarjetaAsignacion({ task, onToggle }: { task: Task; onToggle: (id: string) => void }) {
  const a = task.asignacion;
  if (!a) return null;
  const plazo = (task.due_date || '').slice(0, 10);
  const vencida = !task.completed && !!plazo && new Date(plazo + 'T23:59:59') < new Date();
  return (
    <div style={{ ...seccion, gap: 6 }}>
      <div style={{ fontSize: 13 }}>
        Asignada por <strong>{a.por_nombre}</strong>
        <span style={{ color: COLORS.secondary }}> · el {dia(a.en)}</span>
      </div>
      {plazo && (
        <div style={{ fontSize: 13, color: vencida ? '#d13438' : COLORS.text }}>
          Plazo: {dia(plazo)}{vencida ? ' (vencido)' : ''}
        </div>
      )}
      {a.indicaciones && (
        <div style={{ fontSize: 13, whiteSpace: 'pre-wrap', width: '100%' }}>
          <div style={{ fontSize: 12, color: COLORS.secondary, marginBottom: 2 }}>Indicaciones</div>
          {a.indicaciones}
        </div>
      )}
      {task.completed ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4, fontSize: 13, color: '#107c10' }}>
          ✓ Realizada · se avisó a {a.por_nombre}
          <button type="button" onClick={() => onToggle(task.id)}
            style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontSize: 12, color: COLORS.secondary, fontFamily: 'inherit', textDecoration: 'underline' }}>
            Reabrir
          </button>
        </div>
      ) : (
        <button type="button" onClick={() => onToggle(task.id)}
          style={{
            marginTop: 4, fontSize: 13, padding: '7px 16px', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit',
            border: '1px solid #107c10', background: '#107c10', color: 'white',
          }}>
          ✓ Marcar como realizada
        </button>
      )}
    </div>
  );
}
