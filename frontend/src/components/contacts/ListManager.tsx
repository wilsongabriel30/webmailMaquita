import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../../api/client';

// ── Types ──────────────────────────────────────────────────────────────────────

interface Member {
  id: number;
  display_name: string;
  email: string;
  phone: string;
  organization: string;
  is_favorite: boolean;
}

interface Contact {
  id: number;
  display_name: string;
  email: string;
}

interface Props {
  listId: number;
  listName: string;
  onClose: () => void;
  onSaved: () => void;
  onDeleted: () => void;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  return Math.abs(hash);
}

const AVATAR_COLORS = [
  '#0078d4', '#008272', '#ca5010', '#8764b8',
  '#da3b01', '#498205', '#005b70', '#c239b3',
  '#e3008c', '#4f6bed', '#69797e', '#a4262c',
];

function avatarColor(name: string): string {
  return AVATAR_COLORS[hashString(name) % AVATAR_COLORS.length];
}

function initial(name: string): string {
  return (name || '?').charAt(0).toUpperCase();
}

// ── Styles ─────────────────────────────────────────────────────────────────────

const S = {
  overlay: {
    position: 'fixed' as const,
    inset: 0,
    backgroundColor: 'rgba(0,0,0,0.4)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
  },
  modal: {
    backgroundColor: '#fff',
    borderRadius: 8,
    padding: 28,
    width: 520,
    maxHeight: '80vh',
    overflowY: 'auto' as const,
    boxShadow: '0 8px 30px rgba(0,0,0,0.22)',
    position: 'relative' as const,
  },
  closeBtn: {
    position: 'absolute' as const,
    top: 12,
    right: 16,
    background: 'none',
    border: 'none',
    fontSize: 20,
    cursor: 'pointer',
    color: '#605e5c',
    lineHeight: 1,
  },
  label: {
    display: 'block',
    fontSize: 12,
    fontWeight: 600 as const,
    color: '#323130',
    marginBottom: 4,
  },
  input: {
    width: '100%',
    padding: '6px 10px',
    fontSize: 14,
    border: '1px solid #8a8886',
    borderRadius: 4,
    outline: 'none',
    boxSizing: 'border-box' as const,
    fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
  },
  textarea: {
    width: '100%',
    padding: '6px 10px',
    fontSize: 13,
    border: '1px solid #8a8886',
    borderRadius: 4,
    outline: 'none',
    resize: 'vertical' as const,
    minHeight: 48,
    boxSizing: 'border-box' as const,
    fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
  },
  primaryBtn: {
    backgroundColor: '#0078d4',
    color: '#fff',
    border: 'none',
    borderRadius: 4,
    padding: '6px 18px',
    fontSize: 13,
    fontWeight: 600 as const,
    cursor: 'pointer',
  },
  dangerBtn: {
    backgroundColor: '#d13438',
    color: '#fff',
    border: 'none',
    borderRadius: 4,
    padding: '6px 18px',
    fontSize: 13,
    fontWeight: 600 as const,
    cursor: 'pointer',
  },
  secondaryBtn: {
    backgroundColor: '#fff',
    color: '#323130',
    border: '1px solid #8a8886',
    borderRadius: 4,
    padding: '6px 14px',
    fontSize: 13,
    cursor: 'pointer',
  },
  separator: {
    border: 'none',
    borderTop: '1px solid #edebe9',
    margin: '18px 0',
  },
  sectionHeader: {
    fontSize: 14,
    fontWeight: 600 as const,
    color: '#323130',
    marginBottom: 10,
  },
  memberRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '6px 0',
  },
  avatar: (name: string): React.CSSProperties => ({
    width: 32,
    height: 32,
    borderRadius: '50%',
    backgroundColor: avatarColor(name),
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 14,
    fontWeight: 600,
    flexShrink: 0,
  }),
  memberInfo: {
    flex: 1,
    minWidth: 0,
  },
  memberName: {
    fontSize: 13,
    fontWeight: 600 as const,
    color: '#323130',
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  memberEmail: {
    fontSize: 12,
    color: '#605e5c',
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  removeBtn: {
    background: 'none',
    border: 'none',
    fontSize: 16,
    color: '#a19f9d',
    cursor: 'pointer',
    padding: '2px 6px',
    borderRadius: 4,
    lineHeight: 1,
  },
  searchWrap: {
    position: 'relative' as const,
    marginTop: 8,
  },
  dropdown: {
    position: 'absolute' as const,
    top: '100%',
    left: 0,
    right: 0,
    backgroundColor: '#fff',
    border: '1px solid #edebe9',
    borderRadius: 4,
    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
    zIndex: 10,
    maxHeight: 200,
    overflowY: 'auto' as const,
  },
  dropdownItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '8px 12px',
    cursor: 'pointer',
    fontSize: 13,
  },
  footer: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 18,
  },
};

