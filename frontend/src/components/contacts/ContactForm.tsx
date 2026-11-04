import { useState, useCallback, useId, useRef } from 'react';
import { Avatar } from './Avatar';
import { protegerEnter } from './tecladoContactos';
import type { ContactFormData } from './contactFormData';

/* Datos del formulario (todos los campos editables) */



/* ── Estilos compartidos ── */
const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 12px', fontSize: 14,
  border: '1px solid #8a8886', borderRadius: 4, outline: 'none',
  fontFamily: "'Segoe UI', Calibri, sans-serif", boxSizing: 'border-box',
};
const labelStyle: React.CSSProperties = { fontSize: 12, fontWeight: 600, color: '#605e5c', marginBottom: 4, display: 'block' };

/* ── Componente Field FUERA de ContactForm para evitar re-mount en cada keystroke ── */
function Field({ label: lbl, value, onChange, type = 'text', placeholder = '', error = '', inputRef }: {
  label: string; value: string; onChange: (val: string) => void; type?: string; placeholder?: string;
  error?: string; inputRef?: React.Ref<HTMLInputElement>;
}) {
  const id = useId();
  const idError = `${id}-error`;
  return (
    <div style={{ marginBottom: 12 }}>
      <label htmlFor={id} style={labelStyle}>{lbl}</label>
      <input id={id} ref={inputRef} style={{ ...inputStyle, borderColor: error ? '#a4262c' : '#8a8886' }}
        type={type} value={value}
        onChange={e => onChange(e.target.value)} placeholder={placeholder}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? idError : undefined}
        onFocus={e => { e.target.style.borderColor = error ? '#a4262c' : '#0078d4'; }}
        onBlur={e => { e.target.style.borderColor = error ? '#a4262c' : '#8a8886'; }} />
      {error && (
        <div id={idError} role="alert" style={{ color: '#a4262c', fontSize: 13, marginTop: 4, fontWeight: 600 }}>
          {error}
        </div>
      )}
    </div>
  );
}

/* Validación sencilla de una dirección de correo (usuario@dominio.ext). */
const RE_CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
function errorCorreo(valor: string, obligatorio: boolean): string {
  const v = valor.trim();
  if (!v) return obligatorio ? 'Escriba el correo del contacto.' : '';
  return RE_CORREO.test(v) ? '' : 'Esta dirección de correo no es válida. Ejemplo: nombre@ejemplo.com';
}

