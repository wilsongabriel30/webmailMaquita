import React, { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../../api/client';
import { useMailStore } from '../../store/mailStore';
import { useNavigate } from 'react-router-dom';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface Contact {
  id: number;
  display_name: string;
  email: string;
  phone: string;
  organization: string;
  notes: string;
  created_at: string;
}

interface ContactsResponse {
  contacts: Contact[];
  total: number;
  page: number;
  per_page: number;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */
const AVATAR_COLORS = [
  '#0078d4', '#498205', '#8764b8', '#ca5010', '#038387',
  '#da3b01', '#8e562e', '#647c64', '#7160e8', '#c239b3',
  '#e3008c', '#9c0027', '#004e8c', '#4f6bed', '#881798',
];

function getInitials(name: string): string {
  if (!name || !name.trim()) return '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return parts[0][0].toUpperCase();
}

function getAvatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('es-EC', { day: '2-digit', month: 'short', year: 'numeric' });
}

/* ------------------------------------------------------------------ */
/*  Avatar                                                             */
/* ------------------------------------------------------------------ */
function Avatar({ name, size = 40 }: { name: string; size?: number }) {
  const initials = getInitials(name);
  const bg = getAvatarColor(name);
  const fontSize = size < 40 ? 13 : size < 60 ? 16 : 24;
  return (
    <div
      style={{
        width: size, height: size, borderRadius: '50%',
        backgroundColor: bg, color: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize, fontWeight: 600, flexShrink: 0,
        fontFamily: "'Segoe UI', Calibri, sans-serif",
      }}
    >
      {initials}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Empty state                                                        */
/* ------------------------------------------------------------------ */
function EmptyState({ hasSearch }: { hasSearch: boolean }) {
  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', padding: 40,
      color: '#a19f9d',
    }}>
      <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="#d2d0ce" strokeWidth="1">
        <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
      <p style={{ fontSize: 16, fontWeight: 500, marginTop: 16, color: '#605e5c' }}>
        {hasSearch ? 'No se encontraron contactos' : 'No hay contactos'}
      </p>
      <p style={{ fontSize: 13, marginTop: 4 }}>
        {hasSearch
          ? 'Intenta con otro termino de busqueda'
          : 'Agrega tu primer contacto con el boton "Nuevo contacto"'}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Delete confirmation dialog                                         */
/* ------------------------------------------------------------------ */
function DeleteDialog({ name, onConfirm, onCancel }: {
  name: string; onConfirm: () => void; onCancel: () => void;
}) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      backgroundColor: 'rgba(0,0,0,0.4)',
    }}>
      <div style={{
        background: '#fff', borderRadius: 8, padding: 24, width: 400,
        boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
        fontFamily: "'Segoe UI', Calibri, sans-serif",
      }}>
        <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: '#323130' }}>
          Eliminar contacto
        </h3>
        <p style={{ fontSize: 14, color: '#605e5c', margin: '12px 0 24px' }}>
          ¿Estas seguro de que deseas eliminar a <strong>{name}</strong>? Esta accion no se puede deshacer.
        </p>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button onClick={onCancel} style={{
            padding: '8px 20px', fontSize: 13, fontWeight: 600,
            border: '1px solid #8a8886', borderRadius: 4, background: '#fff',
            color: '#323130', cursor: 'pointer',
          }}>Cancelar</button>
          <button onClick={onConfirm} style={{
            padding: '8px 20px', fontSize: 13, fontWeight: 600,
            border: 'none', borderRadius: 4, background: '#d13438',
            color: '#fff', cursor: 'pointer',
          }}>Eliminar</button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Contact form (used in detail panel and new contact modal)          */
/* ------------------------------------------------------------------ */
interface FormData {
  name: string; email: string; phone: string;
  organization: string; notes: string;
}

