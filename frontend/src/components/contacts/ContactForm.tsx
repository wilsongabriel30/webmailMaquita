import { useState, useCallback } from 'react';
import { Avatar } from './Avatar';
import type { Contact } from './types';

/* Datos del formulario (todos los campos editables) */
export interface ContactFormData {
  first_name: string;
  last_name: string;
  display_name: string;
  nickname: string;
  email: string;
  email2: string;
  email3: string;
  phone: string;
  phone_mobile: string;
  phone_work: string;
  phone_home: string;
  fax: string;
  company: string;
  organization: string;
  job_title: string;
  department: string;
  address_street: string;
  address_city: string;
  address_state: string;
  address_zip: string;
  address_country: string;
  birthday: string;
  website: string;
  im_address: string;
  notes: string;
}

export function emptyFormData(): ContactFormData {
  return {
    first_name: '', last_name: '', display_name: '', nickname: '',
    email: '', email2: '', email3: '',
    phone: '', phone_mobile: '', phone_work: '', phone_home: '', fax: '',
    company: '', organization: '', job_title: '', department: '',
    address_street: '', address_city: '', address_state: '', address_zip: '', address_country: '',
    birthday: '', website: '', im_address: '', notes: '',
  };
}

export function contactToFormData(c: Contact): ContactFormData {
  return {
    first_name: c.first_name || '', last_name: c.last_name || '',
    display_name: c.display_name || '', nickname: c.nickname || '',
    email: c.email || '', email2: c.email2 || '', email3: c.email3 || '',
    phone: c.phone || '', phone_mobile: c.phone_mobile || '',
    phone_work: c.phone_work || '', phone_home: c.phone_home || '', fax: c.fax || '',
    company: c.company || '', organization: c.organization || '',
    job_title: c.job_title || '', department: c.department || '',
    address_street: c.address_street || '', address_city: c.address_city || '',
    address_state: c.address_state || '', address_zip: c.address_zip || '',
    address_country: c.address_country || '',
    birthday: c.birthday || '', website: c.website || '',
    im_address: c.im_address || '', notes: c.notes || '',
  };
}

/* ── Estilos compartidos ── */
const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 12px', fontSize: 14,
  border: '1px solid #8a8886', borderRadius: 4, outline: 'none',
  fontFamily: "'Segoe UI', Calibri, sans-serif", boxSizing: 'border-box',
};
const labelStyle: React.CSSProperties = { fontSize: 12, fontWeight: 600, color: '#605e5c', marginBottom: 4, display: 'block' };

/* ── Componente Field FUERA de ContactForm para evitar re-mount en cada keystroke ── */
function Field({ label: lbl, value, onChange, type = 'text', placeholder = '' }: {
  label: string; value: string; onChange: (val: string) => void; type?: string; placeholder?: string;
}) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={labelStyle}>{lbl}</label>
      <input style={inputStyle} type={type} value={value}
        onChange={e => onChange(e.target.value)} placeholder={placeholder}
        onFocus={e => { e.target.style.borderColor = '#0078d4'; }}
        onBlur={e => { e.target.style.borderColor = '#8a8886'; }} />
    </div>
  );
}

/* ── SectionHeader FUERA de ContactForm ── */
function SectionHeader({ id, label, open, onToggle }: { id: string; label: string; open: boolean; onToggle: (id: string) => void }) {
  return (
    <div
      onClick={() => onToggle(id)}
      style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '10px 0',
        cursor: 'pointer', fontSize: 14, fontWeight: 600, color: '#323130',
        borderBottom: '1px solid #edebe9',
      }}
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
        style={{ transform: open ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}>
        <polyline points="9,18 15,12 9,6" />
      </svg>
      {label}
    </div>
  );
}

interface Props {
  initial: ContactFormData;
  onSave: (data: ContactFormData) => void;
  onCancel: () => void;
  saving: boolean;
  title: string;
}

