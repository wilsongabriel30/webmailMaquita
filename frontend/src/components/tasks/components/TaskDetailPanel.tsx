import React, { useState, useEffect } from 'react';
import type { Task } from '../types';
import { COLORS } from '../types';

interface Props {
  task: Task;
  onUpdate: (id: string, data: Partial<Task>) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}

const RECURRENCE_OPTIONS = [
  { value: '', label: 'No repetir' },
  { value: 'daily', label: 'Diariamente' },
  { value: 'weekdays', label: 'Días laborables' },
  { value: 'weekly', label: 'Semanalmente' },
  { value: 'monthly', label: 'Mensualmente' },
  { value: 'yearly', label: 'Anualmente' },
];

const REMINDER_PRESETS = [
  { label: 'Hoy', offset: 0 },
  { label: 'Mañana 9:00', offset: 1 },
  { label: 'Próximo lunes 9:00', offset: -1 },
];

function formatReminder(r?: string) {
  if (!r) return '';
  const d = new Date(r);
  if (isNaN(d.getTime())) return '';
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const rDate = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diff = Math.round((rDate.getTime() - today.getTime()) / 86400000);
  const time = d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
  if (diff === 0) return `Hoy a las ${time}`;
  if (diff === 1) return `Mañana a las ${time}`;
  if (diff === -1) return `Ayer a las ${time}`;
  return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' }) + ` a las ${time}`;
}

function recurrenceLabel(r?: string) {
  const opt = RECURRENCE_OPTIONS.find(o => o.value === r);
  return opt ? opt.label : '';
}

