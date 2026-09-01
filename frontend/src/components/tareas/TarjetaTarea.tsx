// Tarjeta/fila de una tarea con semáforo, asignados, plazo, avance de subtareas y aceptación.
import type { Tarea } from './tipos';
import { ESTADO_NOMBRE, PRIORIDAD_COLOR, PRIORIDAD_NOMBRE, SEMAFORO_COLOR, fechaCorta, nombreDe } from './tipos';

interface Props { tarea: Tarea; onAbrir: (t: Tarea) => void; compacta?: boolean; arrastrable?: boolean; onDragStart?: (t: Tarea) => void }

export function Semaforo({ tarea }: { tarea: Tarea }) {
  const texto = tarea.estado === 'completada' ? 'Completada' : !tarea.plazo ? 'Sin plazo'
    : tarea.semaforo === 'rojo' ? (new Date(tarea.plazo) < new Date() ? 'Vencida' : 'Vence hoy')
    : tarea.semaforo === 'amarillo' ? 'Vence pronto' : 'A tiempo';
  return (
    <span title={texto} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: SEMAFORO_COLOR[tarea.semaforo], fontWeight: 600 }}>
      <span style={{ width: 10, height: 10, borderRadius: '50%', background: SEMAFORO_COLOR[tarea.semaforo], display: 'inline-block' }} />
      {texto}
    </span>
  );
}

export function TarjetaTarea({ tarea, onAbrir, compacta, arrastrable, onDragStart }: Props) {
  return (
    <div draggable={arrastrable} onDragStart={() => onDragStart?.(tarea)} onClick={() => onAbrir(tarea)}
      style={{ background: '#fff', border: '1px solid #edebe9', borderLeft: `4px solid ${SEMAFORO_COLOR[tarea.semaforo]}`, borderRadius: 6,
        padding: compacta ? '8px 10px' : '10px 14px', margin: compacta ? '6px 0' : '6px 24px', cursor: 'pointer', boxShadow: '0 1px 2px rgba(0,0,0,.06)' }}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,.12)')} onMouseLeave={e => (e.currentTarget.style.boxShadow = '0 1px 2px rgba(0,0,0,.06)')}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ flex: 1, fontSize: 14, fontWeight: 600, color: '#323130', textDecoration: tarea.estado === 'completada' ? 'line-through' : 'none' }}>{tarea.titulo}</span>
        <span style={{ fontSize: 11, color: '#fff', background: PRIORIDAD_COLOR[tarea.prioridad], borderRadius: 10, padding: '1px 7px' }}>{PRIORIDAD_NOMBRE[tarea.prioridad]}</span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center', marginTop: 6, fontSize: 12, color: '#605e5c' }}>
        <Semaforo tarea={tarea} />
        <span>📅 {fechaCorta(tarea.plazo)}</span>
        <span title={tarea.asignados.join(', ')}>👤 {tarea.asignados.map(nombreDe).join(', ') || '—'}</span>
        {!compacta && <span>por {nombreDe(tarea.asignado_por)}</span>}
        <span style={{ background: '#f3f2f1', borderRadius: 10, padding: '1px 7px' }}>{ESTADO_NOMBRE[tarea.estado]}</span>
        {tarea.subtareas_total > 0 && <span>☑ {tarea.subtareas_hechas}/{tarea.subtareas_total}</span>}
        {tarea.comentarios > 0 && <span>💬 {tarea.comentarios}</span>}
        {tarea.correo && <span title={tarea.correo.subject}>📎 correo</span>}
        {tarea.aceptacion === 'rechazada' && <span style={{ color: '#a4262c', fontWeight: 600 }}>Rechazada</span>}
        {tarea.aceptacion === 'sin_responder' && tarea.estado !== 'completada' && tarea.estado !== 'espera' && <span style={{ color: '#c19c00' }}>Sin aceptar</span>}
        {tarea.escalado_en && <span style={{ color: '#a4262c' }}>⬆ escalada</span>}
        {tarea.etiquetas.map(e => <span key={e} style={{ background: '#eff6fc', color: '#004578', borderRadius: 10, padding: '1px 7px' }}>{e}</span>)}
      </div>
    </div>
  );
}
