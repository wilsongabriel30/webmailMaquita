import { useState, useEffect } from 'react';
import type { CSSProperties } from 'react';
import { api } from '../../api/client';

interface Reminder {
  id: number;
  contact_id: number;
  title: string;
  description: string;
  due_date: string;
  completed: boolean;
  created_at: string;
}

interface Props {
  contactId: number;
}

export function RemindersPanel({ contactId }: Props) {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadReminders();
  }, [contactId]);

  const loadReminders = async () => {
    try {
      const data = await api.get<Reminder[]>(`/contacts/${contactId}/reminders`);
      setReminders(data);
    } catch { /* ignore */ }
  };

  const handleAdd = async () => {
    if (!title.trim() || !dueDate) return;
    setSaving(true);
    try {
      const r = await api.post<Reminder>(`/contacts/${contactId}/reminders`, {
        title: title.trim(),
        due_date: new Date(dueDate).toISOString(),
      });
      setReminders(prev => [...prev, r]);
      setTitle('');
      setDueDate('');
      setShowForm(false);
    } catch { /* ignore */ }
    setSaving(false);
  };

  const handleComplete = async (id: number) => {
    try {
      const updated = await api.put<Reminder>(`/contacts/reminders/${id}/complete`);
      setReminders(prev => prev.map(r => r.id === id ? updated : r));
    } catch { /* ignore */ }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.del(`/contacts/reminders/${id}`);
      setReminders(prev => prev.filter(r => r.id !== id));
    } catch { /* ignore */ }
  };

  const isOverdue = (dateStr: string) => {
    return new Date(dateStr) < new Date() ;
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('es-EC', {
      day: '2-digit', month: 'short', year: 'numeric',
    });
  };

  return (
    <div style={styles.container}>
      <div style={styles.header} onClick={() => setCollapsed(!collapsed)}>
        <span style={styles.headerTitle}>
          Recordatorios ({reminders.length})
        </span>
        <span style={{ ...styles.chevron, transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }}>
          {'\u25BC'}
        </span>
      </div>

      {!collapsed && (
        <div style={styles.content}>
          {reminders.length === 0 && !showForm && (
            <div style={styles.empty}>Sin recordatorios</div>
          )}

          {reminders.map(r => (
            <div
              key={r.id}
              style={{
                ...styles.reminderItem,
                ...(r.completed ? styles.completedItem : {}),
                ...(!r.completed && isOverdue(r.due_date) ? styles.overdueItem : {}),
              }}
            >
              <input
                type="checkbox"
                checked={r.completed}
                onChange={() => handleComplete(r.id)}
                style={styles.checkbox}
              />
              <div style={{ flex: 1 }}>
                <div style={{
                  fontSize: 13,
                  color: r.completed ? '#a19f9d' : '#323130',
                  textDecoration: r.completed ? 'line-through' : 'none',
                  fontWeight: 500,
                }}>
                  {r.title}
                </div>
                <div style={{
                  fontSize: 11,
                  color: !r.completed && isOverdue(r.due_date) ? '#d13438' : '#a19f9d',
                  marginTop: 2,
                }}>
                  {formatDate(r.due_date)}
                  {!r.completed && isOverdue(r.due_date) && ' - Vencido'}
                </div>
              </div>
              <button
                onClick={() => handleDelete(r.id)}
                style={styles.deleteBtn}
                title="Eliminar"
              >
                {'\u00D7'}
              </button>
            </div>
          ))}

          {showForm ? (
            <div style={styles.form}>
              <input
                type="text"
                placeholder="Titulo del recordatorio"
                value={title}
                onChange={e => setTitle(e.target.value)}
                style={styles.input}
                autoFocus
              />
              <input
                type="datetime-local"
                value={dueDate}
                onChange={e => setDueDate(e.target.value)}
                style={styles.input}
              />
              <div style={styles.formActions}>
                <button onClick={handleAdd} disabled={saving || !title.trim() || !dueDate} style={styles.saveBtn}>
                  {saving ? 'Guardando...' : 'Guardar'}
                </button>
                <button onClick={() => { setShowForm(false); setTitle(''); setDueDate(''); }} style={styles.cancelBtn}>
                  Cancelar
                </button>
              </div>
            </div>
          ) : (
            <button onClick={() => setShowForm(true)} style={styles.addBtn}>
              + Agregar recordatorio
            </button>
          )}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  container: {
    fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
    color: '#323130',
    border: '1px solid #edebe9',
    borderRadius: 4,
    marginTop: 12,
  },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '10px 14px', cursor: 'pointer', backgroundColor: '#faf9f8',
    borderBottom: '1px solid #edebe9', userSelect: 'none' as const,
  },
  headerTitle: { fontWeight: 600, fontSize: 14, color: '#0078d4' },
  chevron: { fontSize: 12, color: '#605e5c', transition: 'transform 0.2s' },
  content: { padding: 14 },
  empty: { fontSize: 13, color: '#a19f9d', textAlign: 'center', padding: 12 },
  reminderItem: {
    display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px',
    borderRadius: 4, marginBottom: 6, border: '1px solid #edebe9',
    backgroundColor: '#fff',
  },
  completedItem: { opacity: 0.6, backgroundColor: '#faf9f8' },
  overdueItem: { borderColor: '#d13438', backgroundColor: '#fef0f0' },
  checkbox: { cursor: 'pointer', width: 16, height: 16 },
  deleteBtn: {
    border: 'none', background: 'none', color: '#a19f9d', fontSize: 18,
    cursor: 'pointer', padding: '2px 6px', borderRadius: 4,
  },
  form: { marginTop: 8 },
  input: {
    width: '100%', padding: '8px 10px', border: '1px solid #c8c6c4',
    borderRadius: 4, fontSize: 13, marginBottom: 8, boxSizing: 'border-box' as const,
    fontFamily: "'Segoe UI', sans-serif",
  },
  formActions: { display: 'flex', gap: 8 },
  saveBtn: {
    padding: '6px 16px', background: '#0078d4', color: '#fff', border: 'none',
    borderRadius: 4, fontSize: 13, fontWeight: 600, cursor: 'pointer',
  },
  cancelBtn: {
    padding: '6px 16px', background: 'transparent', color: '#605e5c',
    border: '1px solid #c8c6c4', borderRadius: 4, fontSize: 13, cursor: 'pointer',
  },
  addBtn: {
    marginTop: 8, padding: '6px 12px', background: 'transparent',
    color: '#0078d4', border: '1px dashed #0078d4', borderRadius: 4,
    fontSize: 13, cursor: 'pointer', width: '100%',
  },
};