export function TaskDetailPanel({ task, onUpdate, onDelete, onClose }: Props) {
  const [title, setTitle] = useState(task.title);
  const [notes, setNotes] = useState(task.note || '');
  const [dueDate, setDueDate] = useState((task.due_date || '').slice(0, 10));
  const [showReminder, setShowReminder] = useState(false);
  const [showRecurrence, setShowRecurrence] = useState(false);
  const [customReminder, setCustomReminder] = useState('');

  const isMailTask = task.id.startsWith('mail-');

  useEffect(() => {
    setTitle(task.title);
    setNotes(task.note || '');
    setDueDate((task.due_date || '').slice(0, 10));
  }, [task.id, task.title, task.note, task.due_date]);

  const saveTitle = () => {
    if (title.trim() && title !== task.title) {
      onUpdate(task.id, { title: title.trim() });
    }
  };

  const saveNotes = () => {
    if (notes !== (task.note || '')) {
      onUpdate(task.id, { note: notes });
    }
  };

  const setReminder = (dateStr: string) => {
    onUpdate(task.id, { reminder: dateStr || undefined } as any);
    setShowReminder(false);
    setCustomReminder('');
  };

  const setReminderPreset = (offset: number) => {
    const now = new Date();
    let target: Date;
    if (offset === 0) {
      // Today in 3 hours
      target = new Date(now.getTime() + 3 * 3600000);
    } else if (offset === 1) {
      // Tomorrow 9:00
      target = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 9, 0);
    } else {
      // Next monday 9:00
      const day = now.getDay();
      const daysUntilMon = day === 0 ? 1 : (8 - day);
      target = new Date(now.getFullYear(), now.getMonth(), now.getDate() + daysUntilMon, 9, 0);
    }
    setReminder(target.toISOString());
  };

  const sectionStyle: React.CSSProperties = {
    padding: '12px 20px', borderBottom: `1px solid ${COLORS.border}`,
    display: 'flex', alignItems: 'center', gap: 12, fontSize: 14,
    color: COLORS.text, cursor: 'pointer', position: 'relative',
  };

  return (
    <div style={{
      width: 360, minWidth: 360, background: 'white', borderLeft: `1px solid ${COLORS.border}`,
      display: 'flex', flexDirection: 'column', height: '100%',
      fontFamily: "'Segoe UI', system-ui, sans-serif",
      boxShadow: '-2px 0 8px rgba(0,0,0,0.05)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', padding: '12px 20px', borderBottom: `1px solid ${COLORS.border}` }}>
        <div style={{ flex: 1, fontWeight: 600, fontSize: 14 }}>
          {isMailTask ? 'Correo marcado' : 'Detalles de la tarea'}
        </div>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', cursor: 'pointer', fontSize: 18,
          color: COLORS.secondary, padding: '0 4px', lineHeight: 1,
        }}>&times;</button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {/* Title */}
        <div style={{ padding: '16px 20px', borderBottom: `1px solid ${COLORS.border}` }}>
          {isMailTask ? (
            <div style={{ fontSize: 16, fontWeight: 600, color: COLORS.text }}>{task.title}</div>
          ) : (
            <input
              value={title}
              onChange={e => setTitle(e.target.value)}
              onBlur={saveTitle}
              onKeyDown={e => { if (e.key === 'Enter') { saveTitle(); (e.target as HTMLInputElement).blur(); } }}
              style={{
                width: '100%', border: 'none', outline: 'none', fontSize: 16, fontWeight: 600,
                color: task.completed ? COLORS.muted : COLORS.text,
                textDecoration: task.completed ? 'line-through' : 'none',
              }}
            />
          )}
        </div>

        {/* Email info for flagged mail */}
        {isMailTask && task.description && (
          <div style={{ padding: '8px 20px', fontSize: 13, color: COLORS.secondary, borderBottom: `1px solid ${COLORS.border}` }}>
            {task.description}
          </div>
        )}

        {/* Mi día toggle */}
        {!isMailTask && (
          <div
            style={sectionStyle}
            onClick={() => onUpdate(task.id, { my_day: !task.my_day })}
            onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <svg width={18} height={18} viewBox="0 0 24 24" fill={task.my_day ? COLORS.primary : 'none'} stroke={task.my_day ? COLORS.primary : COLORS.secondary} strokeWidth={1.8}>
              <circle cx="12" cy="12" r="5" /><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
            </svg>
            <span style={{ color: task.my_day ? COLORS.primary : COLORS.text }}>
              {task.my_day ? 'Agregado a Mi día' : 'Agregar a Mi día'}
            </span>
          </div>
        )}

        {/* Due date */}
        {!isMailTask && (
          <div style={{ ...sectionStyle, flexDirection: 'column', alignItems: 'flex-start', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%' }}>
              <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={dueDate ? COLORS.primary : COLORS.secondary} strokeWidth={1.8}>
                <rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" />
              </svg>
              <span>{dueDate ? 'Fecha de vencimiento' : 'Agregar fecha de vencimiento'}</span>
              {dueDate && (
                <button onClick={(e) => { e.stopPropagation(); setDueDate(''); onUpdate(task.id, { due_date: null } as any); }}
                  style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: '#d13438', fontSize: 12 }}>
                  Quitar
                </button>
              )}
            </div>
            <input type="date" value={dueDate}
              onChange={e => { setDueDate(e.target.value); onUpdate(task.id, { due_date: e.target.value || undefined }); }}
              style={{ marginLeft: 30, fontSize: 13, border: `1px solid ${COLORS.border}`, borderRadius: 4, padding: '4px 8px', color: COLORS.text }}
            />
          </div>
        )}

        {/* Reminder */}
        {!isMailTask && (
          <div style={{ ...sectionStyle, flexDirection: 'column', alignItems: 'flex-start', gap: 0 }}>
            <div
              style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%' }}
              onClick={() => setShowReminder(!showReminder)}
              onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={task.reminder ? COLORS.primary : COLORS.secondary} strokeWidth={1.8}>
                <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 01-3.46 0" />
              </svg>
              <span style={{ flex: 1, color: task.reminder ? COLORS.primary : COLORS.text }}>
                {task.reminder ? formatReminder(task.reminder) : 'Recordarme'}
              </span>
              {task.reminder && (
                <button onClick={(e) => { e.stopPropagation(); setReminder(''); }}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#d13438', fontSize: 12 }}>
                  Quitar
                </button>
              )}
            </div>
            {showReminder && (
              <div style={{
                marginTop: 8, marginLeft: 30, background: 'white', border: `1px solid ${COLORS.border}`,
                borderRadius: 6, boxShadow: '0 4px 12px rgba(0,0,0,0.15)', padding: 4, width: 220, zIndex: 10,
              }}>
                {REMINDER_PRESETS.map(p => (
                  <div key={p.label} onClick={() => setReminderPreset(p.offset)}
                    style={{ padding: '8px 12px', fontSize: 13, cursor: 'pointer', borderRadius: 4 }}
                    onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                    {p.label}
                  </div>
                ))}
                <div style={{ borderTop: `1px solid ${COLORS.border}`, margin: '4px 0' }} />
                <div style={{ padding: '4px 8px' }}>
                  <input type="datetime-local" value={customReminder}
                    onChange={e => setCustomReminder(e.target.value)}
                    style={{ width: '100%', fontSize: 12, border: `1px solid ${COLORS.border}`, borderRadius: 4, padding: '4px 6px' }}
                  />
                  {customReminder && (
                    <button onClick={() => setReminder(new Date(customReminder).toISOString())}
                      style={{ marginTop: 4, width: '100%', padding: '4px', fontSize: 12, background: COLORS.primary, color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
                      Establecer
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Recurrence */}
        {!isMailTask && (
          <div style={{ ...sectionStyle, flexDirection: 'column', alignItems: 'flex-start', gap: 0 }}>
            <div
              style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%' }}
              onClick={() => setShowRecurrence(!showRecurrence)}
              onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={task.recurrence ? COLORS.primary : COLORS.secondary} strokeWidth={1.8}>
                <polyline points="17 1 21 5 17 9" /><path d="M3 11V9a4 4 0 014-4h14" />
                <polyline points="7 23 3 19 7 15" /><path d="M21 13v2a4 4 0 01-4 4H3" />
              </svg>
              <span style={{ flex: 1, color: task.recurrence ? COLORS.primary : COLORS.text }}>
                {task.recurrence ? recurrenceLabel(task.recurrence) : 'Repetir'}
              </span>
              {task.recurrence && (
                <button onClick={(e) => { e.stopPropagation(); onUpdate(task.id, { recurrence: null } as any); setShowRecurrence(false); }}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#d13438', fontSize: 12 }}>
                  Quitar
                </button>
              )}
            </div>
            {showRecurrence && (
              <div style={{
                marginTop: 8, marginLeft: 30, background: 'white', border: `1px solid ${COLORS.border}`,
                borderRadius: 6, boxShadow: '0 4px 12px rgba(0,0,0,0.15)', padding: 4, width: 200, zIndex: 10,
              }}>
                {RECURRENCE_OPTIONS.map(o => (
                  <div key={o.value}
                    onClick={() => { onUpdate(task.id, { recurrence: o.value || undefined } as any); setShowRecurrence(false); }}
                    style={{
                      padding: '8px 12px', fontSize: 13, cursor: 'pointer', borderRadius: 4,
                      fontWeight: task.recurrence === o.value ? 600 : 400,
                      color: task.recurrence === o.value ? COLORS.primary : COLORS.text,
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                    {o.label}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Notes */}
        {!isMailTask && (
          <div style={{ padding: '16px 20px', borderBottom: `1px solid ${COLORS.border}` }}>
            <textarea
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
        )}

        {/* Created date */}
        {task.created_at && (
          <div style={{ padding: '12px 20px', fontSize: 12, color: COLORS.muted }}>
            {isMailTask ? 'Recibido' : 'Creada'} el {new Date(task.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}
          </div>
        )}
      </div>

      {/* Delete/action button */}
      {!isMailTask && (
        <div style={{ padding: '12px 20px', borderTop: `1px solid ${COLORS.border}` }}>
          <button
            onClick={() => { if (confirm('¿Eliminar esta tarea?')) onDelete(task.id); }}
            style={{
              width: '100%', padding: '8px 16px', fontSize: 13,
              background: 'transparent', border: `1px solid #d13438`,
              color: '#d13438', borderRadius: 4, cursor: 'pointer',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = '#fde7e9'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
          >
            Eliminar tarea
          </button>
        </div>
      )}
    </div>
  );
}
