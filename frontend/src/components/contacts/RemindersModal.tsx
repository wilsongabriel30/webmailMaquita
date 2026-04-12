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
  contact_name: string;
  contact_email: string;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onNavigateToContact?: (contactId: number) => void;
}

export function RemindersModal({ isOpen, onClose, onNavigateToContact }: Props) {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen) loadReminders();
  }, [isOpen]);

  const loadReminders = async () => {
    setLoading(true);
    try {
      const data = await api.get<Reminder[]>('/contacts/reminders');
      setReminders(data.filter((r) => !r.completed));
    } catch { /* ignore */ }
    setLoading(false);
  };

  const handleComplete = async (id: number) => {
    try {
      await api.put(`/contacts/reminders/${id}/complete`);
      setReminders(prev => prev.filter(r => r.id !== id));
    } catch { /* ignore */ }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.del(`/contacts/reminders/${id}`);
      setReminders(prev => prev.filter(r => r.id !== id));
    } catch { /* ignore */ }
  };

  if (!isOpen) return null;

  const now = new Date();
  const todayStr = now.toDateString();
  const weekEnd = new Date(now);
  weekEnd.setDate(weekEnd.getDate() + 7);

  const overdue: Reminder[] = [];
  const today: Reminder[] = [];
  const thisWeek: Reminder[] = [];
  const later: Reminder[] = [];

  reminders.forEach(r => {
    const d = new Date(r.due_date);
    if (d < now && d.toDateString() !== todayStr) {
      overdue.push(r);
    } else if (d.toDateString() === todayStr) {
      today.push(r);
    } else if (d <= weekEnd) {
      thisWeek.push(r);
    } else {
      later.push(r);
    }
  });

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('es-EC', {
      day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  };

  const renderGroup = (groupTitle: string, items: Reminder[], isOverdue = false) => {
    if (items.length === 0) return null;
    return (
      <div style={{ marginBottom: 20 }}>
        <div style={{
          fontSize: 13, fontWeight: 700, color: isOverdue ? '#d13438' : '#0078d4',
          marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5,
        }}>
          {groupTitle} ({items.length})
        </div>
        {items.map(r => (
          <div key={r.id} style={{
            ...styles.item,
            ...(isOverdue ? { borderLeft: '3px solid #d13438', backgroundColor: '#fef0f0' } : {}),
          }}>
            <div style={{ flex: 1 }}>
              <div style={styles.reminderTitle}>{r.title}</div>
              <div style={styles.contactLink}
                onClick={() => onNavigateToContact?.(r.contact_id)}
              >
                {r.contact_name || r.contact_email}
              </div>
              <div style={{
                fontSize: 11,
                color: isOverdue ? '#d13438' : '#a19f9d',
                marginTop: 2,
              }}>
                {formatDate(r.due_date)}
              </div>
            </div>
            <div style={styles.actions}>
              <button onClick={() => handleComplete(r.id)} style={styles.completeBtn} title="Completar">
                {'\u2713'}
              </button>
              <button onClick={() => handleDelete(r.id)} style={styles.deleteBtn} title="Eliminar">
                {'\u00D7'}
              </button>
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={e => e.stopPropagation()}>
        <div style={styles.header}>
          <h2 style={styles.titleText}>Todos los recordatorios</h2>
          <button onClick={onClose} style={styles.closeBtn}>{'\u00D7'}</button>
        </div>

        <div style={styles.body}>
          {loading && <div style={styles.center}>Cargando recordatorios...</div>}

          {!loading && reminders.length === 0 && (
            <div style={styles.center}>No hay recordatorios pendientes.</div>
          )}

          {!loading && (
            <>
              {renderGroup('Vencidos', overdue, true)}
              {renderGroup('Hoy', today)}
              {renderGroup('Esta semana', thisWeek)}
              {renderGroup('Mas adelante', later)}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  overlay: {
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.4)', display: 'flex',
    alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  },
  modal: {
    background: '#fff', borderRadius: 8, width: 560, maxHeight: '80vh',
    display: 'flex', flexDirection: 'column',
    boxShadow: '0 25px 65px rgba(0,0,0,0.3)',
  },
  header: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '16px 20px', borderBottom: '1px solid #edebe9',
  },
  titleText: { margin: 0, fontSize: 18, fontWeight: 600, color: '#323130' },
  closeBtn: {
    border: 'none', background: 'none', fontSize: 22, cursor: 'pointer',
    color: '#605e5c', padding: '4px 8px',
  },
  body: { padding: 20, overflowY: 'auto', flex: 1 },
  center: { textAlign: 'center', padding: 40, color: '#605e5c', fontSize: 14 },
  item: {
    display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px',
    borderRadius: 4, marginBottom: 6, border: '1px solid #edebe9',
    backgroundColor: '#fff',
  },
  reminderTitle: { fontSize: 14, fontWeight: 600, color: '#323130' },
  contactLink: {
    fontSize: 12, color: '#0078d4', cursor: 'pointer', marginTop: 2,
  },
  actions: { display: 'flex', gap: 4 },
  completeBtn: {
    border: '1px solid #498205', background: '#fff', color: '#498205',
    fontSize: 14, cursor: 'pointer', padding: '4px 8px', borderRadius: 4,
    fontWeight: 700,
  },
  deleteBtn: {
    border: '1px solid #c8c6c4', background: '#fff', color: '#a19f9d',
    fontSize: 16, cursor: 'pointer', padding: '4px 8px', borderRadius: 4,
  },
};
