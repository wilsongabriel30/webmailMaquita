import React, { useState } from 'react';
import type { TaskList, ActiveView, SmartView } from '../types';
import { SMART_LISTS, COLORS } from '../types';

interface Props {
  activeView: ActiveView;
  onViewChange: (v: ActiveView) => void;
  customLists: TaskList[];
  onCreateList: (name: string) => void;
  onDeleteList: (id: string) => void;
  smartCounts: Record<string, number>;
}

function SidebarIcon({ icon, size = 18 }: { icon: string; size?: number }) {
  const s = { width: size, height: size };
  switch (icon) {
    case 'sun':
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <circle cx="12" cy="12" r="5" /><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
        </svg>
      );
    case 'star':
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
        </svg>
      );
    case 'calendar':
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" />
        </svg>
      );
    case 'person':
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" /><circle cx="12" cy="7" r="4" />
        </svg>
      );
    case 'flag':
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" /><line x1="4" y1="22" x2="4" y2="15" />
        </svg>
      );
    case 'home':
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" /><polyline points="9 22 9 12 15 12 15 22" />
        </svg>
      );
    case 'list':
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
          <line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
        </svg>
      );
    default:
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <circle cx="12" cy="12" r="10" />
        </svg>
      );
  }
}

export function TasksSidebar({ activeView, onViewChange, customLists, onCreateList, onDeleteList, smartCounts }: Props) {
  const [newListName, setNewListName] = useState('');
  const [showNewList, setShowNewList] = useState(false);
  const [contextMenu, setContextMenu] = useState<{ id: string; x: number; y: number } | null>(null);

  const today = new Date();
  const dateStr = today.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' });

  const handleCreateList = () => {
    if (newListName.trim()) {
      onCreateList(newListName.trim());
      setNewListName('');
      setShowNewList(false);
    }
  };

  const handleContextMenu = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    setContextMenu({ id, x: e.clientX, y: e.clientY });
  };

  return (
    <div
      style={{
        width: 280, minWidth: 280, background: 'white', borderRight: `1px solid ${COLORS.border}`,
        display: 'flex', flexDirection: 'column', height: '100%', userSelect: 'none',
        fontFamily: "'Segoe UI', system-ui, sans-serif",
      }}
      onClick={() => setContextMenu(null)}
    >
      {/* Header */}
      <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12, borderBottom: `1px solid ${COLORS.border}` }}>
        <svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke={COLORS.secondary} strokeWidth={2}>
          <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
        </svg>
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
                  <div style={{ fontSize: 12, color: COLORS.secondary, marginTop: 2, textTransform: 'capitalize' }}>
                    {dateStr}
                  </div>
                )}
              </div>
              {count > 0 && (
                <span style={{ fontSize: 12, color: COLORS.secondary, background: COLORS.hoverBg, borderRadius: 10, padding: '1px 8px', minWidth: 20, textAlign: 'center' }}>
                  {count}
                </span>
              )}
            </div>
          );
        })}

        {/* Separator */}
        <div style={{ height: 1, background: COLORS.border, margin: '8px 16px' }} />

        {/* Custom lists */}
        {customLists.map(cl => {
          const isActive = activeView === cl.id;
          return (
            <div
              key={cl.id}
              onClick={() => onViewChange(cl.id)}
              onContextMenu={e => handleContextMenu(e, cl.id)}
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
              <span style={{ color: COLORS.secondary, display: 'flex' }}><SidebarIcon icon="list" /></span>
              <span style={{ flex: 1 }}>{cl.name}</span>
              {cl.task_count > 0 && (
                <span style={{ fontSize: 12, color: COLORS.secondary }}>{cl.task_count}</span>
              )}
            </div>
          );
        })}

        {/* Context menu for delete */}
        {contextMenu && (
          <div
            style={{
              position: 'fixed', left: contextMenu.x, top: contextMenu.y, zIndex: 1000,
              background: 'white', border: `1px solid ${COLORS.border}`, borderRadius: 4,
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)', padding: '4px 0',
            }}
          >
            <div
              onClick={() => { onDeleteList(contextMenu.id); setContextMenu(null); }}
              style={{ padding: '8px 16px', fontSize: 13, color: '#d13438', cursor: 'pointer' }}
              onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              Eliminar lista
            </div>
          </div>
        )}
      </div>

      {/* New list button */}
      <div style={{ padding: '12px 16px', borderTop: `1px solid ${COLORS.border}` }}>
        {showNewList ? (
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              autoFocus
              value={newListName}
              onChange={e => setNewListName(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleCreateList(); if (e.key === 'Escape') { setShowNewList(false); setNewListName(''); } }}
              placeholder="Nombre de la lista..."
              style={{
                flex: 1, padding: '6px 10px', fontSize: 13, border: `1px solid ${COLORS.primary}`,
                borderRadius: 4, outline: 'none',
              }}
            />
            <button onClick={handleCreateList} style={{
              padding: '6px 12px', fontSize: 13, background: COLORS.primary, color: 'white',
              border: 'none', borderRadius: 4, cursor: 'pointer',
            }}>
              OK
            </button>
          </div>
        ) : (
          <div
            onClick={() => setShowNewList(true)}
            style={{ display: 'flex', alignItems: 'center', gap: 8, color: COLORS.primary, fontSize: 14, cursor: 'pointer', fontWeight: 500 }}
          >
            <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Nueva lista
          </div>
        )}
      </div>
    </div>
  );
}
