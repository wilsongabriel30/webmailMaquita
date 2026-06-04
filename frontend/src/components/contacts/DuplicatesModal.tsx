import { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { GravatarAvatar } from './GravatarAvatar';

interface Contact {
  id: number;
  display_name: string;
  email: string;
  phone: string;
  organization: string;
  first_name: string;
  last_name: string;
  photo_url: string;
}

interface DuplicateGroup {
  reason: string;
  contacts: Contact[];
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onMerged: () => void;
}

export function DuplicatesModal({ isOpen, onClose, onMerged }: Props) {
  const [groups, setGroups] = useState<DuplicateGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [merging, setMerging] = useState<string | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen) loadDuplicates();
  }, [isOpen]);

  const loadDuplicates = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.get<DuplicateGroup[]>('/contacts/duplicates');
      setGroups(data);
    } catch {
      setError('Error al buscar duplicados');
    }
    setLoading(false);
  };

  const handleMerge = async (keepId: number, mergeId: number) => {
    const key = `${keepId}-${mergeId}`;
    setMerging(key);
    try {
      await api.post('/contacts/merge', { keep_id: keepId, merge_id: mergeId });
      setGroups(prev => prev.filter(g => {
        const ids = g.contacts.map(c => c.id);
        return !(ids.includes(keepId) && ids.includes(mergeId));
      }));
      onMerged();
    } catch {
      setError('Error al fusionar contactos');
    }
    setMerging(null);
  };

  if (!isOpen) return null;

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={e => e.stopPropagation()}>
        <div style={styles.header}>
          <h2 style={styles.title}>Contactos duplicados</h2>
          <button onClick={onClose} style={styles.closeBtn}>×</button>
        </div>

        <div style={styles.body}>
          {loading && <div style={styles.center}>Buscando duplicados...</div>}
          {error && <div style={{ ...styles.center, color: '#d13438' }}>{error}</div>}

          {!loading && groups.length === 0 && (
            <div style={styles.center}>No se encontraron contactos duplicados.</div>
          )}

          {groups.map((group, gi) => (
            <div key={gi} style={styles.group}>
              <div style={styles.groupReason}>{group.reason}</div>
              <div style={styles.contactsRow}>
                {group.contacts.slice(0, 2).map((contact) => (
                  <div key={contact.id} style={styles.contactCard}>
                    <div style={styles.cardHeader}>
                      <GravatarAvatar name={contact.display_name} email={contact.email} size={40} />
                      <div>
                        <div style={styles.contactName}>{contact.display_name || '(Sin nombre)'}</div>
                        <div style={styles.contactEmail}>{contact.email}</div>
                      </div>
                    </div>
                    <div style={styles.cardFields}>
                      {contact.phone && <div style={styles.field}>Tel: {contact.phone}</div>}
                      {contact.organization && <div style={styles.field}>Org: {contact.organization}</div>}
                      {contact.first_name && <div style={styles.field}>Nombre: {contact.first_name} {contact.last_name}</div>}
                    </div>
                    <button
                      style={{
                        ...styles.keepBtn,
                        opacity: merging ? 0.6 : 1,
                      }}
                      disabled={!!merging}
                      onClick={() => {
                        const otherId = group.contacts.find(c => c.id !== contact.id)?.id;
                        if (otherId) handleMerge(contact.id, otherId);
                      }}
                    >
                      {merging === `${contact.id}-${group.contacts.find(c => c.id !== contact.id)?.id}`
                        ? 'Fusionando...'
                        : 'Mantener este'}
                    </button>
                  </div>
                ))}
              </div>
              {group.contacts.length > 2 && (
                <div style={styles.moreText}>+{group.contacts.length - 2} contactos similares mas</div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.4)', display: 'flex',
    alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  },
  modal: {
    background: '#fff', borderRadius: 8, width: 700, maxHeight: '80vh',
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
  center: { textAlign: 'center', padding: 40, color: '#605e5c', fontSize: 14 },
  group: {
    border: '1px solid #edebe9', borderRadius: 6, padding: 16, marginBottom: 16,
    backgroundColor: '#faf9f8',
  },
  groupReason: {
    fontSize: 13, color: '#0078d4', fontWeight: 600, marginBottom: 12,
  },
  contactsRow: {
    display: 'flex', gap: 12,
  },
  contactCard: {
    flex: 1, background: '#fff', borderRadius: 6, padding: 14,
    border: '1px solid #e1dfdd',
  },
  cardHeader: {
    display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10,
  },
  contactName: { fontSize: 14, fontWeight: 600, color: '#323130' },
  contactEmail: { fontSize: 12, color: '#605e5c' },
  cardFields: { marginBottom: 12 },
  field: { fontSize: 12, color: '#605e5c', marginBottom: 4 },
  keepBtn: {
    width: '100%', padding: '8px 0', border: '1px solid #0078d4',
    borderRadius: 4, background: '#0078d4', color: '#fff',
    fontSize: 13, fontWeight: 600, cursor: 'pointer',
  },
  moreText: { fontSize: 12, color: '#a19f9d', marginTop: 8, textAlign: 'center' },
};
