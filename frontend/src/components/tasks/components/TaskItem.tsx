
import type { MouseEvent } from 'react';
import type { Task } from '../types';
import { COLORS } from '../types';
import { colorCategoria } from './categorias';
import { CirculoPersona } from './CirculoPersona';
import { urlCorreo } from './urlCorreo';

interface Props {
  task: Task;
  onToggle: (id: string) => void;
  onToggleImportant: (id: string) => void;
  onClick: (task: Task) => void;
  /** En las listas inteligentes se muestra de qué lista es cada tarea (como en To Do). */
  mostrarLista?: boolean;
  seleccionada?: boolean;
  /** Clic derecho: menú de la tarea (Mover a…, Mi día, etc.). */
  onMenu?: (task: Task, e: MouseEvent) => void;
}

export function TaskItem({ task, onToggle, onToggleImportant, onClick, mostrarLista, seleccionada, onMenu }: Props) {
  const formatDate = (d?: string) => {
    if (!d) return '';
    const date = new Date(d.slice(0, 10) + 'T00:00:00');
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const diff = date.getTime() - today.getTime();
    const days = Math.round(diff / 86400000);
    if (days === 0) return 'Hoy';
    if (days === 1) return 'Mañana';
    if (days === -1) return 'Ayer';
    if (days < -1) return 'Atrasado';
    return date.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
  };

  const dueDateColor = () => {
    if (!task.due_date) return COLORS.secondary;
    const date = new Date(task.due_date.slice(0, 10) + 'T00:00:00');
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    if (date < today) return '#d13438';
    if (date.getTime() === today.getTime()) return COLORS.primary;
    return COLORS.secondary;
  };

  return (
    <div
      onClick={() => onClick(task)}
      onContextMenu={onMenu ? e => { e.preventDefault(); onMenu(task, e); } : undefined}
      style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '10px 24px', cursor: 'pointer',
        transition: 'background 0.1s',
        background: seleccionada ? COLORS.activeBg : 'transparent',
        fontFamily: "'Segoe UI', system-ui, sans-serif",
      }}
      onMouseEnter={e => { if (!seleccionada) e.currentTarget.style.background = COLORS.hoverBg; }}
      onMouseLeave={e => { if (!seleccionada) e.currentTarget.style.background = 'transparent'; }}
    >
      {/* Checkbox */}
      <div
        role="checkbox" aria-checked={task.completed} aria-label={task.completed ? 'Marcar como no completada' : 'Marcar como completada'}
        onClick={e => { e.stopPropagation(); onToggle(task.id); }}
        style={{
          width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
          border: task.completed ? 'none' : `1.5px solid ${COLORS.muted}`,
          background: task.completed ? COLORS.primary : 'transparent',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', transition: 'all 0.15s',
        }}
      >
        {task.completed ? (
          <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={3}>
            <polyline points="20 6 9 17 4 12" />
          </svg>
        ) : null}
      </div>

      {/* Title + metadata */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 14, color: task.completed ? COLORS.muted : COLORS.text,
          textDecoration: task.completed ? 'line-through' : 'none',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {task.title}
        </div>
        {(task.correo || (mostrarLista && task.list_name)) && (
          <div style={{ fontSize: 12, color: COLORS.secondary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {task.correo ? (
              <a href={urlCorreo(task.correo)} onClick={e => e.stopPropagation()} style={{ color: COLORS.primary, textDecoration: 'none' }}>
                Correo{task.correo.remitente ? ` de ${task.correo.remitente}` : ''}
              </a>
            ) : task.list_name}
          </div>
        )}
        {(task.due_date || task.recurrence || task.reminder || task.pasos || task.adjuntos || task.note || !!task.labels?.length) && (
          <div style={{ fontSize: 12, color: COLORS.secondary, marginTop: 2, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            {!!task.pasos && <span>{task.pasos_hechos ?? 0} de {task.pasos}</span>}
            {task.recurrence && (
              <span style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <svg width={11} height={11} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <polyline points="17 1 21 5 17 9" /><path d="M3 11V9a4 4 0 014-4h14" />
                  <polyline points="7 23 3 19 7 15" /><path d="M21 13v2a4 4 0 01-4 4H3" />
                </svg>
              </span>
            )}
            {task.reminder && (
              <span style={{ display: 'flex', alignItems: 'center', gap: 2, color: '#0078d4' }}>
                <svg width={11} height={11} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 01-3.46 0" />
                </svg>
              </span>
            )}
            {task.due_date && (
              <span style={{ color: dueDateColor() }}>
                <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} style={{ verticalAlign: -1, marginRight: 3 }}>
                  <rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" />
                </svg>
                {formatDate(task.due_date)}
              </span>
            )}
            {!!task.adjuntos && (
              <span title={`${task.adjuntos} archivo(s)`} style={{ display: 'flex', alignItems: 'center' }}>
                <svg aria-label="Con archivos" width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
                </svg>
              </span>
            )}
            {(task.labels || []).map(c => (
              <span key={c} title={c} style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                <span aria-hidden="true" style={{ width: 8, height: 8, borderRadius: 2, background: colorCategoria(c).color }} />
                {c.replace(/^Categoría /, '')}
              </span>
            ))}
            {!!task.note && (
              <span title="Tiene nota" style={{ display: 'flex', alignItems: 'center' }}>
                <svg aria-label="Con nota" width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><path d="M14 2v6h6M8 13h8M8 17h5" />
                </svg>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Personas asignadas */}
      {!!task.asignados?.length && (
        <div style={{ display: 'flex', flexShrink: 0 }} aria-label={`Asignada a ${task.asignados.join(', ')}`}>
          {task.asignados.slice(0, 3).map((e, i) => (
            <span key={e} style={{ marginLeft: i ? -6 : 0, border: '2px solid white', borderRadius: '50%', display: 'flex' }}>
              <CirculoPersona email={e} tamano={22} />
            </span>
          ))}
          {task.asignados.length > 3 && <span style={{ fontSize: 11, color: COLORS.secondary, alignSelf: 'center', marginLeft: 2 }}>+{task.asignados.length - 3}</span>}
        </div>
      )}

      {/* Star */}
      <div
        onClick={e => { e.stopPropagation(); onToggleImportant(task.id); }}
        style={{ cursor: 'pointer', display: 'flex', flexShrink: 0 }}
      >
        <svg width={16} height={16} viewBox="0 0 24 24"
          fill={task.important ? COLORS.primary : 'none'}
          stroke={task.important ? COLORS.primary : COLORS.muted}
          strokeWidth={1.8}
        >
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
        </svg>
      </div>
    </div>
  );
}
