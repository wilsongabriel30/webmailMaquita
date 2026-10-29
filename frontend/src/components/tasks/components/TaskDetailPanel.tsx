// Panel de detalle de una tarea, como el de Outlook (F5): tarjetas sobre fondo rosado claro. Completar, título e
// importancia con sus pasos; Mi día; asignar; recordatorio, vencimiento y repetición; categoría; archivos; nota; y,
// al pie, ocultar el panel, cuándo se creó y eliminar.
import { useState } from 'react';
import type { Task } from '../types';
import { COLORS } from '../types';
import { ActividadLista } from './ActividadLista';
import { AdjuntosTarea } from './AdjuntosTarea';
import { AsignarTarea } from './AsignarTarea';
import { CategoriaTarea } from './CategoriaTarea';
import { EnlaceCorreo } from './EnlaceCorreo';
import { RecordatorioTarea } from './RecordatorioTarea';
import { RepeticionTarea } from './RepeticionTarea';
import { StepsList } from './StepsList';
import { TarjetaPanel } from './TarjetaPanel';
import { VencimientoTarea } from './VencimientoTarea';
import { FONDO_PANEL, LINEA_TARJETA, filaSeccion, seccion } from './estiloPanel';
import { hoyTexto } from './repeticion';

interface Props {
  task: Task;
  onUpdate: (id: string, data: Partial<Task>) => void;
  onToggle: (id: string) => void;
  onToggleImportant: (id: string) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
  /** Cambiaron los pasos o los archivos: se vuelve a pedir la lista para ver los contadores. */
  onRefrescar: () => void;
  /** La tarea volvió del servidor con otros asignados. */
  onAsignada: (t: Task) => void;
}

function fechaCorta(iso: string): string {
  const d = new Date(iso);
  const hoy = new Date();
  const ayer = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - 1);
  if (d.toDateString() === hoy.toDateString()) return 'hoy';
  if (d.toDateString() === ayer.toDateString()) return 'ayer';
  return 'el ' + d.toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' });
}

const iconoPie = { display: 'flex', background: 'none', border: 'none', cursor: 'pointer', color: COLORS.secondary, padding: 4 };

