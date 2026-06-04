import { useState, useRef, useEffect } from 'react';
import { COLORS, type ActiveView } from '../types';

interface Props {
  onAdd: (title: string, dueDate?: string, reminder?: string) => void;
  activeView: ActiveView;
}

export function TaskInput({ onAdd, activeView }: Props) {
  const [title, setTitle] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [reminder, setReminder] = useState('');
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [showReminderPicker, setShowReminderPicker] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const [shake, setShake] = useState(false);

  // Cerrar los selectores al cambiar de vista (evita que persistan en otra pestana)
  useEffect(() => { setShowDatePicker(false); setShowReminderPicker(false); }, [activeView]);

  const handleAdd = () => {
    if (title.trim()) {
      onAdd(title.trim(), dueDate || undefined, reminder || undefined);
      setTitle('');
      setDueDate('');
      setReminder('');
      setShowDatePicker(false);
      setShowReminderPicker(false);
    } else {
      // Si no hay texto, enfocar el input y hacer shake visual
      inputRef.current?.focus();
      setShake(true);
      setTimeout(() => setShake(false), 600);
    }
  };

  const setQuickReminder = (type: string) => {
    const now = new Date();
    let target: Date;
    if (type === 'today') {
      target = new Date(now.getTime() + 3 * 3600000);
    } else if (type === 'tomorrow') {
      target = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 9, 0);
    } else {
      const day = now.getDay();
      const daysUntilMon = day === 0 ? 1 : (8 - day);
      target = new Date(now.getFullYear(), now.getMonth(), now.getDate() + daysUntilMon, 9, 0);
    }
    setReminder(target.toISOString());
    setShowReminderPicker(false);
  };

  return (
    <div style={{
      margin: '0 24px', padding: '12px 16px',
      background: 'white', borderRadius: 4,
      border: `1px solid ${COLORS.border}`,
      fontFamily: "'Segoe UI', system-ui, sans-serif",
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          width: 20, height: 20, borderRadius: '50%',
          border: `1.5px solid ${COLORS.muted}`, flexShrink: 0,
        }} />
        <input
          value={title}
          onChange={e => setTitle(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleAdd(); }}
          placeholder="Escriba aqui y presione Enter o Agregar..."
          ref={inputRef}
          autoFocus
          className={shake ? 'task-input-shake' : ''}
          style={{
            flex: 1, border: 'none', outline: 'none', fontSize: 14,
            color: COLORS.text, background: 'transparent',
          }}
        />
        <button
          onClick={handleAdd}
          style={{
            padding: '6px 16px', fontSize: 13, borderRadius: 4,
            border: title.trim() ? 'none' : `1px solid ${COLORS.border}`,
            background: title.trim() ? COLORS.primary : 'white',
            color: title.trim() ? 'white' : COLORS.muted,
            cursor: title.trim() ? 'pointer' : 'default', fontWeight: 600,
            transition: 'all 0.15s ease',
          }}
        >
          Agregar
        </button>
      </div>

      <div style={{ display: 'flex', gap: 16, marginTop: 8, marginLeft: 32, alignItems: 'center' }}>
        {/* Due date */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => { setShowDatePicker(!showDatePicker); setShowReminderPicker(false); }}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2, display: 'flex', color: dueDate ? COLORS.primary : COLORS.muted }}
            title="Fecha de vencimiento"
          >
            <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
              <rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" />
            </svg>
          </button>
          {showDatePicker && (
            <>
            <div style={{ position: 'fixed', inset: 0, zIndex: 99 }} onClick={() => setShowDatePicker(false)} />
            <div style={{
              position: 'absolute', top: 28, left: 0, zIndex: 100,
              background: 'white', border: `1px solid ${COLORS.border}`,
              borderRadius: 4, boxShadow: '0 2px 8px rgba(0,0,0,0.15)', padding: 8,
            }}>
              <input type="date" value={dueDate}
                onChange={e => { setDueDate(e.target.value); setShowDatePicker(false); }}
                style={{ fontSize: 13, border: `1px solid ${COLORS.border}`, borderRadius: 4, padding: '4px 8px' }}
                autoFocus
              />
            </div>
            </>
          )}
        </div>

        {/* Reminder */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => { setShowReminderPicker(!showReminderPicker); setShowDatePicker(false); }}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2, display: 'flex', color: reminder ? COLORS.primary : COLORS.muted }}
            title="Recordatorio"
          >
            <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
              <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 01-3.46 0" />
            </svg>
          </button>
          {showReminderPicker && (
            <>
            <div style={{ position: 'fixed', inset: 0, zIndex: 99 }} onClick={() => setShowReminderPicker(false)} />
            <div style={{
              position: 'absolute', top: 28, left: 0, zIndex: 100,
              background: 'white', border: `1px solid ${COLORS.border}`,
              borderRadius: 6, boxShadow: '0 4px 12px rgba(0,0,0,0.15)', padding: 4, minWidth: 180,
            }}>
              <div onClick={() => setQuickReminder('today')}
                style={{ padding: '8px 12px', fontSize: 13, cursor: 'pointer', borderRadius: 4 }}
                onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                Hoy (en 3h)
              </div>
              <div onClick={() => setQuickReminder('tomorrow')}
                style={{ padding: '8px 12px', fontSize: 13, cursor: 'pointer', borderRadius: 4 }}
                onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                Mañana 9:00
              </div>
              <div onClick={() => setQuickReminder('monday')}
                style={{ padding: '8px 12px', fontSize: 13, cursor: 'pointer', borderRadius: 4 }}
                onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                Próximo lunes 9:00
              </div>
              <div style={{ borderTop: `1px solid ${COLORS.border}`, margin: '4px 0' }} />
              <div style={{ padding: '4px 8px' }}>
                <input type="datetime-local"
                  onChange={e => { if (e.target.value) { setReminder(new Date(e.target.value).toISOString()); setShowReminderPicker(false); } }}
                  style={{ width: '100%', fontSize: 12, border: `1px solid ${COLORS.border}`, borderRadius: 4, padding: '4px 6px' }}
                />
              </div>
            </div>
            </>
          )}
        </div>

        {/* Repeat - just visual info */}
        <button style={{ background: 'none', border: 'none', cursor: 'default', padding: 2, display: 'flex', color: COLORS.muted }} title="Repetir (configurar en detalles)">
          <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
            <polyline points="17 1 21 5 17 9" /><path d="M3 11V9a4 4 0 014-4h14" />
            <polyline points="7 23 3 19 7 15" /><path d="M21 13v2a4 4 0 01-4 4H3" />
          </svg>
        </button>

        {/* Date/reminder labels */}
        {dueDate && (
          <span style={{ fontSize: 12, color: COLORS.primary, display: 'flex', alignItems: 'center', gap: 4 }}>
            <svg width={10} height={10} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" />
            </svg>
            {new Date(dueDate + 'T00:00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })}
            <button onClick={() => setDueDate('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#d13438', fontSize: 10, padding: 0 }}>&times;</button>
          </span>
        )}
        {reminder && (
          <span style={{ fontSize: 12, color: COLORS.primary, display: 'flex', alignItems: 'center', gap: 4 }}>
            <svg width={10} height={10} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" />
            </svg>
            Recordatorio
            <button onClick={() => setReminder('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#d13438', fontSize: 10, padding: 0 }}>&times;</button>
          </span>
        )}
      </div>
    </div>
  );
}

// Inyectar CSS de animacion shake
if (typeof document !== 'undefined' && !document.getElementById('task-input-shake-style')) {
  const style = document.createElement('style');
  style.id = 'task-input-shake-style';
  style.textContent = `
    @keyframes task-shake { 0%,100%{transform:translateX(0)} 20%{transform:translateX(-6px)} 40%{transform:translateX(6px)} 60%{transform:translateX(-4px)} 80%{transform:translateX(4px)} }
    .task-input-shake { animation: task-shake 0.4s ease-in-out; border-bottom: 2px solid #d13438 !important; }
  `;
  document.head.appendChild(style);
}