export function ContactForm({ initial, onSave, onCancel, saving, title }: Props) {
  const [form, setForm] = useState<ContactFormData>(initial);
  const [openSection, setOpenSection] = useState<Record<string, boolean>>({
    nombre: true, contacto: true, trabajo: false, direccion: false, personal: false, notas: false,
  });

  const set = useCallback((key: keyof ContactFormData, val: string) => {
    setForm(prev => {
      const next = { ...prev, [key]: val };
      // Autocalcular "Nombre para mostrar" = Nombre + Apellido, mientras el
      // usuario no lo haya personalizado (vacio o igual al auto-generado).
      if (key === 'first_name' || key === 'last_name') {
        const prevAuto = `${prev.first_name} ${prev.last_name}`.trim();
        if (!prev.display_name || prev.display_name === prevAuto) {
          next.display_name = `${next.first_name} ${next.last_name}`.trim();
        }
      }
      return next;
    });
  }, []);

  const toggleSection = useCallback((id: string) => {
    setOpenSection(prev => ({ ...prev, [id]: !prev[id] }));
  }, []);

  const displayName = form.display_name || `${form.first_name} ${form.last_name}`.trim() || 'Nuevo contacto';

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: 32, maxWidth: 600 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
        <Avatar name={displayName} size={56} />
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#323130' }}>{title}</h2>
      </div>

      {/* Seccion: Nombre */}
      <SectionHeader id="nombre" label="Nombre" open={!!openSection.nombre} onToggle={toggleSection} />
      {openSection.nombre && (
        <div style={{ padding: '12px 0' }}>
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}><Field label="Nombre" value={form.first_name} onChange={v => set('first_name', v)} placeholder="Nombre" /></div>
            <div style={{ flex: 1 }}><Field label="Apellido" value={form.last_name} onChange={v => set('last_name', v)} placeholder="Apellido" /></div>
          </div>
          <Field label="Nombre para mostrar" value={form.display_name} onChange={v => set('display_name', v)} placeholder="Se calcula automáticamente" />
          <Field label="Apodo" value={form.nickname} onChange={v => set('nickname', v)} />
        </div>
      )}

      {/* Seccion: Contacto */}
      <SectionHeader id="contacto" label="Información de contacto" open={!!openSection.contacto} onToggle={toggleSection} />
      {openSection.contacto && (
        <div style={{ padding: '12px 0' }}>
          <Field label="Email principal *" value={form.email} onChange={v => set('email', v)} type="email" placeholder="correo@ejemplo.com" />
          <Field label="Email 2" value={form.email2} onChange={v => set('email2', v)} type="email" />
          <Field label="Email 3" value={form.email3} onChange={v => set('email3', v)} type="email" />
          <Field label="Telefono" value={form.phone} onChange={v => set('phone', v)} placeholder="+593 ..." />
          <Field label="Celular" value={form.phone_mobile} onChange={v => set('phone_mobile', v)} />
          <Field label="Telefono trabajo" value={form.phone_work} onChange={v => set('phone_work', v)} />
          <Field label="Telefono casa" value={form.phone_home} onChange={v => set('phone_home', v)} />
          <Field label="Fax" value={form.fax} onChange={v => set('fax', v)} />
        </div>
      )}

      {/* Seccion: Trabajo */}
      <SectionHeader id="trabajo" label="Trabajo" open={!!openSection.trabajo} onToggle={toggleSection} />
      {openSection.trabajo && (
        <div style={{ padding: '12px 0' }}>
          <Field label="Empresa" value={form.company} onChange={v => set('company', v)} placeholder="Empresa u organizacion" />
          <Field label="Organizacion" value={form.organization} onChange={v => set('organization', v)} />
          <Field label="Cargo" value={form.job_title} onChange={v => set('job_title', v)} />
          <Field label="Departamento" value={form.department} onChange={v => set('department', v)} />
        </div>
      )}

      {/* Seccion: Dirección */}
      <SectionHeader id="direccion" label="Dirección" open={!!openSection.direccion} onToggle={toggleSection} />
      {openSection.direccion && (
        <div style={{ padding: '12px 0' }}>
          <Field label="Calle" value={form.address_street} onChange={v => set('address_street', v)} />
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}><Field label="Ciudad" value={form.address_city} onChange={v => set('address_city', v)} /></div>
            <div style={{ flex: 1 }}><Field label="Provincia/Estado" value={form.address_state} onChange={v => set('address_state', v)} /></div>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}><Field label="Codigo postal" value={form.address_zip} onChange={v => set('address_zip', v)} /></div>
            <div style={{ flex: 1 }}><Field label="Pais" value={form.address_country} onChange={v => set('address_country', v)} /></div>
          </div>
        </div>
      )}

      {/* Seccion: Personal */}
      <SectionHeader id="personal" label="Personal" open={!!openSection.personal} onToggle={toggleSection} />
      {openSection.personal && (
        <div style={{ padding: '12px 0' }}>
          <Field label="Cumpleanos" value={form.birthday} onChange={v => set('birthday', v)} type="date" />
          <Field label="Sitio web" value={form.website} onChange={v => set('website', v)} placeholder="https://..." />
          <Field label="Mensajeria instantanea" value={form.im_address} onChange={v => set('im_address', v)} />
        </div>
      )}

      {/* Seccion: Notas */}
      <SectionHeader id="notas" label="Notas" open={!!openSection.notas} onToggle={toggleSection} />
      {openSection.notas && (
        <div style={{ padding: '12px 0' }}>
          <textarea
            style={{ ...inputStyle, minHeight: 100, resize: 'vertical' }}
            value={form.notes}
            onChange={e => set('notes', e.target.value)}
            placeholder="Notas adicionales..."
            onFocus={e => { e.target.style.borderColor = '#0078d4'; }}
            onBlur={e => { e.target.style.borderColor = '#8a8886'; }}
          />
        </div>
      )}

      {/* Botones */}
      <div style={{ display: 'flex', gap: 8, marginTop: 20, paddingBottom: 32 }}>
        <button
          onClick={() => onSave(form)}
          disabled={saving || !form.email.trim()}
          style={{
            padding: '8px 24px', fontSize: 13, fontWeight: 600,
            border: 'none', borderRadius: 4,
            background: !form.email.trim() ? '#c8c6c4' : '#0078d4',
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