export function TaskDetailPanel({ task, onUpdate, onToggle, onToggleImportant, onDelete, onClose, onRefrescar, onAsignada }: Props) {
  const [title, setTitle] = useState(task.title);
  const [verActividad, setVerActividad] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [notes, setNotes] = useState(task.note || '');

  // Si la tarea cambia desde fuera (otra tarea, o se editó en la lista), el formulario se pone al día.
  const clave = `${task.id}|${task.title}|${task.note || ''}`;
  const [claveVista, setClaveVista] = useState(clave);
  if (claveVista !== clave) {
    setClaveVista(clave);
    setTitle(task.title);
    setNotes(task.note || '');
    if (task.id !== claveVista.split('|')[0]) setConfirmDelete(false);
  }

  const saveTitle = () => {
    if (title.trim() && title !== task.title) onUpdate(task.id, { title: title.trim() });
  };

  const saveNotes = () => {
    if (notes !== (task.note || '')) onUpdate(task.id, { note: notes });
  };

  // Como en To Do: una tarea que se repite y no tiene fecha vence hoy.
  const cambiarRepeticion = (regla: string | null) => {
    if (regla && !task.due_date) onUpdate(task.id, { recurrence: regla, due_date: hoyTexto() });
    else onUpdate(task.id, { recurrence: regla });
  };

  const pie = task.completed && task.completed_at
    ? `Completada ${fechaCorta(task.completed_at)}`
    : task.created_at ? `Creada ${fechaCorta(task.created_at)}` : '';

  return (
    <aside aria-label="Detalles de la tarea" className="panel-tarea" style={{
      width: 360, minWidth: 360, background: FONDO_PANEL, borderLeft: `1px solid ${COLORS.border}`,
      display: 'flex', flexDirection: 'column', height: '100%',
      fontFamily: "'Segoe UI', system-ui, sans-serif",
    }}>
      <style>{`.panel-tarea input.paso-nuevo::placeholder, .panel-tarea textarea.nota-tarea::placeholder { color: ${COLORS.secondary}; }
.panel-tarea input.paso-nuevo::placeholder { color: ${COLORS.primary}; }`}</style>

      <div style={{ flex: 1, overflowY: 'auto', paddingTop: 16 }}>
        {/* Completar, título e importancia, con los pasos */}
        <TarjetaPanel>
          <div>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, padding: '14px 16px 6px' }}>
              <button type="button" role="checkbox" aria-checked={task.completed}
                aria-label={task.completed ? 'Marcar como no completada' : 'Marcar como completada'}
                onClick={() => onToggle(task.id)}
                style={{
                  width: 20, height: 20, marginTop: 3, borderRadius: '50%', padding: 0, flexShrink: 0, cursor: 'pointer',
                  border: task.completed ? 'none' : `1.5px solid ${COLORS.primary}`,
                  background: task.completed ? COLORS.primary : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                {task.completed && <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={3}><polyline points="20 6 9 17 4 12" /></svg>}
              </button>
              <textarea
                aria-label="Título de la tarea"
                value={title}
                rows={Math.min(5, Math.max(1, Math.ceil(title.length / 26)))}
                onChange={e => setTitle(e.target.value.replace(/\n/g, ''))}
                onBlur={saveTitle}
                onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); saveTitle(); e.currentTarget.blur(); } }}
                style={{
                  flex: 1, minWidth: 0, border: 'none', outline: 'none', background: 'transparent', resize: 'none', padding: 0,
                  fontSize: 17, lineHeight: '24px', fontWeight: 600, fontFamily: 'inherit',
                  color: task.completed ? COLORS.muted : COLORS.text,
                  textDecoration: task.completed ? 'line-through' : 'none',
                }}
              />
              <button type="button" aria-label={task.important ? 'Quitar importancia' : 'Marcar como importante'}
                onClick={() => onToggleImportant(task.id)}
                style={{ display: 'flex', background: 'none', border: 'none', padding: 2, marginTop: 2, cursor: 'pointer' }}>
                <svg width={20} height={20} viewBox="0 0 24 24" fill={task.important ? COLORS.primary : 'none'}
                  stroke={COLORS.primary} strokeWidth={1.6}>
                  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                </svg>
              </button>
            </div>
            <StepsList cardId={task.id} onCambio={onRefrescar} />
          </div>
        </TarjetaPanel>

        {/* Tarea que viene de un correo marcado: enlace para abrirlo */}
        {task.correo && <TarjetaPanel><EnlaceCorreo correo={task.correo} /></TarjetaPanel>}

        <TarjetaPanel>
          <div style={seccion}>
            <button type="button" style={filaSeccion} onClick={() => onUpdate(task.id, { my_day: !task.my_day })}>
              <svg aria-hidden="true" width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={task.my_day ? COLORS.primary : COLORS.secondary} strokeWidth={1.6}>
                <circle cx="12" cy="12" r="4.5" /><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
              </svg>
              <span style={{ flex: 1, color: task.my_day ? COLORS.primary : COLORS.text }}>
                {task.my_day ? 'Agregada a Mi día' : 'Agregar a Mi día'}
              </span>
              {task.my_day && <span aria-label="Quitar de Mi día" title="Quitar de Mi día" style={{ color: COLORS.secondary, fontSize: 16 }}>&times;</span>}
            </button>
          </div>
        </TarjetaPanel>

        {!task.correo && <TarjetaPanel><AsignarTarea task={task} onAsignada={onAsignada} /></TarjetaPanel>}

        <TarjetaPanel>
          <RecordatorioTarea valor={task.reminder} onCambiar={r => onUpdate(task.id, { reminder: r })} />
          <VencimientoTarea valor={(task.due_date || '').slice(0, 10)} onCambiar={f => onUpdate(task.id, { due_date: f })} />
          <RepeticionTarea valor={task.recurrence} onCambiar={cambiarRepeticion} />
        </TarjetaPanel>

        <TarjetaPanel>
          <CategoriaTarea valor={task.labels || []} onCambiar={labels => onUpdate(task.id, { labels })} />
        </TarjetaPanel>

        <TarjetaPanel>
          <AdjuntosTarea cardId={task.id} onCambio={onRefrescar} />
        </TarjetaPanel>

        <TarjetaPanel>
          <textarea
            aria-label="Nota"
            className="nota-tarea"
            value={notes}
            onChange={e => setNotes(e.target.value)}
            onBlur={saveNotes}
            placeholder="Agregar nota"
            style={{
              width: '100%', minHeight: 96, border: 'none', outline: 'none', background: 'transparent', boxSizing: 'border-box',
              padding: '14px 16px', fontSize: 14, color: COLORS.text, resize: 'vertical', fontFamily: 'inherit',
            }}
          />
        </TarjetaPanel>

        {/* Registro de actividad de la tarea (listas compartidas, F4) */}
        <div style={{ padding: '0 16px 16px' }}>
          <button type="button" aria-expanded={verActividad} onClick={() => setVerActividad(!verActividad)}
            style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontSize: 12, color: COLORS.secondary, fontFamily: 'inherit' }}>
            {verActividad ? '▾' : '▸'} Actividad
          </button>
          {verActividad && <ActividadLista ruta={`/tasks/tasks/${task.id}/actividad`} vacio="Sin actividad registrada." />}
        </div>
      </div>

      {/* Pie: ocultar el panel, cuándo se creó y eliminar */}
      <div style={{ padding: '10px 12px', borderTop: `1px solid ${LINEA_TARJETA}` }}>
        {!confirmDelete ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button type="button" aria-label="Ocultar la vista de detalles" title="Ocultar la vista de detalles" onClick={onClose} style={iconoPie}>
              <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6}>
                <rect x="3" y="4" width="18" height="16" rx="2" /><path d="M15 4v16M8 10l2 2-2 2" />
              </svg>
            </button>
            <span style={{ flex: 1, fontSize: 12, color: COLORS.secondary, textAlign: 'center' }}>{pie}</span>
            <button type="button" aria-label="Eliminar tarea" title="Eliminar tarea" onClick={() => setConfirmDelete(true)} style={iconoPie}
              onMouseEnter={e => { e.currentTarget.style.color = '#d13438'; }}
              onMouseLeave={e => { e.currentTarget.style.color = COLORS.secondary; }}>
              <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6}>
                <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6M10 11v6M14 11v6" />
              </svg>
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <span style={{ fontSize: 12, color: COLORS.text }}>¿Eliminar «{task.title}»? No se puede deshacer.</span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="button" onClick={() => onDelete(task.id)}
                style={{ flex: 1, padding: '8px 16px', fontSize: 13, background: '#d13438', border: 'none', color: 'white', borderRadius: 4, cursor: 'pointer' }}>
                Eliminar
              </button>
              <button type="button" onClick={() => setConfirmDelete(false)}
                style={{ flex: 1, padding: '8px 16px', fontSize: 13, background: 'white', border: `1px solid ${COLORS.border}`, color: COLORS.text, borderRadius: 4, cursor: 'pointer' }}>
                Cancelar
              </button>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
