import { useState, useEffect } from 'react';
import type { CSSProperties } from 'react';
import { api } from '../../api/client';

interface CustomField {
  id: number;
  field_name: string;
  field_type: string;
  created_at: string;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

const FIELD_TYPES = [
  { value: 'text', label: 'Texto' },
  { value: 'number', label: 'Numero' },
  { value: 'date', label: 'Fecha' },
  { value: 'url', label: 'URL' },
  { value: 'email', label: 'Email' },
];

export function CustomFieldsManager({ isOpen, onClose }: Props) {
  const [fields, setFields] = useState<CustomField[]>([]);
  const [loading, setLoading] = useState(false);
  const [newName, setNewName] = useState('');
  const [newType, setNewType] = useState('text');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen) loadFields();
  }, [isOpen]);

  const loadFields = async () => {
    setLoading(true);
    try {
      const data = await api.get<CustomField[]>('/contacts/custom-fields');
      setFields(data);
    } catch { /* ignore */ }
    setLoading(false);
  };

  const handleAdd = async () => {
    if (!newName.trim()) return;
    setSaving(true);
    setError('');
    try {
      const created = await api.post<CustomField>('/contacts/custom-fields', {
        field_name: newName.trim(),
        field_type: newType,
      });
      setFields(prev => [...prev, created]);
      setNewName('');
      setNewType('text');
    } catch (e: any) {
      setError(e?.message || 'Error al crear campo');
    }
    setSaving(false);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Eliminar este campo y todos sus valores?')) return;
    try {
      await api.del(`/contacts/custom-fields/${id}`);
      setFields(prev => prev.filter(f => f.id !== id));
    } catch { /* ignore */ }
  };

  if (!isOpen) return null;

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={e => e.stopPropagation()}>
        <div style={styles.header}>
          <h2 style={styles.title}>Campos personalizados</h2>
          <button onClick={onClose} style={styles.closeBtn}>{'\u00D7'}</button>
        </div>

        <div style={styles.body}>
          {error && <div style={styles.error}>{error}</div>}

          {/* Add new field form */}
          <div style={styles.addForm}>
            <input
              type="text"
              placeholder="Nombre del campo"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              style={styles.input}
              onKeyDown={e => e.key === 'Enter' && handleAdd()}
            />
            <select value={newType} onChange={e => setNewType(e.target.value)} style={styles.select}>
              {FIELD_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
            <button onClick={handleAdd} disabled={saving || !newName.trim()} style={styles.addBtn}>
              {saving ? '...' : 'Agregar'}
            </button>
          </div>

          {/* Existing fields table */}
          {loading ? (
            <div style={styles.center}>Cargando...</div>
          ) : fields.length === 0 ? (
            <div style={styles.center}>No hay campos personalizados. Crea uno arriba.</div>
          ) : (
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Campo</th>
                  <th style={styles.th}>Tipo</th>
                  <th style={{ ...styles.th, width: 60 }}></th>
                </tr>
              </thead>
              <tbody>
                {fields.map(f => (
                  <tr key={f.id}>
                    <td style={styles.td}>{f.field_name}</td>
                    <td style={styles.td}>
                      <span style={styles.typeBadge}>
                        {FIELD_TYPES.find(t => t.value === f.field_type)?.label || f.field_type}
                      </span>
                    </td>
                    <td style={styles.td}>
                      <button onClick={() => handleDelete(f.id)} style={styles.deleteBtn} title="Eliminar">
                        {'\u00D7'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}


/* --- Sub-components for ContactDetail and ContactForm integration --- */

interface CustomValue {
  id: number;
  field_id: number;
  field_name: string;
  field_type: string;
  value: string;
}

/** Read-only display of custom field values for ContactDetail */
export function CustomFieldsDisplay({ contactId }: { contactId: number }) {
  const [values, setValues] = useState<CustomValue[]>([]);

  useEffect(() => {
    api.get<CustomValue[]>(`/contacts/${contactId}/custom-values`).then(setValues).catch(() => {});
  }, [contactId]);

  if (values.length === 0) return null;

  return (
    <div style={{ marginBottom: 24 }}>
      <h4 style={{
        fontSize: 13, fontWeight: 600, color: '#605e5c', margin: '0 0 12px',
        textTransform: 'uppercase', letterSpacing: 0.5,
      }}>
        Campos personalizados
      </h4>
      {values.map(v => (
        <div key={v.id} style={{ display: 'flex', gap: 12, marginBottom: 10 }}>
          <div style={{ fontSize: 12, color: '#a19f9d', minWidth: 100 }}>{v.field_name}</div>
          <div style={{ fontSize: 14, color: '#323130' }}>
            {v.field_type === 'url' ? (
              <a href={v.value} target="_blank" rel="noreferrer" style={{ color: '#0078d4', textDecoration: 'none' }}>{v.value}</a>
            ) : v.field_type === 'email' ? (
              <a href={`mailto:${v.value}`} style={{ color: '#0078d4', textDecoration: 'none' }}>{v.value}</a>
            ) : v.value}
          </div>
        </div>
      ))}
    </div>
  );
}

/** Editable custom fields for ContactForm */
export function CustomFieldsEditor({ contactId }: { contactId: number }) {
  const [fields, setFields] = useState<CustomField[]>([]);
  const [values, setValues] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get<CustomField[]>('/contacts/custom-fields'),
      contactId ? api.get<CustomValue[]>(`/contacts/${contactId}/custom-values`) : Promise.resolve([] as CustomValue[]),
    ]).then(([f, v]) => {
      setFields(f);
      const map: Record<number, string> = {};
      (v as CustomValue[]).forEach((cv) => { map[cv.field_id] = cv.value; });
      setValues(map);
    }).catch(() => {});
  }, [contactId]);

  const handleSave = async () => {
    if (!contactId) return;
    setSaving(true);
    try {
      await api.put(`/contacts/${contactId}/custom-values`, values);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch { /* ignore */ }
    setSaving(false);
  };

  if (fields.length === 0) return null;

  const getInputType = (ft: string) => {
    switch (ft) {
      case 'number': return 'number';
      case 'date': return 'date';
      case 'url': return 'url';
      case 'email': return 'email';
      default: return 'text';
    }
  };

  return (
    <div style={{ marginTop: 20, borderTop: '1px solid #edebe9', paddingTop: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h4 style={{
          fontSize: 13, fontWeight: 600, color: '#605e5c', margin: 0,
          textTransform: 'uppercase', letterSpacing: 0.5,
        }}>
          Campos personalizados
        </h4>
        <button onClick={handleSave} disabled={saving} style={{
          padding: '4px 12px', background: saved ? '#498205' : '#0078d4', color: '#fff',
          border: 'none', borderRadius: 4, fontSize: 12, cursor: 'pointer',
        }}>
          {saving ? 'Guardando...' : saved ? 'Guardado' : 'Guardar campos'}
        </button>
      </div>
      {fields.map(f => (
        <div key={f.id} style={{ marginBottom: 10 }}>
          <label style={{ display: 'block', fontSize: 12, color: '#605e5c', marginBottom: 4 }}>
            {f.field_name}
          </label>
          <input
            type={getInputType(f.field_type)}
            value={values[f.id] || ''}
            onChange={e => setValues(prev => ({ ...prev, [f.id]: e.target.value }))}
            style={{
              width: '100%', padding: '6px 10px', border: '1px solid #c8c6c4',
              borderRadius: 4, fontSize: 13, boxSizing: 'border-box' as const,
              fontFamily: "'Segoe UI', sans-serif",
            }}
            placeholder={`Ingrese ${f.field_name.toLowerCase()}`}
          />
        </div>
      ))}
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
    background: '#fff', borderRadius: 8, width: 520, maxHeight: '80vh',
    display: 'flex', flexDirection: 'column',
    boxShadow: '0 25px 65px rgba(0,0,0,0.3)',
  },
  header: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '16px 20px', borderBottom: '1px solid #edebe9',
  },
  title: { margin: 0, fontSize: 18, fontWeight: 600, color: '#323130' },
  closeBtn: {
    border: 'none', background: 'none', fontSize: 22, cursor: 'pointer',
    color: '#605e5c', padding: '4px 8px',
  },
  body: { padding: 20, overflowY: 'auto', flex: 1 },
  error: {
    padding: '8px 12px', background: '#fef0f0', color: '#d13438',
    borderRadius: 4, fontSize: 13, marginBottom: 12,
  },
  addForm: { display: 'flex', gap: 8, marginBottom: 20 },
  input: {
    flex: 1, padding: '8px 10px', border: '1px solid #c8c6c4',
    borderRadius: 4, fontSize: 13, fontFamily: "'Segoe UI', sans-serif",
  },
  select: {
    padding: '8px 10px', border: '1px solid #c8c6c4', borderRadius: 4,
    fontSize: 13, fontFamily: "'Segoe UI', sans-serif", background: '#fff',
  },
  addBtn: {
    padding: '8px 16px', background: '#0078d4', color: '#fff', border: 'none',
    borderRadius: 4, fontSize: 13, fontWeight: 600, cursor: 'pointer',
  },
  center: { textAlign: 'center', padding: 30, color: '#a19f9d', fontSize: 13 },
  table: {
    width: '100%', borderCollapse: 'collapse',
  },
  th: {
    textAlign: 'left', padding: '8px 12px', fontSize: 12, fontWeight: 600,
    color: '#605e5c', borderBottom: '2px solid #edebe9',
    textTransform: 'uppercase', letterSpacing: 0.5,
  },
  td: {
    padding: '10px 12px', fontSize: 13, color: '#323130',
    borderBottom: '1px solid #edebe9',
  },
  typeBadge: {
    display: 'inline-block', padding: '2px 8px', borderRadius: 10,
    fontSize: 11, background: '#f3f2f1', color: '#605e5c',
  },
  deleteBtn: {
    border: 'none', background: 'none', color: '#a19f9d', fontSize: 18,
    cursor: 'pointer', padding: '2px 6px',
  },
};