// ── Component ──────────────────────────────────────────────────────────────────

export function ListManager({ listId, listName, onClose, onSaved, onDeleted }: Props) {
  // Editable fields
  const [name, setName] = useState(listName);
  const [description, setDescription] = useState('');
  const [nameDescDirty, setNameDescDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  // Members
  const [members, setMembers] = useState<Member[]>([]);
  const [loadingMembers, setLoadingMembers] = useState(true);

  // Search / add
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Contact[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchWrapRef = useRef<HTMLDivElement>(null);

  // Delete confirmation
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // ── Load members ──

  const fetchMembers = useCallback(async () => {
    setLoadingMembers(true);
    try {
      const res = await api.get<Member[]>(`/contacts/lists/${listId}/members`);
      setMembers(res);
    } catch {
      // silently fail
    } finally {
      setLoadingMembers(false);
    }
  }, [listId]);

  useEffect(() => {
    fetchMembers();
  }, [fetchMembers]);

  // ── Load list details for description ──

  useEffect(() => {
    // Las listas no tienen endpoint individual GET, usamos los datos del prop
    // description se carga vacío, el usuario la edita desde aquí
  }, [listId]);

  // ── Save name/description ──

  const handleSaveDetails = async () => {
    setSaving(true);
    try {
      await api.put(`/contacts/lists/${listId}`, { name, description });
      setNameDescDirty(false);
      onSaved();
    } catch {
      // handle error
    } finally {
      setSaving(false);
    }
  };

  // ── Remove member ──

  const handleRemoveMember = async (contactId: number) => {
    try {
      await api.del(`/contacts/lists/${listId}/members/${contactId}`);
      setMembers((prev) => prev.filter((m) => m.id !== contactId));
      onSaved();
    } catch {
      // handle error
    }
  };

  // ── Search contacts ──

  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      setSearchOpen(false);
      return;
    }

    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);

    searchTimerRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const params = new URLSearchParams({ search: searchQuery, per_page: '10' });
        const res = await api.get<{ contacts: Contact[] }>(`/contacts?${params}`);
        const memberIds = new Set(members.map((m) => m.id));
        const filtered = (res.contacts as Contact[]).filter(
          (c) => !memberIds.has(c.id)
        );
        setSearchResults(filtered);
        setSearchOpen(true);
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);

    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    };
  }, [searchQuery, members]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchWrapRef.current && !searchWrapRef.current.contains(e.target as Node)) {
        setSearchOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // ── Add member ──

  const handleAddMember = async (contact: Contact) => {
    try {
      await api.post(`/contacts/lists/${listId}/members`, {
        contact_ids: [contact.id],
      });
      setSearchQuery('');
      setSearchOpen(false);
      fetchMembers();
      onSaved();
    } catch {
      // handle error
    }
  };

  // ── Delete list ──

  const handleDeleteList = async () => {
    setDeleting(true);
    try {
      await api.del(`/contacts/lists/${listId}`);
      onDeleted();
    } catch {
      // handle error
    } finally {
      setDeleting(false);
    }
  };

  // ── Overlay click → close ──

  const handleOverlayClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) onClose();
  };

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div style={S.overlay} onClick={handleOverlayClick}>
      <div style={S.modal}>
        {/* Close button */}
        <button style={S.closeBtn} onClick={onClose} title="Cerrar">×</button>

        {/* ── Header: name & description ── */}
        <div style={{ marginBottom: 12 }}>
          <label style={S.label}>Nombre de la lista</label>
          <input
            style={S.input}
            value={name}
            onChange={(e) => { setName(e.target.value); setNameDescDirty(true); }}
            placeholder="Nombre de la lista"
          />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label style={S.label}>Descripción</label>
          <textarea
            style={S.textarea}
            value={description}
            onChange={(e) => { setDescription(e.target.value); setNameDescDirty(true); }}
            placeholder="Descripción opcional"
            rows={2}
          />
        </div>
        {nameDescDirty && (
          <div style={{ textAlign: 'right', marginBottom: 4 }}>
            <button
              style={{ ...S.primaryBtn, opacity: saving ? 0.6 : 1 }}
              onClick={handleSaveDetails}
              disabled={saving}
            >
              {saving ? 'Guardando…' : 'Guardar cambios'}
            </button>
          </div>
        )}

        <hr style={S.separator} />

        {/* ── Members ── */}
        <div style={S.sectionHeader}>Miembros ({members.length})</div>

        {loadingMembers ? (
          <div style={{ fontSize: 13, color: '#605e5c', padding: '8px 0' }}>Cargando miembros…</div>
        ) : members.length === 0 ? (
          <div style={{ fontSize: 13, color: '#a19f9d', padding: '8px 0' }}>
            Esta lista no tiene miembros aún.
          </div>
        ) : (
          <div style={{ maxHeight: 220, overflowY: 'auto', marginBottom: 8 }}>
            {members.map((m) => (
              <div key={m.id} style={S.memberRow}>
                <div style={S.avatar(m.display_name)}>{initial(m.display_name)}</div>
                <div style={S.memberInfo}>
                  <div style={S.memberName}>{m.display_name}</div>
                  <div style={S.memberEmail}>{m.email}</div>
                </div>
                <button
                  style={S.removeBtn}
                  title="Eliminar de la lista"
                  onClick={() => handleRemoveMember(m.id)}
                  onMouseEnter={(e) => (e.currentTarget.style.color = '#d13438')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = '#a19f9d')}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}

        <hr style={S.separator} />

        {/* ── Add members ── */}
        <div style={S.sectionHeader}>Agregar miembros</div>
        <div style={S.searchWrap} ref={searchWrapRef}>
          <input
            style={S.input}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Buscar contactos por nombre o email…"
          />
          {searchOpen && searchResults.length > 0 && (
            <div style={S.dropdown}>
              {searchResults.map((c) => (
                <div
                  key={c.id}
                  style={S.dropdownItem}
                  onClick={() => handleAddMember(c)}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#f3f2f1')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#fff')}
                >
                  <div style={S.avatar(c.display_name)}>{initial(c.display_name)}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, color: '#323130' }}>{c.display_name}</div>
                    <div style={{ fontSize: 12, color: '#605e5c' }}>{c.email}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
          {searchOpen && searchResults.length === 0 && !searching && searchQuery.trim() && (
            <div style={{ ...S.dropdown, padding: '10px 12px', fontSize: 13, color: '#605e5c' }}>
              No se encontraron contactos.
            </div>
          )}
          {searching && (
            <div style={{ fontSize: 12, color: '#605e5c', marginTop: 4 }}>Buscando…</div>
          )}
        </div>

        <hr style={S.separator} />

        {/* ── Footer: delete list ── */}
        <div style={S.footer}>
          <div>
            {!confirmDelete ? (
              <button style={S.dangerBtn} onClick={() => setConfirmDelete(true)}>
                Eliminar lista
              </button>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 13, color: '#d13438', fontWeight: 600 }}>
                  ¿Eliminar esta lista?
                </span>
                <button
                  style={{ ...S.dangerBtn, opacity: deleting ? 0.6 : 1 }}
                  onClick={handleDeleteList}
                  disabled={deleting}
                >
                  {deleting ? 'Eliminando…' : 'Sí, eliminar'}
                </button>
                <button style={S.secondaryBtn} onClick={() => setConfirmDelete(false)}>
                  Cancelar
                </button>
              </div>
            )}
          </div>
          <button style={S.secondaryBtn} onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </div>
  );
}
