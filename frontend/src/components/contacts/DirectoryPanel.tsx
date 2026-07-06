import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../../api/client';
import { useMailStore } from '../../store/mailStore';
import { useNavigate } from 'react-router-dom';
import { getInitials, getAvatarColor } from './types';

// ── Types ──

interface OrgContact {
  id: number;
  display_name: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  phone_mobile: string;
  job_title: string;
  department: string;
  company: string;
  photo_url: string;
  notes: string;
  created_by: string;
  location?: string;
  source?: string;
  is_active?: boolean;
}

type ViewMode = 'list' | 'cards' | 'org';
type SourceFilter = 'all' | 'mailbox' | 'directory';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  pickerMode?: boolean;
  onPickContact?: (contact: OrgContact, target: 'to' | 'cc' | 'bcc') => void;
  pickerTarget?: 'to' | 'cc' | 'bcc';
}

// ── Helpers ──

function ContactAvatar({ contact, size = 40 }: { contact: OrgContact; size?: number }) {
  const [fotoRota, setFotoRota] = useState(false);
  if (contact.photo_url && !fotoRota) {
    return <img src={contact.photo_url} alt="" className="rounded-full object-cover shrink-0"
      style={{ width: size, height: size }} onError={() => setFotoRota(true)} />;
  }
  const name = contact.display_name || contact.email;
  const color = getAvatarColor(contact.email || name);
  const initials = getInitials(name);
  const fs = size < 40 ? 13 : size < 60 ? 16 : 24;
  return (
    <div className="rounded-full flex items-center justify-center text-white font-semibold shrink-0"
      style={{ width: size, height: size, backgroundColor: color, fontSize: fs }}>
      {initials}
    </div>
  );
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text).catch(() => {});
}

// ── Main component ──