function ContactForm({ initial, onSave, onCancel, saving }: {
  initial: FormData;
  onSave: (data: FormData) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const [form, setForm] = useState<FormData>(initial);

  const initialRef = useRef(initial);
  useEffect(() => {
    const prev = initialRef.current;
    if (
      prev.name !== initial.name || prev.email !== initial.email ||
      prev.phone !== initial.phone || prev.organization !== initial.organization ||
      prev.notes !== initial.notes
    ) {
      initialRef.current = initial;
      setForm(initial);
    }
  }, [initial]);

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '8px 12px', fontSize: 14,
    border: '1px solid #8a8886', borderRadius: 4, outline: 'none',
    fontFamily: "'Segoe UI', Calibri, sans-serif",
    boxSizing: 'border-box',
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 13, fontWeight: 600, color: '#323130',
    marginBottom: 4, display: 'block',
  };

  const handleFocus = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    e.target.style.borderColor = '#0078d4';
  };
  const handleBlur = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    e.target.style.borderColor = '#8a8886';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <label style={labelStyle}>Nombre</label>
        <input style={inputStyle} value={form.name}
          onChange={e => setForm({ ...form, name: e.target.value })}
          placeholder="Nombre completo"
          onFocus={handleFocus} onBlur={handleBlur} />
      </div>
      <div>
        <label style={labelStyle}>Email</label>
        <input style={inputStyle} type="email" value={form.email}
          onChange={e => setForm({ ...form, email: e.target.value })}
          placeholder="correo@ejemplo.com"
          onFocus={handleFocus} onBlur={handleBlur} />
      </div>
      <div>
        <label style={labelStyle}>Telefono</label>
        <input style={inputStyle} value={form.phone}
          onChange={e => setForm({ ...form, phone: e.target.value })}
          placeholder="+593 ..."
          onFocus={handleFocus} onBlur={handleBlur} />
      </div>
      <div>
        <label style={labelStyle}>Organizacion</label>
        <input style={inputStyle} value={form.organization}
          onChange={e => setForm({ ...form, organization: e.target.value })}
          placeholder="Empresa u organizacion"
          onFocus={handleFocus} onBlur={handleBlur} />
      </div>
      <div>
        <label style={labelStyle}>Notas</label>
        <textarea style={{ ...inputStyle, minHeight: 80, resize: 'vertical' }}
          value={form.notes}
          onChange={e => setForm({ ...form, notes: e.target.value })}
          placeholder="Notas adicionales..."
          onFocus={handleFocus} onBlur={handleBlur} />
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <button
          onClick={() => onSave(form)}
          disabled={saving || !form.name.trim() || !form.email.trim()}
          style={{
            padding: '8px 24px', fontSize: 13, fontWeight: 600,
            border: 'none', borderRadius: 4,
            background: (!form.name.trim() || !form.email.trim()) ? '#c8c6c4' : '#0078d4',
            color: '#fff', cursor: saving ? 'wait' : 'pointer',
          }}
        >
          {saving ? 'Guardando...' : 'Guardar'}
        </button>
        <button onClick={onCancel} style={{
          padding: '8px 20px', fontSize: 13, fontWeight: 600,
          border: '1px solid #8a8886', borderRadius: 4, background: '#fff',
          color: '#323130', cursor: 'pointer',
        }}>Cancelar</button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  New contact modal                                                  */
