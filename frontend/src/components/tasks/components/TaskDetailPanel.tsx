// Panel de detalle de una tarea (como en To Do): completar, título e importancia; pasos; Mi día; recordatorio;
// vencimiento; repetición; archivos; nota; y, al pie, cuándo se creó y eliminar.
import { useState } from 'react';
import type { Task } from '../types';
import { COLORS } from '../types';
import { AdjuntosTarea } from './AdjuntosTarea';
import { EnlaceCorreo } from './EnlaceCorreo';
import { RecordatorioTarea } from './RecordatorioTarea';
import { RepeticionTarea } from './RepeticionTarea';
import { StepsList } from './StepsList';
import { filaSeccion, quitar, seccion } from './estiloPanel';
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
}

export function TaskDetailPanel({ task, onUpdate, onToggle, onToggleImportant, onDelete, onClose, onRefrescar }: Props) {
  const [title, setTitle] = useState(task.title);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [notes, setNotes] = useState(task.note || '');
  const [dueDate, setDueDate] = useState((task.due_date || '').slice(0, 10));

  // Si la tarea cambia desde fuera (otra tarea, o se editó en la lista), el formulario se pone al día.
  const clave = `${task.id}|${task.title}|${task.note || ''}|${task.due_date || ''}`;
  const [claveVista, setClaveVista] = useState(clave);
  if (claveVista !== clave) {
    setClaveVista(clave);
    setTitle(task.title);
    setNotes(task.note || '');
    setDueDate((task.due_date || '').slice(0, 10));
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

  return (
    <div style={{
      width: 360, minWidth: 360, background: 'white', borderLeft: `1px solid ${COLORS.border}`,
      display: 'flex', flexDirection: 'column', height: '100%',
      fontFamily: "'Segoe UI', system-ui, sans-serif",
      boxShadow: '-2px 0 8px rgba(0,0,0,0.05)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', padding: '12px 20px', borderBottom: `1px solid ${COLORS.border}` }}>
        <div style={{ flex: 1, fontSize: 12, color: COLORS.secondary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {task.list_name || 'Detalles de la tarea'}
        </div>
        <button type="button" aria-label="Cerrar detalles" onClick={onClose} style={{
          background: 'none', border: 'none', cursor: 'pointer', fontSize: 18,
          color: COLORS.secondary, padding: '0 4px', lineHeight: 1,
        }}>&times;</button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {/* Completar, título e importancia */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '16px 20px 8px' }}>
          <button type="button" role="checkbox" aria-checked={task.completed}
            aria-label={task.completed ? 'Marcar como no completada' : 'Marcar como completada'}
            onClick={() => onToggle(task.id)}
            style={{
              width: 20, height: 20, borderRadius: '50%', padding: 0, flexShrink: 0, cursor: 'pointer',
              border: task.completed ? 'none' : `1.5px solid ${COLORS.muted}`,
              background: task.completed ? COLORS.primary : 'transparent',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
            {task.completed && <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={3}><polyline points="20 6 9 17 4 12" /></svg>}
          </button>
          <input
            aria-label="Título de la tarea"
            value={title}
            onChange={e => setTitle(e.target.value)}
            onBlur={saveTitle}
            onKeyDown={e => { if (e.key === 'Enter') { saveTitle(); e.currentTarget.blur(); } }}
            style={{
              flex: 1, minWidth: 0, border: 'none', outline: 'none', fontSize: 16, fontWeight: 600, fontFamily: 'inherit',
              color: task.completed ? COLORS.muted : COLORS.text,
              textDecoration: task.completed ? 'line-through' : 'none',
            }}
          />
          <button type="button" aria-label={task.important ? 'Quitar importancia' : 'Marcar como importante'}
            onClick={() => onToggleImportant(task.id)}
            style={{ display: 'flex', background: 'none', border: 'none', padding: 2, cursor: 'pointer' }}>
            <svg width={18} height={18} viewBox="0 0 24 24" fill={task.important ? COLORS.primary : 'none'}
              stroke={task.important ? COLORS.primary : COLORS.muted} strokeWidth={1.8}>
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
            </svg>
          </button>
        </div>

        {/* Tarea que viene de un correo marcado: enlace para abrirlo */}
        {task.correo && <EnlaceCorreo correo={task.correo} />}

        <StepsList cardId={task.id} onCambio={onRefrescar} />

        <div style={seccion}>
          <button type="button" style={filaSeccion} onClick={() => onUpdate(task.id, { my_day: !task.my_day })}>
            <svg aria-hidden="true" width={18} height={18} viewBox="0 0 24 24" fill={task.my_day ? COLORS.primary : 'none'} stroke={task.my_day ? COLORS.primary : COLORS.secondary} strokeWidth={1.8}>
              <circle cx="12" cy="12" r="5" /><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
            </svg>
            <span style={{ color: task.my_day ? COLORS.primary : COLORS.text }}>
              {task.my_day ? 'Agregado a Mi día' : 'Agregar a Mi día'}
            </span>
          </button>
        </div>

        <RecordatorioTarea valor={task.reminder} onCambiar={r => onUpdate(task.id, { reminder: r })} />

        <div style={{ ...seccion, gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%' }}>
            <svg aria-hidden="true" width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={dueDate ? COLORS.primary : COLORS.secondary} strokeWidth={1.8}>
              <rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" />
            </svg>
            <span>{dueDate ? 'Fecha de vencimiento' : 'Agregar fecha de vencimiento'}</span>
            {dueDate && (
              <button type="button" style={quitar} onClick={() => { setDueDate(''); onUpdate(task.id, { due_date: null }); }}>
                Quitar
              </button>
            )}
          </div>
          <input type="date" aria-label="Fecha de vencimiento" value={dueDate}
            onChange={e => setDueDate(e.target.value)}
            onBlur={() => {
              if (dueDate !== (task.due_date || '').slice(0, 10)) onUpdate(task.id, { due_date: dueDate || null });
            }}
            onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur(); }}
            style={{ marginLeft: 30, fontSize: 13, border: `1px solid ${COLORS.border}`, borderRadius: 4, padding: '4px 8px', color: COLORS.text }}
          />
        </div>

        <RepeticionTarea valor={task.recurrence} onCambiar={cambiarRepeticion} />

        <AdjuntosTarea cardId={task.id} onCambio={onRefrescar} />

        <div style={{ padding: '16px 20px', borderBottom: `1px solid ${COLORS.border}` }}>
          <textarea
            aria-label="Nota"
            value={notes}
            onChange={e => setNotes(e.target.value)}
            onBlur={saveNotes}
            placeholder="Agregar nota"
            style={{
              width: '100%', minHeight: 80, border: 'none', outline: 'none',
              fontSize: 13, color: COLORS.text, resize: 'vertical',
              fontFamily: "'Segoe UI', system-ui, sans-serif",
            }}
          />
        </div>
      </div>

      {/* Pie: cuándo se creó y eliminar */}
      <div style={{ padding: '12px 20px', borderTop: `1px solid ${COLORS.border}` }}>
        {!confirmDelete ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ flex: 1, fontSize: 12, color: COLORS.muted, textAlign: 'center' }}>
              {task.completed && task.completed_at
                ? `Completada el ${new Date(task.completed_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}`
                : task.created_at
                  ? `Creada el ${new Date(task.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}`
                  : ''}
            </span>
            <button type="button" aria-label="Eliminar tarea" title="Eliminar tarea" onClick={() => setConfirmDelete(true)}
              style={{ display: 'flex', background: 'none', border: 'none', cursor: 'pointer', color: COLORS.secondary, padding: 4 }}
              onMouseEnter={e => { e.currentTarget.style.color = '#d13438'; }}
              onMouseLeave={e => { e.currentTarget.style.color = COLORS.secondary; }}>
              <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6" />
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
                style={{ flex: 1, padding: '8px 16px', fontSize: 13, background: 'transparent', border: `1px solid ${COLORS.border}`, color: COLORS.text, borderRadius: 4, cursor: 'pointer' }}>
                Cancelar
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
