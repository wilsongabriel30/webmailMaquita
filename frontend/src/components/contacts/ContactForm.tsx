import { useState } from 'react';
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

  const set = (key: keyof ContactFormData, val: string) => setForm({ ...form, [key]: val });

  const displayName = form.display_name || `${form.first_name} ${form.last_name}`.trim() || 'Nuevo contacto';

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '8px 12px', fontSize: 14,
    border: '1px solid #8a8886', borderRadius: 4, outline: 'none',
    fontFamily: "'Segoe UI', Calibri, sans-serif", boxSizing: 'border-box',
  };
  const labelStyle: React.CSSProperties = { fontSize: 12, fontWeight: 600, color: '#605e5c', marginBottom: 4, display: 'block' };

  const SectionHeader = ({ id, label }: { id: string; label: string }) => (
    <div
      onClick={() => setOpenSection({ ...openSection, [id]: !openSection[id] })}
      style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '10px 0',
        cursor: 'pointer', fontSize: 14, fontWeight: 600, color: '#323130',
        borderBottom: '1px solid #edebe9',
      }}
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
        style={{ transform: openSection[id] ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}>
        <polyline points="9,18 15,12 9,6" />
      </svg>
      {label}
    </div>
  );

  const Field = ({ label: lbl, field, type = 'text', placeholder = '' }: {
    label: string; field: keyof ContactFormData; type?: string; placeholder?: string;
  }) => (
    <div style={{ marginBottom: 12 }}>
      <label style={labelStyle}>{lbl}</label>
      <input style={inputStyle} type={type} value={form[field]}
        onChange={e => set(field, e.target.value)} placeholder={placeholder}
        onFocus={e => { e.target.style.borderColor = '#0078d4'; }}
        onBlur={e => { e.target.style.borderColor = '#8a8886'; }} />
    </div>
  );

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: 32, maxWidth: 600 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
        <Avatar name={displayName} size={56} />
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#323130' }}>{title}</h2>
      </div>

      {/* Sección: Nombre */}
      <SectionHeader id="nombre" label="Nombre" />
      {openSection.nombre && (
        <div style={{ padding: '12px 0' }}>
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}><Field label="Nombre" field="first_name" placeholder="Nombre" /></div>
            <div style={{ flex: 1 }}><Field label="Apellido" field="last_name" placeholder="Apellido" /></div>
          </div>
          <Field label="Nombre para mostrar" field="display_name" placeholder="Se calcula automáticamente" />
          <Field label="Apodo" field="nickname" />
        </div>
      )}

      {/* Sección: Contacto */}
      <SectionHeader id="contacto" label="Información de contacto" />
      {openSection.contacto && (
        <div style={{ padding: '12px 0' }}>
          <Field label="Email principal *" field="email" type="email" placeholder="correo@ejemplo.com" />
          <Field label="Email 2" field="email2" type="email" />
          <Field label="Email 3" field="email3" type="email" />
          <Field label="Teléfono" field="phone" placeholder="+593 ..." />
          <Field label="Celular" field="phone_mobile" />
          <Field label="Teléfono trabajo" field="phone_work" />
          <Field label="Teléfono casa" field="phone_home" />
          <Field label="Fax" field="fax" />
        </div>
      )}

      {/* Sección: Trabajo */}
      <SectionHeader id="trabajo" label="Trabajo" />
      {openSection.trabajo && (
        <div style={{ padding: '12px 0' }}>
          <Field label="Empresa" field="company" placeholder="Empresa u organización" />
          <Field label="Organización" field="organization" />
          <Field label="Cargo" field="job_title" />
          <Field label="Departamento" field="department" />
        </div>
      )}

      {/* Sección: Dirección */}
      <SectionHeader id="direccion" label="Dirección" />
      {openSection.direccion && (
        <div style={{ padding: '12px 0' }}>
          <Field label="Calle" field="address_street" />
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}><Field label="Ciudad" field="address_city" /></div>
            <div style={{ flex: 1 }}><Field label="Provincia/Estado" field="address_state" /></div>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}><Field label="Código postal" field="address_zip" /></div>
            <div style={{ flex: 1 }}><Field label="País" field="address_country" /></div>
          </div>
        </div>
      )}

      {/* Sección: Personal */}
      <SectionHeader id="personal" label="Personal" />
      {openSection.personal && (
        <div style={{ padding: '12px 0' }}>
          <Field label="Cumpleaños" field="birthday" type="date" />
          <Field label="Sitio web" field="website" placeholder="https://..." />
          <Field label="Mensajería instantánea" field="im_address" />
        </div>
      )}

      {/* Sección: Notas */}
      <SectionHeader id="notas" label="Notas" />
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