/* ------------------------------------------------------------------ */
function NewContactModal({ onSave, onClose, saving }: {
  onSave: (data: FormData) => void; onClose: () => void; saving: boolean;
}) {
  const blank: FormData = { name: '', email: '', phone: '', organization: '', notes: '' };
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9998,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      backgroundColor: 'rgba(0,0,0,0.4)',
    }}>
      <div style={{
        background: '#fff', borderRadius: 8, padding: 28, width: 460,
        maxHeight: '90vh', overflowY: 'auto',
        boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
        fontFamily: "'Segoe UI', Calibri, sans-serif",
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h3 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#323130' }}>
            Nuevo contacto
          </h3>
          <button onClick={onClose} style={{
            border: 'none', background: 'none', fontSize: 20,
            cursor: 'pointer', color: '#605e5c', padding: 4,
          }}>&times;</button>
        </div>
        <ContactForm initial={blank} onSave={onSave} onCancel={onClose} saving={saving} />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Detail row                                                         */
/* ------------------------------------------------------------------ */
function DetailRow({ icon, label, value, multiline }: {
  icon: string; label: string; value: string; multiline?: boolean;
}) {
  if (!value) return null;
  const icons: Record<string, React.ReactNode> = {
    mail: <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />,
    phone: <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z" />,
    org: <><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" /><polyline points="9,22 9,12 15,12 15,22" /></>,
    note: <><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14,2 14,8 20,8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></>,
  };

  return (
    <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: multiline ? 'flex-start' : 'center' }}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#605e5c" strokeWidth="1.5"
        style={{ flexShrink: 0, marginTop: multiline ? 2 : 0 }}>
        {icons[icon]}
      </svg>
      <div>
        <div style={{ fontSize: 12, color: '#a19f9d', marginBottom: 2 }}>{label}</div>
        <div style={{
          fontSize: 14, color: '#323130',
          whiteSpace: multiline ? 'pre-wrap' : 'nowrap',
        }}>
          {value}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main ContactsView component                                        */
/* ------------------------------------------------------------------ */
export function ContactsView() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const perPage = 50;
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Contact | null>(null);
  const [editing, setEditing] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [saving, setSaving] = useState(false);
  const [mobileShowDetail, setMobileShowDetail] = useState(false);
  const searchTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const openCompose = useMailStore(s => s.openCompose);
  const navigate = useNavigate();

  /* Fetch contacts */
  const fetchContacts = useCallback(async (p: number, q: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(p), per_page: String(perPage) });
      if (q) params.set('search', q);
      const res = await api.get<ContactsResponse>('/contacts?' + params.toString());
      setContacts(res.contacts);
      setTotal(res.total);
      setPage(res.page);
    } catch (_err) {
      void _err;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchContacts(1, ''); }, [fetchContacts]);

  /* Search debounce */
  const handleSearch = (val: string) => {
    setSearch(val);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setSelected(null);
      fetchContacts(1, val);
    }, 300);
  };

  /* CRUD handlers */
  const handleCreate = async (data: FormData) => {
    setSaving(true);
    try {
      await api.post('/contacts', data);
      setShowNew(false);
      await fetchContacts(1, search);
    } finally { setSaving(false); }
  };

  const handleUpdate = async (data: FormData) => {
    if (!selected) return;
    setSaving(true);
    try {
      await api.put('/contacts/' + selected.id, data);
      setEditing(false);
      await fetchContacts(page, search);
      setSelected(prev => prev ? {
        ...prev,
        display_name: data.name, email: data.email,
        phone: data.phone, organization: data.organization, notes: data.notes,
      } : null);
    } finally { setSaving(false); }
  };

  const handleDelete = async () => {
    if (!selected) return;
    try {
      await api.del('/contacts/' + selected.id);
      setShowDelete(false);
      setSelected(null);
      setMobileShowDetail(false);
      await fetchContacts(page, search);
    } catch (_err) {
      void _err;
    }
  };

  const handleSendEmail = () => {
    if (!selected) return;
    const emailAddr = selected.display_name
      ? selected.display_name + ' <' + selected.email + '>'
      : selected.email;
    openCompose('new', {
      to: [emailAddr], subject: '', text_body: '', html_body: '',
    });
    navigate('/');
  };

  /* Alphabetical grouping */
  const grouped = contacts.reduce<Record<string, Contact[]>>((acc, c) => {
    const firstChar = (c.display_name || '?')[0].toUpperCase();
    const letter = /[A-Z]/.test(firstChar) ? firstChar : '#';
    if (!acc[letter]) acc[letter] = [];
    acc[letter].push(c);
    return acc;
  }, {});
  const sortedLetters = Object.keys(grouped).sort((a, b) => {
    if (a === '#') return 1;
    if (b === '#') return -1;
    return a.localeCompare(b);
  });

  const totalPages = Math.ceil(total / perPage);

  /* Responsive breakpoint */
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);

  /* ----- RENDER ----- */
  const showList = !isMobile || !mobileShowDetail;
  const showDetail = !isMobile || mobileShowDetail;

  return (
    <div style={{
      display: 'flex', height: '100%', background: '#f3f2f1',
      fontFamily: "'Segoe UI', Calibri, sans-serif",
    }}>
      {/* ===== LEFT PANEL: Contact list ===== */}
      {showList && (
        <div style={{
          width: isMobile ? '100%' : 320,
          minWidth: isMobile ? undefined : 280,
          borderRight: '1px solid #edebe9',
          display: 'flex', flexDirection: 'column',
          background: '#fff',
        }}>
          {/* Header */}
          <div style={{
            padding: '16px 16px 12px', borderBottom: '1px solid #edebe9',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#323130' }}>
                Contactos
              </h2>
              <span style={{ fontSize: 12, color: '#a19f9d' }}>
                {total} contacto{total !== 1 ? 's' : ''}
              </span>
            </div>
            {/* New contact button */}
            <button
              onClick={() => setShowNew(true)}
              style={{
                width: '100%', padding: '8px 12px', fontSize: 13, fontWeight: 600,
                border: 'none', borderRadius: 4, background: '#0078d4',
                color: '#fff', cursor: 'pointer', marginBottom: 12,
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Nuevo contacto
            </button>
            {/* Search */}
            <div style={{ position: 'relative' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                stroke="#a19f9d" strokeWidth="2" style={{
                  position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
                }}>
                <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                value={search}
                onChange={e => handleSearch(e.target.value)}
                placeholder="Buscar contactos..."
                style={{
                  width: '100%', padding: '8px 12px 8px 34px', fontSize: 13,
                  border: '1px solid #edebe9', borderRadius: 4, outline: 'none',
                  fontFamily: "'Segoe UI', Calibri, sans-serif",
                  boxSizing: 'border-box',
                }}
                onFocus={e => { e.target.style.borderColor = '#0078d4'; }}
                onBlur={e => { e.target.style.borderColor = '#edebe9'; }}
              />
            </div>
          </div>

          {/* Contact list */}
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {loading && contacts.length === 0 ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
                <div className="contacts-spinner" style={{
                  width: 24, height: 24, border: '2px solid #edebe9',
                  borderTopColor: '#0078d4', borderRadius: '50%',
                }} />
              </div>
            ) : contacts.length === 0 ? (
              <EmptyState hasSearch={search.length > 0} />
            ) : (
              sortedLetters.map(letter => (
                <div key={letter}>
                  {/* Letter header */}
                  <div style={{
                    padding: '8px 16px', fontSize: 12, fontWeight: 600,
                    color: '#0078d4', background: '#faf9f8',
                    borderBottom: '1px solid #edebe9',
                    position: 'sticky', top: 0, zIndex: 1,
                  }}>
                    {letter}
                  </div>
                  {/* Contacts under this letter */}
                  {grouped[letter].map(contact => {
                    const isSelected = selected?.id === contact.id;
                    return (
                      <ContactListItem
                        key={contact.id}
                        contact={contact}
                        isSelected={isSelected}
                        onClick={() => {
                          setSelected(contact);
                          setEditing(false);
                          if (isMobile) setMobileShowDetail(true);
                        }}
                      />
                    );
                  })}
                </div>
              ))
            )}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{
              display: 'flex', justifyContent: 'center', alignItems: 'center',
              gap: 8, padding: '10px 16px', borderTop: '1px solid #edebe9',
              background: '#faf9f8',
            }}>
              <button
                disabled={page <= 1}
                onClick={() => fetchContacts(page - 1, search)}
                style={{
                  padding: '4px 12px', fontSize: 12, border: '1px solid #edebe9',
                  borderRadius: 4, background: '#fff', cursor: page <= 1 ? 'default' : 'pointer',
                  color: page <= 1 ? '#c8c6c4' : '#323130',
                }}
              >
                Anterior
              </button>
              <span style={{ fontSize: 12, color: '#605e5c' }}>
                {page} / {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => fetchContacts(page + 1, search)}
                style={{
                  padding: '4px 12px', fontSize: 12, border: '1px solid #edebe9',
                  borderRadius: 4, background: '#fff', cursor: page >= totalPages ? 'default' : 'pointer',
                  color: page >= totalPages ? '#c8c6c4' : '#323130',
                }}
              >
                Siguiente
              </button>
            </div>
          )}
        </div>
      )}

      {/* ===== RIGHT PANEL: Contact detail ===== */}
      {showDetail && (
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          background: '#fff', overflow: 'hidden',
        }}>
          {!selected ? (
            <div style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', color: '#a19f9d',
            }}>
              <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#d2d0ce" strokeWidth="1">
                <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
              <p style={{ fontSize: 14, marginTop: 12 }}>
                Selecciona un contacto para ver sus detalles
              </p>
            </div>
          ) : editing ? (
            <div style={{ flex: 1, overflowY: 'auto', padding: 32, maxWidth: 560 }}>
              {isMobile && (
                <button onClick={() => { setMobileShowDetail(false); setEditing(false); }}
                  style={{
                    border: 'none', background: 'none', fontSize: 13,
                    color: '#0078d4', cursor: 'pointer', padding: 0, marginBottom: 16,
                    fontWeight: 600,
                  }}>
                  Volver
                </button>
              )}
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
                <Avatar name={selected.display_name} size={56} />
                <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#323130' }}>
                  Editar contacto
                </h2>
              </div>
              <ContactForm
                initial={{
                  name: selected.display_name, email: selected.email,
                  phone: selected.phone || '', organization: selected.organization || '',
                  notes: selected.notes || '',
                }}
                onSave={handleUpdate}
                onCancel={() => setEditing(false)}
                saving={saving}
              />
            </div>
          ) : (
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {/* Detail header */}
              <div style={{
                padding: '32px 32px 24px',
                borderBottom: '1px solid #edebe9',
                background: '#faf9f8',
              }}>
                {isMobile && (
                  <button onClick={() => setMobileShowDetail(false)}
                    style={{
                      border: 'none', background: 'none', fontSize: 13,
                      color: '#0078d4', cursor: 'pointer', padding: 0, marginBottom: 16,
                      fontWeight: 600,
                    }}>
                    Volver
                  </button>
                )}
                <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
                  <Avatar name={selected.display_name} size={72} />
                  <div>
                    <h2 style={{ margin: 0, fontSize: 24, fontWeight: 600, color: '#323130' }}>
                      {selected.display_name || '(Sin nombre)'}
                    </h2>
                    {selected.organization && (
                      <p style={{ margin: '4px 0 0', fontSize: 14, color: '#605e5c' }}>
                        {selected.organization}
                      </p>
                    )}
                  </div>
                </div>
                {/* Action buttons */}
                <div style={{ display: 'flex', gap: 8, marginTop: 20, flexWrap: 'wrap' }}>
                  <button onClick={handleSendEmail} style={{
                    padding: '8px 16px', fontSize: 13, fontWeight: 600,
                    border: 'none', borderRadius: 4, background: '#0078d4',
                    color: '#fff', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 6,
                  }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                      <polyline points="22,6 12,13 2,6" />
                    </svg>
                    Enviar correo
                  </button>
                  <button onClick={() => setEditing(true)} style={{
                    padding: '8px 16px', fontSize: 13, fontWeight: 600,
                    border: '1px solid #8a8886', borderRadius: 4, background: '#fff',
                    color: '#323130', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 6,
                  }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                      <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                    </svg>
                    Editar
                  </button>
                  <button onClick={() => setShowDelete(true)} style={{
                    padding: '8px 16px', fontSize: 13, fontWeight: 600,
                    border: '1px solid #d13438', borderRadius: 4, background: '#fff',
                    color: '#d13438', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 6,
                  }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="3,6 5,6 21,6" />
                      <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                    </svg>
                    Eliminar
                  </button>
                </div>
              </div>

              {/* Contact details */}
              <div style={{ padding: 32 }}>
                <DetailRow icon="mail" label="Email" value={selected.email} />
                <DetailRow icon="phone" label="Telefono" value={selected.phone} />
                <DetailRow icon="org" label="Organizacion" value={selected.organization} />
                <DetailRow icon="note" label="Notas" value={selected.notes} multiline />
                {selected.created_at && (
                  <div style={{ marginTop: 24, fontSize: 12, color: '#a19f9d' }}>
                    Contacto creado el {formatDate(selected.created_at)}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Modals */}
      {showNew && (
        <NewContactModal
          onSave={handleCreate}
          onClose={() => setShowNew(false)}
          saving={saving}
        />
      )}
      {showDelete && selected && (
        <DeleteDialog
          name={selected.display_name || selected.email}
          onConfirm={handleDelete}
          onCancel={() => setShowDelete(false)}
        />
      )}

      {/* Spinner animation */}
      <style>{'.contacts-spinner { animation: contacts-spin 0.8s linear infinite; } @keyframes contacts-spin { to { transform: rotate(360deg); } }'}</style>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Contact list item (extracted for hover handling)                    */
/* ------------------------------------------------------------------ */
function ContactListItem({ contact, isSelected, onClick }: {
  contact: Contact; isSelected: boolean; onClick: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '10px 16px', cursor: 'pointer',
        background: isSelected ? '#e1dfdd' : hovered ? '#f3f2f1' : '#fff',
        borderBottom: '1px solid #f3f2f1',
        transition: 'background 0.1s',
      }}
    >
      <Avatar name={contact.display_name} size={36} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 14, fontWeight: 600, color: '#323130',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {contact.display_name || '(Sin nombre)'}
        </div>
        <div style={{
          fontSize: 12, color: '#605e5c',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {contact.email}
        </div>
      </div>
    </div>
  );
}
