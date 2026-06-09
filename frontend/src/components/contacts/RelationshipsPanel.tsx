import { useState, useEffect } from 'react';
import type { CSSProperties } from 'react';
import { api } from '../../api/client';
import { GravatarAvatar } from './GravatarAvatar';

interface Relationship {
  id: number;
  relation_type: string;
  relation_label: string;
  related_id: number;
  display_name: string;
  email: string;
  photo_url: string;
  direction: string;
}

interface ContactOption {
  id: number;
  display_name: string;
  email: string;
}

interface Props {
  contactId: number;
  onNavigateToContact?: (contactId: number) => void;
}

const RELATION_TYPES = [
  { value: 'assistant', label: 'Asistente' },
  { value: 'manager', label: 'Gerente' },
  { value: 'spouse', label: 'Conyuge' },
  { value: 'referral', label: 'Referido' },
  { value: 'partner', label: 'Socio' },
  { value: 'provider', label: 'Proveedor' },
  { value: 'client', label: 'Cliente' },
];

export function RelationshipsPanel({ contactId, onNavigateToContact }: Props) {
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [relationType, setRelationType] = useState('assistant');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<ContactOption[]>([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    loadRelationships();
  }, [contactId]);

  const loadRelationships = async () => {
    try {
      const data = await api.get<Relationship[]>(`/contacts/${contactId}/relationships`);
      setRelationships(data);
    } catch { /* ignore */ }
  };

  const handleSearch = async (q: string) => {
    setSearchQuery(q);
    if (q.length < 2) { setSearchResults([]); return; }
    setSearching(true);
    try {
      const data = await api.get<{ contacts: ContactOption[] }>(`/contacts?search=${encodeURIComponent(q)}&per_page=8`);
      // Filter out current contact
      setSearchResults((data?.contacts || []).filter((c) => c.id && c.id !== contactId));
    } catch { setSearchResults([]); }
    setSearching(false);
  };

  const handleAdd = async (toContactId: number) => {
    try {
      await api.post(`/contacts/${contactId}/relationships`, {
        to_contact_id: toContactId,
        relation_type: relationType,
      });
      await loadRelationships();
      setShowForm(false);
      setSearchQuery('');
      setSearchResults([]);
    } catch { /* ignore */ }
  };

  const handleDelete = async (relId: number) => {
    try {
      await api.del(`/contacts/relationships/${relId}`);
      setRelationships(prev => prev.filter(r => r.id !== relId));
    } catch { /* ignore */ }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header} onClick={() => setCollapsed(!collapsed)}>
        <span style={styles.headerTitle}>
          Relaciones ({relationships.length})
        </span>
        <span style={{ ...styles.chevron, transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }}>
          {'\u25BC'}
        </span>
      </div>

      {!collapsed && (
        <div style={styles.content}>
          {relationships.length === 0 && !showForm && (
            <div style={styles.empty}>Sin relaciones</div>
          )}

          {relationships.map(r => (
            <div key={r.id} style={styles.relItem}>
              <GravatarAvatar name={r.display_name} email={r.email} size={32} />
              <div style={{ flex: 1 }}>
                <div style={styles.relLabel}>{r.relation_label}</div>
                <div
                  style={styles.relName}
                  onClick={() => onNavigateToContact?.(r.related_id)}
                >
                  {r.display_name || r.email}
                </div>
              </div>
              <button onClick={() => handleDelete(r.id)} style={styles.deleteBtn} title="Eliminar">
                {'\u00D7'}
              </button>
            </div>
          ))}

          {showForm ? (
            <div style={styles.form}>
              <select
                value={relationType}
                onChange={e => setRelationType(e.target.value)}
                style={styles.select}
              >
                {RELATION_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
              <input
                type="text"
                placeholder="Buscar contacto..."
                value={searchQuery}
                onChange={e => handleSearch(e.target.value)}
                style={styles.input}
                autoFocus
              />
              {searching && <div style={styles.searchHint}>Buscando...</div>}
              {searchResults.length > 0 && (
                <div style={styles.searchResults}>
                  {searchResults.map(c => (
                    <div
                      key={c.id}
                      style={styles.searchItem}
                      onClick={() => handleAdd(c.id)}
                    >
                      <GravatarAvatar name={c.display_name} email={c.email} size={24} />
                      <div>
                        <div style={{ fontSize: 13, color: '#323130' }}>{c.display_name}</div>
                        <div style={{ fontSize: 11, color: '#a19f9d' }}>{c.email}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <button
                onClick={() => { setShowForm(false); setSearchQuery(''); setSearchResults([]); }}
                style={styles.cancelBtn}
              >
                Cancelar
              </button>
            </div>
          ) : (
            <button onClick={() => setShowForm(true)} style={styles.addBtn}>
              + Agregar relacion
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
  relItem: {
    display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px',
    borderRadius: 4, marginBottom: 6, border: '1px solid #edebe9',
    backgroundColor: '#fff',
  },
  relLabel: {
    fontSize: 11, color: '#0078d4', fontWeight: 600, textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  relName: {
    fontSize: 13, color: '#323130', cursor: 'pointer', fontWeight: 500,
  },
  deleteBtn: {
    border: 'none', background: 'none', color: '#a19f9d', fontSize: 18,
    cursor: 'pointer', padding: '2px 6px',
  },
  form: { marginTop: 8 },
  select: {
    width: '100%', padding: '8px 10px', border: '1px solid #c8c6c4',
    borderRadius: 4, fontSize: 13, marginBottom: 8, background: '#fff',
    fontFamily: "'Segoe UI', sans-serif",
  },
  input: {
    width: '100%', padding: '8px 10px', border: '1px solid #c8c6c4',
    borderRadius: 4, fontSize: 13, marginBottom: 4, boxSizing: 'border-box' as const,
    fontFamily: "'Segoe UI', sans-serif",
  },
  searchHint: { fontSize: 12, color: '#a19f9d', padding: 4 },
  searchResults: {
    border: '1px solid #edebe9', borderRadius: 4, maxHeight: 200,
    overflowY: 'auto', marginBottom: 8,
  },
  searchItem: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
    cursor: 'pointer', borderBottom: '1px solid #f3f2f1',
  },
  cancelBtn: {
    marginTop: 4, padding: '6px 16px', background: 'transparent',
    color: '#605e5c', border: '1px solid #c8c6c4', borderRadius: 4,
    fontSize: 13, cursor: 'pointer', width: '100%',
  },
  addBtn: {
    marginTop: 8, padding: '6px 12px', background: 'transparent',
    color: '#0078d4', border: '1px dashed #0078d4', borderRadius: 4,
    fontSize: 13, cursor: 'pointer', width: '100%',
  },
};
