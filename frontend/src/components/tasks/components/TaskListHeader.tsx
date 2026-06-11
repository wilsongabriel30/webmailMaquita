import { useState } from 'react';
import type { ActiveView } from '../types';
import { SMART_LISTS, COLORS } from '../types';

interface Props {
  activeView: ActiveView;
  customListName?: string;
  sortBy: string;
  onSortChange: (s: string) => void;
}

const SORT_OPTIONS = [
  { value: 'date', label: 'Fecha de vencimiento', icon: 'M3 4h18M3 10h12M3 16h6' },
  { value: 'alpha', label: 'Alfabéticamente', icon: 'M3 4h18M3 10h12M3 16h6' },
  { value: 'important', label: 'Importancia', icon: 'M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z' },
  { value: 'created', label: 'Fecha de creación', icon: 'M3 4h18M3 10h12M3 16h6' },
];

export function TaskListHeader({ activeView, customListName, sortBy, onSortChange }: Props) {
  const [showSort, setShowSort] = useState(false);
  const smart = SMART_LISTS.find(s => s.id === activeView);
  const title = smart ? smart.name : (customListName || 'Tareas');
  const isSmartList = !!smart;

  const today = new Date();
  const dateStrRaw = today.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' });
  const dateStr = dateStrRaw.charAt(0).toUpperCase() + dateStrRaw.slice(1);

  const currentSort = SORT_OPTIONS.find(o => o.value === sortBy);

  return (
    <div style={{
      padding: '20px 24px 12px', display: 'flex', flexDirection: 'column', gap: 8,
      fontFamily: "'Segoe UI', system-ui, sans-serif",
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          aria-label="Alternar panel de listas"
          onClick={() => window.dispatchEvent(new CustomEvent('toggle-tasks-sidebar'))}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, display: 'flex', color: COLORS.secondary }}
        >
          <svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <h1 style={{
          fontSize: 20, fontWeight: 600, margin: 0,
          color: isSmartList ? COLORS.primary : COLORS.text,
        }}>
          {title}
        </h1>
        <div style={{ flex: 1 }} />

        {/* Sort button with dropdown */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setShowSort(!showSort)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 12px', fontSize: 13, color: COLORS.secondary,
              background: 'transparent', border: 'none', cursor: 'pointer', borderRadius: 4,
            }}
            onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
            onMouseLeave={e => { if (!showSort) e.currentTarget.style.background = 'transparent'; }}
          >
            <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M3 6h18M3 12h12M3 18h6" />
            </svg>
            <span>Ordenar</span>
            {currentSort && sortBy !== 'date' && (
              <span style={{ fontSize: 11, color: COLORS.primary, fontWeight: 500 }}>
                ({currentSort.label})
              </span>
            )}
          </button>

          {showSort && (
            <>
              <div style={{ position: 'fixed', inset: 0, zIndex: 99 }} onClick={() => setShowSort(false)} />
              <div style={{
                position: 'absolute', right: 0, top: '100%', marginTop: 4, zIndex: 100,
                background: 'white', border: `1px solid ${COLORS.border}`, borderRadius: 6,
                boxShadow: '0 4px 12px rgba(0,0,0,0.15)', padding: 4, minWidth: 200,
              }}>
                {SORT_OPTIONS.map(opt => (
                  <div key={opt.value}
                    onClick={() => { onSortChange(opt.value); setShowSort(false); }}
                    style={{
                      padding: '8px 12px', fontSize: 13, cursor: 'pointer', borderRadius: 4,
                      display: 'flex', alignItems: 'center', gap: 8,
                      fontWeight: sortBy === opt.value ? 600 : 400,
                      color: sortBy === opt.value ? COLORS.primary : COLORS.text,
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  >
                    {sortBy === opt.value && (
                      <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke={COLORS.primary} strokeWidth={3}>
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    )}
                    <span style={{ marginLeft: sortBy === opt.value ? 0 : 22 }}>{opt.label}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {activeView === 'my-day' && (
        <div style={{ fontSize: 13, color: COLORS.secondary }}>{dateStr}</div>
      )}
    </div>
  );
}
