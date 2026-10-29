import { useState, type ReactNode } from 'react';
import type { ActiveView } from '../types';
import { SMART_LISTS, COLORS } from '../types';
import { SidebarIcon } from './IconoBarra';
import { esTarea, idTarea } from './arrastreTarea';

// Soltar una tarea aquí: «Mi día» la agrega a Mi día, «Importante» la marca y «Tareas» la mueve a esa lista.
const ACEPTAN_TAREAS = ['my-day', 'important', 'tasks'];

interface Props {
  activeView: ActiveView;
  onViewChange: (v: ActiveView) => void;
  smartCounts: Record<string, number>;
  /** Listas propias y grupos (MisListas), debajo de las listas inteligentes. */
  children?: ReactNode;
  /** Pie fijo: los botones «Nueva lista» y «Nuevo grupo». */
  pie?: ReactNode;
  /** Caja de búsqueda, arriba junto al botón de plegar la barra. */
  buscador?: ReactNode;
  onSoltarTarea?: (destino: ActiveView, taskId: string) => void;
  /** ⚙ Configuración (F6) y listas inteligentes que la persona ocultó. */
  onAjustes?: () => void;
  ocultas?: string[];
}

export function TasksSidebar({ activeView, onViewChange, smartCounts, children, pie, buscador, onSoltarTarea, onAjustes, ocultas = [] }: Props) {
  const [sobre, setSobre] = useState<string | null>(null);
  const today = new Date();
  const dateStrRaw = today.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' });
  const dateStr = dateStrRaw.charAt(0).toUpperCase() + dateStrRaw.slice(1);

  return (
    <div
      style={{
        width: 280, minWidth: 280, background: 'white', borderRight: `1px solid ${COLORS.border}`,
        display: 'flex', flexDirection: 'column', height: '100%', userSelect: 'none',
        fontFamily: "'Segoe UI', system-ui, sans-serif",
      }}
    >
      {/* Header */}
      <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12, borderBottom: `1px solid ${COLORS.border}` }}>
        <button
          aria-label="Alternar panel de listas"
          onClick={() => window.dispatchEvent(new CustomEvent('toggle-tasks-sidebar'))}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex' }}
        >
          <svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke={COLORS.secondary} strokeWidth={2}>
            <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        {buscador}
        {onAjustes && (
          <button type="button" aria-label="Configuración de Tareas" title="Configuración" onClick={onAjustes}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2, display: 'flex', color: COLORS.secondary, flexShrink: 0 }}>
            <svg aria-hidden="true" width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6}>
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z" />
            </svg>
          </button>
        )}
      </div>

      {/* Smart lists */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        {SMART_LISTS.filter(sl => !ocultas.includes(sl.id) || activeView === sl.id).map(sl => {
          const isActive = activeView === sl.id;
          const count = smartCounts[sl.id] || 0;
          const acepta = !!onSoltarTarea && ACEPTAN_TAREAS.includes(sl.id);
          return (
            <div
              key={sl.id}
              onClick={() => onViewChange(sl.id)}
              onDragOver={acepta ? e => { if (esTarea(e)) { e.preventDefault(); setSobre(sl.id); } } : undefined}
              onDragLeave={acepta ? () => setSobre(s => (s === sl.id ? null : s)) : undefined}
              onDrop={acepta ? e => { if (esTarea(e)) { e.preventDefault(); onSoltarTarea!(sl.id, idTarea(e)); } setSobre(null); } : undefined}
              style={{
                outline: sobre === sl.id ? `2px dashed ${COLORS.primary}` : 'none', outlineOffset: -2,
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '10px 16px', cursor: 'pointer',
                background: isActive ? COLORS.activeBg : 'transparent',
                borderLeft: isActive ? `3px solid ${COLORS.primary}` : '3px solid transparent',
                fontWeight: isActive ? 600 : 400,
                fontSize: 14, color: COLORS.text,
                transition: 'background 0.15s',
              }}
              onMouseEnter={e => { if (!isActive) (e.currentTarget.style.background = COLORS.hoverBg); }}
              onMouseLeave={e => { if (!isActive) (e.currentTarget.style.background = 'transparent'); }}
            >
              <span style={{ color: isActive ? COLORS.primary : COLORS.secondary, display: 'flex' }}>
                <SidebarIcon icon={sl.icon} />
              </span>
              <div style={{ flex: 1 }}>
                <div style={{ color: isActive && sl.id === 'my-day' ? COLORS.primary : COLORS.text }}>
                  {sl.name}
                </div>
                {sl.id === 'my-day' && isActive && (
                  <div style={{ fontSize: 12, color: COLORS.secondary, marginTop: 2 }}>
                    {dateStr}
                  </div>
                )}
              </div>
              {count > 0 && (
                <span aria-label={`${count} pendientes`} style={{ fontSize: 13, color: COLORS.text, minWidth: 20, textAlign: 'right' }}>
                  {count}
                </span>
              )}
            </div>
          );
        })}

        {/* Separator */}
        <div style={{ height: 1, background: COLORS.border, margin: '8px 16px' }} />

        {children}
      </div>

      {pie}
    </div>
  );
}