export function DirectoryPanel({ isOpen, onClose, pickerMode, onPickContact, pickerTarget = 'to' }: Props) {
  const [contacts, setContacts] = useState<OrgContact[]>([]);
  const [departments, setDepartments] = useState<string[]>([]);
  const [locations, setLocations] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [deptFilter, setDeptFilter] = useState('');
  const [locFilter, setLocFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all');
  const [activeOnly, setActiveOnly] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [selected, setSelected] = useState<OrgContact | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<Partial<OrgContact>>({});
  const [saving, setSaving] = useState(false);
  const [copyStatus, setCopyStatus] = useState<Record<number, string>>({});
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [currentTarget, setCurrentTarget] = useState<'to' | 'cc' | 'bcc'>(pickerTarget);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const openCompose = useMailStore(s => s.openCompose);
  const navigate = useNavigate();

  // ── Data loading ──

  const loadContacts = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set('search', search);
      if (deptFilter) params.set('department', deptFilter);
      if (locFilter) params.set('location', locFilter);
      if (sourceFilter !== 'all') params.set('source', sourceFilter);
      if (activeOnly) params.set('active_only', 'true');
      const data = await api.get<OrgContact[]>(`/contacts/directory?${params}`);
      setContacts(data);
    } catch { /* ignore */ }
    setLoading(false);
  }, [search, deptFilter, locFilter, sourceFilter, activeOnly]);

  const loadFilters = async () => {
    try {
      const [depts, locs] = await Promise.all([
        api.get<string[]>('/contacts/directory/departments'),
        api.get<string[]>('/contacts/directory/locations').catch(() => [] as string[]),
      ]);
      setDepartments(depts);
      setLocations(locs);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    if (isOpen) {
      loadContacts();
      loadFilters();
      setTimeout(() => searchInputRef.current?.focus(), 100);
    }
  }, [isOpen, loadContacts]);

  const handleSearchChange = (val: string) => {
    setSearch(val);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(() => loadContacts(), 300);
  };

  // ── CRUD ──

  const handleSave = async () => {
    if (!formData.email) return;
    setSaving(true);
    try {
      if (formData.id) {
        const updated = await api.put<OrgContact>(`/contacts/directory/${formData.id}`, formData);
        setContacts(prev => prev.map(c => c.id === updated.id ? updated : c));
        setSelected(updated);
      } else {
        const created = await api.post<OrgContact>('/contacts/directory', formData);
        setContacts(prev => [...prev, created]);
      }
      setShowForm(false);
      setFormData({});
    } catch (e: any) {
      alert(e?.message || 'Error al guardar');
    }
    setSaving(false);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Eliminar este contacto del directorio?')) return;
    try {
      await api.del(`/contacts/directory/${id}`);
      setContacts(prev => prev.filter(c => c.id !== id));
      if (selected?.id === id) setSelected(null);
    } catch { /* ignore */ }
  };

  const handleCopyToPersonal = async (id: number) => {
    setCopyStatus(prev => ({ ...prev, [id]: 'saving' }));
    try {
      const res = await api.post<{ status: string }>(`/contacts/directory/${id}/copy-to-personal`);
      setCopyStatus(prev => ({ ...prev, [id]: res.status === 'exists' ? 'exists' : 'done' }));
    } catch {
      setCopyStatus(prev => ({ ...prev, [id]: 'error' }));
    }
  };

  const handleSendEmail = (contact: OrgContact) => {
    const emailAddr = contact.display_name
      ? `${contact.display_name} <${contact.email}>`
      : contact.email;
    openCompose('new', { to: [emailAddr], subject: '', text_body: '', html_body: '' });
    onClose();
    navigate('/');
  };

  const handleCopyField = (text: string, field: string) => {
    copyToClipboard(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const handleExportCSV = async () => {
    try {
      const allContacts = await api.get<OrgContact[]>('/contacts/directory?limit=10000');
      const headers = ['Nombre', 'Email', 'Cargo', 'Departamento', 'Telefono', 'Celular', 'Empresa'];
      const rows = allContacts.map(c => [
        c.display_name, c.email, c.job_title, c.department, c.phone, c.phone_mobile, c.company
      ]);
      const csv = [headers, ...rows].map(r => r.map(v => `"${(v || '').replace(/"/g, '""')}"`).join(',')).join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `directorio-${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* ignore */ }
  };

  // Group contacts by department (for org view)
  const groupedByDept = contacts.reduce<Record<string, OrgContact[]>>((acc, c) => {
    const dept = c.department || 'Sin departamento';
    if (!acc[dept]) acc[dept] = [];
    acc[dept].push(c);
    return acc;
  }, {});

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white rounded-xl w-[1100px] max-w-[95vw] max-h-[90vh] flex flex-col shadow-2xl"
        onClick={e => e.stopPropagation()}>

        {/* ── Header ── */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#edebe9]">
          <div className="flex items-center gap-3">
            <svg className="w-5 h-5 text-[#0078d4]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
            <h2 className="text-lg font-semibold text-[#323130] m-0">
              {pickerMode ? 'Seleccionar destinatario' : 'Directorio institucional'}
            </h2>
            {pickerMode && (
              <div className="flex items-center gap-1 ml-4">
                {(['to', 'cc', 'bcc'] as const).map(t => (
                  <button key={t} onClick={() => setCurrentTarget(t)}
                    className={`px-2.5 py-1 text-[11px] font-medium rounded-full transition-colors ${
                      currentTarget === t ? 'bg-[#0078d4] text-white' : 'bg-[#f3f2f1] text-[#605e5c] hover:bg-[#e1dfdd]'
                    }`}>
                    {t === 'to' ? 'Para' : t === 'cc' ? 'CC' : 'CCO'}
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {/* View mode toggles */}
            <div className="flex items-center border border-[#e1dfdd] rounded-md overflow-hidden">
              <button onClick={() => setViewMode('list')} title="Lista"
                className={`p-1.5 transition-colors ${viewMode === 'list' ? 'bg-[#0078d4] text-white' : 'text-[#605e5c] hover:bg-[#f3f2f1]'}`}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                </svg>
              </button>
              <button onClick={() => setViewMode('cards')} title="Tarjetas"
                className={`p-1.5 transition-colors ${viewMode === 'cards' ? 'bg-[#0078d4] text-white' : 'text-[#605e5c] hover:bg-[#f3f2f1]'}`}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
                </svg>
              </button>
              <button onClick={() => setViewMode('org')} title="Organigrama"
                className={`p-1.5 transition-colors ${viewMode === 'org' ? 'bg-[#0078d4] text-white' : 'text-[#605e5c] hover:bg-[#f3f2f1]'}`}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
              </button>
            </div>
            <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-md text-[#605e5c] hover:bg-[#f3f2f1] hover:text-[#323130] transition-colors text-lg">
              {'\u00D7'}
            </button>
          </div>
        </div>

        {/* ── Toolbar ── */}
        <div className="flex flex-wrap items-center gap-2 px-5 py-3 border-b border-[#edebe9] bg-[#faf9f8]">
          <div className="relative flex-1 min-w-[200px]">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#a19f9d]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input ref={searchInputRef} type="text" placeholder="Buscar por nombre, email, cargo..."
              value={search} onChange={e => handleSearchChange(e.target.value)}
              className="w-full pl-9 pr-3 py-2 border border-[#c8c6c4] rounded-md text-[13px] focus:border-[#0078d4] focus:ring-1 focus:ring-[#0078d4] outline-none transition-colors" />
          </div>
          <select value={deptFilter} onChange={e => setDeptFilter(e.target.value)}
            className="py-2 px-3 border border-[#c8c6c4] rounded-md text-[13px] bg-white min-w-[160px]">
            <option value="">Todos los departamentos</option>
            {departments.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
          {locations.length > 0 && (
            <select value={locFilter} onChange={e => setLocFilter(e.target.value)}
              className="py-2 px-3 border border-[#c8c6c4] rounded-md text-[13px] bg-white min-w-[140px]">
              <option value="">Todas las ubicaciones</option>
              {locations.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          )}
          <div className="flex items-center border border-[#c8c6c4] rounded-md overflow-hidden">
            {([
              { value: 'all' as SourceFilter, label: 'Todos' },
              { value: 'mailbox' as SourceFilter, label: 'Usuarios' },
              { value: 'directory' as SourceFilter, label: 'Directorio' },
            ]).map(s => (
              <button key={s.value} onClick={() => setSourceFilter(s.value)}
                className={`px-3 py-1.5 text-[12px] font-medium transition-colors ${
                  sourceFilter === s.value ? 'bg-[#0078d4] text-white' : 'bg-white text-[#605e5c] hover:bg-[#f3f2f1]'
                }`}>
                {s.label}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-1.5 text-[12px] text-[#605e5c] cursor-pointer select-none">
            <input type="checkbox" checked={activeOnly} onChange={e => setActiveOnly(e.target.checked)}
              className="rounded border-[#c8c6c4] text-[#0078d4] focus:ring-[#0078d4]" />
            Solo activos
          </label>
          <button onClick={() => { setFormData({}); setShowForm(true); }}
            className="px-3 py-2 bg-[#0078d4] text-white rounded-md text-[12px] font-semibold hover:bg-[#106ebe] transition-colors whitespace-nowrap">
            + Nuevo
          </button>
          <button onClick={handleExportCSV}
            className="px-3 py-2 border border-[#c8c6c4] text-[#605e5c] rounded-md text-[12px] hover:bg-[#f3f2f1] transition-colors whitespace-nowrap"
            title="Exportar CSV">
            <svg className="w-4 h-4 inline-block mr-1 -mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            CSV
          </button>
          <span className="text-[11px] text-[#a19f9d]">{contacts.length} contacto{contacts.length !== 1 ? 's' : ''}</span>
        </div>

        {/* ── Body ── */}
        <div className="flex-1 flex overflow-hidden relative">

          {/* ── Form panel (overlay) ── */}
          {showForm && (
            <div className="absolute inset-0 z-10 bg-white/95 flex items-center justify-center">
              <div className="w-[600px] bg-white rounded-xl shadow-2xl border border-[#edebe9] p-6">
                <h3 className="text-[16px] font-semibold text-[#323130] mb-4">
                  {formData.id ? 'Editar contacto' : 'Nuevo contacto del directorio'}
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { key: 'first_name', label: 'Nombre' },
                    { key: 'last_name', label: 'Apellido' },
                    { key: 'email', label: 'Email *' },
                    { key: 'phone', label: 'Telefono' },
                    { key: 'job_title', label: 'Cargo' },
                    { key: 'department', label: 'Departamento' },
                    { key: 'company', label: 'Empresa' },
                    { key: 'phone_mobile', label: 'Celular' },
                  ].map(f => (
                    <div key={f.key}>
                      <label className="block text-[11px] text-[#605e5c] mb-1 uppercase font-medium">{f.label}</label>
                      <input placeholder={f.label}
                        value={(formData as any)[f.key] || ''}
                        onChange={e => setFormData(p => ({ ...p, [f.key]: e.target.value }))}
                        className="w-full px-3 py-2 border border-[#c8c6c4] rounded-md text-[13px] focus:border-[#0078d4] focus:ring-1 focus:ring-[#0078d4] outline-none" />
                    </div>
                  ))}
                </div>
                <div className="flex gap-2 mt-5 justify-end">
                  <button onClick={() => { setShowForm(false); setFormData({}); }}
                    className="px-4 py-2 border border-[#c8c6c4] text-[#605e5c] rounded-md text-[13px] hover:bg-[#f3f2f1] transition-colors">
                    Cancelar
                  </button>
                  <button onClick={handleSave} disabled={saving || !formData.email}
                    className="px-5 py-2 bg-[#0078d4] text-white rounded-md text-[13px] font-semibold hover:bg-[#106ebe] disabled:opacity-50 transition-colors">
                    {saving ? 'Guardando...' : 'Guardar'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ── Left: Contact list ── */}
          <div className={`${selected ? 'w-[55%]' : 'w-full'} border-r border-[#edebe9] overflow-y-auto transition-all`}>
            {loading && (
              <div className="flex items-center justify-center py-16 text-[13px] text-[#605e5c]">
                <svg className="w-5 h-5 animate-spin mr-2 text-[#0078d4]" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Cargando directorio...
              </div>
            )}

            {!loading && contacts.length === 0 && (
              <div className="flex flex-col items-center justify-center py-16 text-[#a19f9d]">
                <svg className="w-12 h-12 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
                    d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                <p className="text-[14px]">No se encontraron contactos</p>
                <p className="text-[12px] mt-1">Intenta ajustar los filtros de busqueda</p>
              </div>
            )}

            {/* ── List view ── */}
            {!loading && viewMode === 'list' && contacts.map(c => (
              <div key={c.id}
                className={`flex items-center gap-3 px-4 py-3 cursor-pointer border-b border-[#f3f2f1] transition-colors group ${
                  selected?.id === c.id ? 'bg-[#deecf9]' : 'hover:bg-[#f3f2f1]'
                }`}
                onClick={() => setSelected(c)}
                onDoubleClick={() => {
                  if (pickerMode && onPickContact) onPickContact(c, currentTarget);
                }}>
                <ContactAvatar contact={c} size={40} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[14px] font-semibold text-[#323130] truncate">{c.display_name}</span>
                    {c.source === 'mailbox' && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">Usuario</span>
                    )}
                  </div>
                  <div className="text-[12px] text-[#605e5c] truncate">{c.email}</div>
                  {(c.job_title || c.department) && (
                    <div className="text-[11px] text-[#a19f9d] truncate">
                      {[c.job_title, c.department].filter(Boolean).join(' - ')}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                  {pickerMode && onPickContact && (
                    <button onClick={e => { e.stopPropagation(); onPickContact(c, currentTarget); }}
                      className="w-7 h-7 rounded-full bg-[#0078d4] text-white flex items-center justify-center hover:bg-[#106ebe] transition-colors"
                      title={`Agregar a ${currentTarget === 'to' ? 'Para' : currentTarget === 'cc' ? 'CC' : 'CCO'}`}>
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
                      </svg>
                    </button>
                  )}
                  {(() => {
                    const s = copyStatus[c.id];
                    if (s === 'done') return <span className="text-[11px] text-green-600 font-medium">Copiado</span>;
                    if (s === 'exists') return <span className="text-[11px] text-[#a19f9d]">Ya existe</span>;
                    if (s === 'saving') return <span className="text-[11px] text-[#a19f9d]">...</span>;
                    return (
                      <button onClick={e => { e.stopPropagation(); handleCopyToPersonal(c.id); }}
                        className="w-7 h-7 rounded-full border border-[#0078d4] text-[#0078d4] flex items-center justify-center hover:bg-[#deecf9] transition-colors"
                        title="Copiar a mis contactos">
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
                        </svg>
                      </button>
                    );
                  })()}
                </div>
              </div>
            ))}

            {/* ── Cards view ── */}
            {!loading && viewMode === 'cards' && (
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 p-4">
                {contacts.map(c => (
                  <div key={c.id}
                    className={`rounded-lg border p-4 cursor-pointer transition-all hover:shadow-md ${
                      selected?.id === c.id ? 'border-[#0078d4] bg-[#deecf9]/30 shadow-md' : 'border-[#edebe9] hover:border-[#c8c6c4]'
                    }`}
                    onClick={() => setSelected(c)}
                    onDoubleClick={() => {
                      if (pickerMode && onPickContact) onPickContact(c, currentTarget);
                    }}>
                    <div className="flex flex-col items-center text-center">
                      <ContactAvatar contact={c} size={56} />
                      <div className="mt-2 font-semibold text-[14px] text-[#323130] truncate w-full">{c.display_name}</div>
                      {c.job_title && <div className="text-[12px] text-[#605e5c] truncate w-full">{c.job_title}</div>}
                      {c.department && <div className="text-[11px] text-[#a19f9d] truncate w-full">{c.department}</div>}
                      <div className="text-[11px] text-[#0078d4] truncate w-full mt-1">{c.email}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* ── Org view (grouped by department) ── */}
            {!loading && viewMode === 'org' && (
              <div className="p-4 space-y-4">
                {Object.entries(groupedByDept).sort(([a], [b]) => a.localeCompare(b)).map(([dept, members]) => (
                  <div key={dept} className="rounded-lg border border-[#edebe9] overflow-hidden">
                    <div className="bg-[#f3f2f1] px-4 py-2.5 flex items-center gap-2">
                      <svg className="w-4 h-4 text-[#605e5c]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                          d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                      </svg>
                      <span className="font-semibold text-[14px] text-[#323130]">{dept}</span>
                      <span className="text-[11px] text-[#a19f9d] ml-auto">{members.length} miembro{members.length !== 1 ? 's' : ''}</span>
                    </div>
                    <div>
                      {members.map(c => (
                        <div key={c.id}
                          className={`flex items-center gap-3 px-4 py-2.5 border-t border-[#f3f2f1] cursor-pointer transition-colors ${
                            selected?.id === c.id ? 'bg-[#deecf9]' : 'hover:bg-[#faf9f8]'
                          }`}
                          onClick={() => setSelected(c)}>
                          <ContactAvatar contact={c} size={32} />
                          <div className="flex-1 min-w-0">
                            <span className="text-[13px] font-semibold text-[#323130]">{c.display_name}</span>
                            {c.job_title && <span className="text-[12px] text-[#605e5c] ml-2">{c.job_title}</span>}
                          </div>
                          <span className="text-[11px] text-[#a19f9d] shrink-0">{c.email}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Right: Detail panel ── */}
          {selected && (
            <div className="w-[45%] overflow-y-auto bg-white">
              <div className="p-6">
                {/* Profile header */}
                <div className="flex flex-col items-center text-center mb-6">
                  <ContactAvatar contact={selected} size={80} />
                  <h3 className="mt-3 text-[20px] font-semibold text-[#323130]">{selected.display_name}</h3>
                  {selected.job_title && (
                    <p className="text-[14px] text-[#605e5c] mt-0.5">
                      {selected.job_title}
                      {selected.department ? ` - ${selected.department}` : ''}
                    </p>
                  )}
                  {selected.company && (
                    <p className="text-[13px] text-[#a19f9d] mt-0.5">{selected.company}</p>
                  )}
                </div>

                <div className="border-t border-[#edebe9] my-4" />

                {/* Contact fields */}
                <div className="space-y-3">
                  {/* Email */}
                  <div className="flex items-center gap-3 group">
                    <span className="text-[16px] shrink-0 w-6 text-center">&#9993;</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-[11px] text-[#a19f9d] uppercase font-medium">Email</div>
                      <div className="text-[13px] text-[#323130] truncate">{selected.email}</div>
                    </div>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button onClick={() => handleCopyField(selected.email, 'email')}
                        className="px-2 py-1 text-[11px] text-[#605e5c] border border-[#e1dfdd] rounded hover:bg-[#f3f2f1] transition-colors">
                        {copiedField === 'email' ? 'Copiado' : 'Copiar'}
                      </button>
                      <button onClick={() => handleSendEmail(selected)}
                        className="px-2 py-1 text-[11px] text-[#0078d4] border border-[#0078d4] rounded hover:bg-[#deecf9] transition-colors">
                        Enviar correo
                      </button>
                    </div>
                  </div>

                  {/* Phone */}
                  {selected.phone && (
                    <div className="flex items-center gap-3 group">
                      <span className="text-[16px] shrink-0 w-6 text-center">&#128222;</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-[11px] text-[#a19f9d] uppercase font-medium">Telefono</div>
                        <div className="text-[13px] text-[#323130]">{selected.phone}</div>
                      </div>
                      <button onClick={() => handleCopyField(selected.phone, 'phone')}
                        className="px-2 py-1 text-[11px] text-[#605e5c] border border-[#e1dfdd] rounded hover:bg-[#f3f2f1] opacity-0 group-hover:opacity-100 transition-all">
                        {copiedField === 'phone' ? 'Copiado' : 'Copiar'}
                      </button>
                    </div>
                  )}

                  {/* Mobile */}
                  {selected.phone_mobile && (
                    <div className="flex items-center gap-3 group">
                      <span className="text-[16px] shrink-0 w-6 text-center">&#128241;</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-[11px] text-[#a19f9d] uppercase font-medium">Celular</div>
                        <div className="text-[13px] text-[#323130]">{selected.phone_mobile}</div>
                      </div>
                      <button onClick={() => handleCopyField(selected.phone_mobile, 'mobile')}
                        className="px-2 py-1 text-[11px] text-[#605e5c] border border-[#e1dfdd] rounded hover:bg-[#f3f2f1] opacity-0 group-hover:opacity-100 transition-all">
                        {copiedField === 'mobile' ? 'Copiado' : 'Copiar'}
                      </button>
                    </div>
                  )}

                  {/* Location */}
                  {selected.location && (
                    <div className="flex items-center gap-3">
                      <span className="text-[16px] shrink-0 w-6 text-center">&#128205;</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-[11px] text-[#a19f9d] uppercase font-medium">Ubicacion</div>
                        <div className="text-[13px] text-[#323130]">{selected.location}</div>
                      </div>
                    </div>
                  )}

                  {/* Company */}
                  {selected.company && (
                    <div className="flex items-center gap-3">
                      <span className="text-[16px] shrink-0 w-6 text-center">&#127970;</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-[11px] text-[#a19f9d] uppercase font-medium">Empresa</div>
                        <div className="text-[13px] text-[#323130]">{selected.company}</div>
                      </div>
                    </div>
                  )}

                  {/* Notes */}
                  {selected.notes && (
                    <div className="flex items-start gap-3 mt-2">
                      <span className="text-[16px] shrink-0 w-6 text-center mt-0.5">&#128221;</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-[11px] text-[#a19f9d] uppercase font-medium">Notas</div>
                        <div className="text-[13px] text-[#605e5c] whitespace-pre-wrap">{selected.notes}</div>
                      </div>
                    </div>
                  )}
                </div>

                <div className="border-t border-[#edebe9] my-5" />

                {/* Action buttons */}
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={() => handleSendEmail(selected)}
                    className="flex items-center justify-center gap-2 px-3 py-2.5 bg-[#0078d4] text-white rounded-md text-[13px] font-semibold hover:bg-[#106ebe] transition-colors">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                    Enviar correo
                  </button>
                  <button onClick={() => handleCopyToPersonal(selected.id)}
                    className="flex items-center justify-center gap-2 px-3 py-2.5 border border-[#0078d4] text-[#0078d4] rounded-md text-[13px] font-semibold hover:bg-[#deecf9] transition-colors">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
                    </svg>
                    {copyStatus[selected.id] === 'done' ? 'Copiado' : copyStatus[selected.id] === 'exists' ? 'Ya existe' : 'A mis contactos'}
                  </button>
                  <button onClick={() => { setFormData(selected); setShowForm(true); }}
                    className="flex items-center justify-center gap-2 px-3 py-2.5 border border-[#c8c6c4] text-[#605e5c] rounded-md text-[13px] hover:bg-[#f3f2f1] transition-colors">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                    Editar
                  </button>
                  <button onClick={() => handleDelete(selected.id)}
                    className="flex items-center justify-center gap-2 px-3 py-2.5 border border-[#d13438] text-[#d13438] rounded-md text-[13px] hover:bg-[#fde7e9] transition-colors">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    Eliminar
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
