import { useState, useEffect } from 'react';
import type { CSSProperties } from 'react';
import { api } from '../../api/client';

interface SharedNote {
  id: number;
  contact_id: number | null;
  org_contact_id: number | null;
  author: string;
  content: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

interface Props {
  contactId: number;
  orgContactId?: number;
}

export function SharedNotesPanel({ contactId, orgContactId }: Props) {
  const [notes, setNotes] = useState<SharedNote[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [content, setContent] = useState('');
  const [tags, setTags] = useState('');
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  useEffect(() => {
    loadNotes();
  }, [contactId, orgContactId]);

  const loadNotes = async () => {
    try {
      const endpoint = orgContactId
        ? `/contacts/directory/${orgContactId}/shared-notes`
        : `/contacts/${contactId}/shared-notes`;
      const data = await api.get<SharedNote[]>(endpoint);
      setNotes(data);
    } catch { /* ignore */ }
  };

  const handleSave = async () => {
    if (!content.trim()) return;
    setSaving(true);
    try {
      const tagList = tags.split(',').map(t => t.trim()).filter(Boolean);
      if (editingId) {
        const updated = await api.put<SharedNote>(`/contacts/shared-notes/${editingId}`, {
          content: content.trim(),
          tags: tagList,
        });
        setNotes(prev => prev.map(n => n.id === editingId ? updated : n));
      } else {
        const created = await api.post<SharedNote>('/contacts/shared-notes', {
          content: content.trim(),
          tags: tagList,
          contact_id: orgContactId ? null : contactId,
          org_contact_id: orgContactId || null,
        });
        setNotes(prev => [created, ...prev]);
      }
      setContent('');
      setTags('');
      setShowForm(false);
      setEditingId(null);
    } catch (e: any) {
      alert(e?.message || 'Error al guardar nota');
    }
    setSaving(false);
  };

  const handleDelete = async (id: number) => {
    try {
      await api.del(`/contacts/shared-notes/${id}`);
      setNotes(prev => prev.filter(n => n.id !== id));
    } catch { /* ignore */ }
  };

  const startEdit = (note: SharedNote) => {
    setContent(note.content);
    setTags(note.tags.join(', '));
    setEditingId(note.id);
    setShowForm(true);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('es-EC', {
      day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  };

  return (
    <div style={styles.container}>
      <div style={styles.header} onClick={() => setCollapsed(!collapsed)}>
        <span style={styles.headerTitle}>
          Notas compartidas ({notes.length})
        </span>
        <span style={{ ...styles.chevron, transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }}>
          {'\u25BC'}
        </span>
      </div>

      {!collapsed && (
        <div style={styles.body}>
          {showForm ? (
            <div style={styles.form}>
              <textarea
                value={content}
                onChange={e => setContent(e.target.value)}
                placeholder="Escribir nota compartida..."
                style={styles.textarea}
                rows={3}
                autoFocus
              />
              <input
                type="text"
                value={tags}
                onChange={e => setTags(e.target.value)}
                placeholder="Etiquetas separadas por coma"
                style={styles.input}
              />
              <div style={styles.formActions}>
                <button onClick={handleSave} disabled={saving || !content.trim()} style={styles.saveBtn}>
                  {saving ? 'Guardando...' : editingId ? 'Actualizar' : 'Publicar'}
                </button>
                <button onClick={() => { setShowForm(false); setContent(''); setTags(''); setEditingId(null); }} style={styles.cancelBtn}>
                  Cancelar
                </button>
              </div>
            </div>
          ) : (
            <button onClick={() => setShowForm(true)} style={styles.addBtn}>
              + Agregar nota
            </button>
          )}

          {notes.length === 0 && !showForm && (
            <div style={styles.empty}>Sin notas compartidas</div>
          )}

          {notes.map(note => (
            <div key={note.id} style={styles.noteItem}>
              <div style={styles.noteMeta}>
                <span style={styles.noteAuthor}>{note.author}</span>
                <span style={styles.noteDate}>{formatDate(note.created_at)}</span>
              </div>
              <div style={styles.noteContent}>{note.content}</div>
              {note.tags.length > 0 && (
                <div style={styles.tagRow}>
                  {note.tags.map((tag, i) => (
                    <span key={i} style={styles.tag}>{tag}</span>
                  ))}
                </div>
              )}
              <div style={styles.noteActions}>
                <button onClick={() => startEdit(note)} style={styles.actionLink}>Editar</button>
                <button onClick={() => handleDelete(note.id)} style={styles.actionLink}>Eliminar</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  container: {
    fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
    color: '#323130', border: '1px solid #edebe9', borderRadius: 4, marginTop: 12,
  },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '10px 14px', cursor: 'pointer', backgroundColor: '#faf9f8',
    borderBottom: '1px solid #edebe9', userSelect: 'none',
  },
  headerTitle: { fontWeight: 600, fontSize: 14, color: '#0078d4' },
  chevron: { fontSize: 12, color: '#605e5c', transition: 'transform 0.2s' },
  body: { padding: 14 },
  empty: { fontSize: 13, color: '#a19f9d', textAlign: 'center', padding: 12 },
  form: { marginBottom: 12 },
  textarea: {
    width: '100%', padding: '8px 10px', border: '1px solid #c8c6c4', borderRadius: 4,
    fontSize: 13, fontFamily: "'Segoe UI', sans-serif", resize: 'vertical',
    boxSizing: 'border-box',
  },
  input: {
    width: '100%', padding: '6px 10px', border: '1px solid #c8c6c4', borderRadius: 4,
    fontSize: 12, fontFamily: "'Segoe UI', sans-serif", marginTop: 6, boxSizing: 'border-box',
  },
  formActions: { display: 'flex', gap: 8, marginTop: 8 },
  saveBtn: {
    padding: '6px 16px', background: '#0078d4', color: '#fff', border: 'none',
    borderRadius: 4, fontSize: 13, fontWeight: 600, cursor: 'pointer',
  },
  cancelBtn: {
    padding: '6px 16px', background: 'transparent', color: '#605e5c',
    border: '1px solid #c8c6c4', borderRadius: 4, fontSize: 13, cursor: 'pointer',
  },
  addBtn: {
    marginBottom: 12, padding: '6px 12px', background: 'transparent',
    color: '#0078d4', border: '1px dashed #0078d4', borderRadius: 4,
    fontSize: 13, cursor: 'pointer', width: '100%',
  },
  noteItem: {
    padding: '10px 12px', borderRadius: 4, marginBottom: 8,
    border: '1px solid #edebe9', backgroundColor: '#faf9f8',
  },
  noteMeta: {
    display: 'flex', justifyContent: 'space-between', marginBottom: 6,
  },
  noteAuthor: { fontSize: 12, fontWeight: 600, color: '#0078d4' },
  noteDate: { fontSize: 11, color: '#a19f9d' },
  noteContent: { fontSize: 13, color: '#323130', lineHeight: 1.5, whiteSpace: 'pre-wrap' },
  tagRow: { display: 'flex', gap: 4, marginTop: 8, flexWrap: 'wrap' },
  tag: {
    display: 'inline-block', padding: '2px 8px', borderRadius: 10,
    fontSize: 11, background: '#e1dfdd', color: '#605e5c',
  },
  noteActions: { display: 'flex', gap: 12, marginTop: 8 },
  actionLink: {
    border: 'none', background: 'none', color: '#0078d4', fontSize: 12,
    cursor: 'pointer', padding: 0, textDecoration: 'underline',
  },
};
