import type { ReactNode } from 'react';
import type { ActiveView } from '../types';
import { SMART_LISTS, COLORS } from '../types';
import { SidebarIcon } from './IconoBarra';

interface Props {
  activeView: ActiveView;
  onViewChange: (v: ActiveView) => void;
  smartCounts: Record<string, number>;
  /** Listas propias y grupos (MisListas), debajo de las listas inteligentes. */
  children?: ReactNode;
  /** Pie fijo: los botones «Nueva lista» y «Nuevo grupo». */
  pie?: ReactNode;
}

export function TasksSidebar({ activeView, onViewChange, smartCounts, children, pie }: Props) {
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
      </div>

      {/* Smart lists */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        {SMART_LISTS.map(sl => {
          const isActive = activeView === sl.id;
          const count = smartCounts[sl.id] || 0;
          return (
            <div
              key={sl.id}
              onClick={() => onViewChange(sl.id)}
              style={{
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