/* ── SectionHeader FUERA de ContactForm: botón nativo, se abre con Tab + Enter o Espacio ── */
function SectionHeader({ id, label, open, onToggle }: { id: string; label: string; open: boolean; onToggle: (id: string) => void }) {
  return (
    <button
      type="button"
      onClick={() => onToggle(id)}
      aria-expanded={open}
      aria-controls={`seccion-contacto-${id}`}
      style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '10px 0', width: '100%',
        cursor: 'pointer', fontSize: 14, fontWeight: 600, color: '#323130',
        border: 'none', borderBottom: '1px solid #edebe9', background: 'transparent',
        textAlign: 'left', fontFamily: 'inherit',
      }}
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"
        style={{ transform: open ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}>
        <polyline points="9,18 15,12 9,6" />
      </svg>
      {label}
    </button>
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

  const [errores, setErrores] = useState<Record<string, string>>({});
  const refEmail = useRef<HTMLInputElement>(null);
  const refEmail2 = useRef<HTMLInputElement>(null);
  const refEmail3 = useRef<HTMLInputElement>(null);

  const guardar = () => {
    const e: Record<string, string> = {
      email: errorCorreo(form.email, true),
      email2: errorCorreo(form.email2, false),
      email3: errorCorreo(form.email3, false),
    };
    setErrores(e);
    const primero = (['email', 'email2', 'email3'] as const).find(k => e[k]);
    if (primero) {
      setOpenSection(prev => ({ ...prev, contacto: true }));
      const ref = primero === 'email' ? refEmail : primero === 'email2' ? refEmail2 : refEmail3;
      setTimeout(() => ref.current?.focus(), 0);
      return;
    }
    onSave({ ...form, email: form.email.trim(), email2: form.email2.trim(), email3: form.email3.trim() });
  };

  const setCorreo = (key: 'email' | 'email2' | 'email3', v: string) => {
    set(key, v);
    if (errores[key]) setErrores(prev => ({ ...prev, [key]: '' }));
  };

  const toggleSection = useCallback((id: string) => {
    setOpenSection(prev => ({ ...prev, [id]: !prev[id] }));
  }, []);

  const displayName = form.display_name || `${form.first_name} ${form.last_name}`.trim() || 'Nuevo contacto';

  return (
    <div onKeyDown={protegerEnter} style={{ flex: 1, overflowY: 'auto', padding: 32, maxWidth: 600 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
        <Avatar name={displayName} size={56} />
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#323130' }}>{title}</h2>
      </div>

      {/* Seccion: Nombre */}
      <SectionHeader id="nombre" label="Nombre" open={!!openSection.nombre} onToggle={toggleSection} />
      {openSection.nombre && (
        <div id="seccion-contacto-nombre" style={{ padding: '12px 0' }}>
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
        <div id="seccion-contacto-contacto" style={{ padding: '12px 0' }}>
          <Field label="Email principal *" value={form.email} onChange={v => setCorreo('email', v)} type="email" placeholder="correo@ejemplo.com" error={errores.email} inputRef={refEmail} />
          <Field label="Email 2" value={form.email2} onChange={v => setCorreo('email2', v)} type="email" error={errores.email2} inputRef={refEmail2} />
          <Field label="Email 3" value={form.email3} onChange={v => setCorreo('email3', v)} type="email" error={errores.email3} inputRef={refEmail3} />
          <Field label="Teléfono" value={form.phone} onChange={v => set('phone', v)} placeholder="+593 ..." />
          <Field label="Celular" value={form.phone_mobile} onChange={v => set('phone_mobile', v)} />
          <Field label="Teléfono trabajo" value={form.phone_work} onChange={v => set('phone_work', v)} />
          <Field label="Teléfono casa" value={form.phone_home} onChange={v => set('phone_home', v)} />
          <Field label="Fax" value={form.fax} onChange={v => set('fax', v)} />
        </div>
      )}

      {/* Seccion: Trabajo */}
      <SectionHeader id="trabajo" label="Trabajo" open={!!openSection.trabajo} onToggle={toggleSection} />
      {openSection.trabajo && (
        <div id="seccion-contacto-trabajo" style={{ padding: '12px 0' }}>
          <Field label="Empresa" value={form.company} onChange={v => set('company', v)} placeholder="Empresa u organización" />
          <Field label="Organización" value={form.organization} onChange={v => set('organization', v)} />
          <Field label="Cargo" value={form.job_title} onChange={v => set('job_title', v)} />
          <Field label="Departamento" value={form.department} onChange={v => set('department', v)} />
        </div>
      )}

      {/* Seccion: Dirección */}
      <SectionHeader id="direccion" label="Dirección" open={!!openSection.direccion} onToggle={toggleSection} />
      {openSection.direccion && (
        <div id="seccion-contacto-direccion" style={{ padding: '12px 0' }}>
          <Field label="Calle" value={form.address_street} onChange={v => set('address_street', v)} />
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}><Field label="Ciudad" value={form.address_city} onChange={v => set('address_city', v)} /></div>
            <div style={{ flex: 1 }}><Field label="Provincia/Estado" value={form.address_state} onChange={v => set('address_state', v)} /></div>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}><Field label="Código postal" value={form.address_zip} onChange={v => set('address_zip', v)} /></div>
            <div style={{ flex: 1 }}><Field label="País" value={form.address_country} onChange={v => set('address_country', v)} /></div>
          </div>
        </div>
      )}

      {/* Seccion: Personal */}
      <SectionHeader id="personal" label="Personal" open={!!openSection.personal} onToggle={toggleSection} />
      {openSection.personal && (
        <div id="seccion-contacto-personal" style={{ padding: '12px 0' }}>
          <Field label="Cumpleaños" value={form.birthday} onChange={v => set('birthday', v)} type="date" />
          <Field label="Sitio web" value={form.website} onChange={v => set('website', v)} placeholder="https://..." />
          <Field label="Mensajería instantánea" value={form.im_address} onChange={v => set('im_address', v)} />
        </div>
      )}

      {/* Seccion: Notas */}
      <SectionHeader id="notas" label="Notas" open={!!openSection.notas} onToggle={toggleSection} />
      {openSection.notas && (
        <div id="seccion-contacto-notas" style={{ padding: '12px 0' }}>
          <label htmlFor="contacto-notas" style={labelStyle}>Notas</label>
          <textarea
            id="contacto-notas"
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
          type="button"
          onClick={guardar}
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
