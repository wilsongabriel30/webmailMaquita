import { GravatarAvatar } from './GravatarAvatar';
import { InteractionHistory } from './InteractionHistory';
import { RemindersPanel } from './RemindersPanel';
import { RelationshipsPanel } from './RelationshipsPanel';
import { CustomFieldsDisplay } from './CustomFieldsManager';
import { SharedNotesPanel } from './SharedNotesPanel';
import { SignatureEnrichment } from './SignatureEnrichment';
import type { Contact } from './types';
import { formatDate } from './types';

interface Props {
  contact: Contact;
  onSendEmail: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onRestore?: () => void;
  onNavigateToContact?: (contactId: number) => void;
}

function DetailRow({ icon, label, value, href }: {
  icon: React.ReactNode; label: string; value: string; href?: string;
}) {
  if (!value) return null;
  return (
    <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'flex-start' }}>
      <span style={{ flexShrink: 0, marginTop: 2, color: '#605e5c' }}>{icon}</span>
      <div>
        <div style={{ fontSize: 12, color: '#a19f9d', marginBottom: 2 }}>{label}</div>
        {href ? (
          <a href={href} target="_blank" rel="noreferrer"
            style={{ fontSize: 14, color: '#0078d4', textDecoration: 'none' }}>{value}</a>
        ) : (
          <div style={{ fontSize: 14, color: '#323130', whiteSpace: 'pre-wrap' }}>{value}</div>
        )}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const hasContent = Array.isArray(children)
    ? children.some(c => c !== null && c !== undefined && c !== false)
    : children !== null && children !== undefined && children !== false;
  if (!hasContent) return null;
  return (
    <div style={{ marginBottom: 24 }}>
      <h4 style={{ fontSize: 13, fontWeight: 600, color: '#605e5c', margin: '0 0 12px', textTransform: 'uppercase', letterSpacing: 0.5 }}>
        {title}
      </h4>
      {children}
    </div>
  );
}

// Iconos
const mailIcon = <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22,6 12,13 2,6" /></svg>;
const phoneIcon = <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z" /></svg>;
const buildingIcon = <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" /><polyline points="9,22 9,12 15,12 15,22" /></svg>;
const mapIcon = <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" /><circle cx="12" cy="10" r="3" /></svg>;
const cakeIcon = <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M20 21v-8a2 2 0 00-2-2H6a2 2 0 00-2 2v8" /><path d="M4 16s.5-1 2-1 2.5 2 4 2 2.5-2 4-2 2.5 2 4 2 2-1 2-1" /><path d="M2 21h20" /><path d="M7 8v3" /><path d="M12 8v3" /><path d="M17 8v3" /><path d="M7 4h.01" /><path d="M12 4h.01" /><path d="M17 4h.01" /></svg>;
const globeIcon = <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="10" /><line x1="2" y1="12" x2="22" y2="12" /><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" /></svg>;
const noteIcon = <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14,2 14,8 20,8" /></svg>;

export function ContactDetail({ contact, onSendEmail, onEdit, onDelete, onRestore, onNavigateToContact }: Props) {
  const isDeleted = !!contact.deleted_at;
  const address = [contact.address_street, contact.address_city, contact.address_state, contact.address_zip, contact.address_country]
    .filter(Boolean).join(', ');

  const sourceLabels: Record<string, string> = {
    manual: 'Creado manualmente',
    import: 'Importado desde CSV',
    from_email: 'Agregado desde correo',
    autocollect: 'Recopilado automáticamente',
  };

  return (
    <div style={{ flex: 1, overflowY: 'auto' }}>
      {/* Header */}
      <div style={{ padding: '32px 32px 24px', borderBottom: '1px solid #edebe9', background: '#faf9f8' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <GravatarAvatar name={contact.display_name} email={contact.email} size={72} />
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <h2 style={{ margin: 0, fontSize: 24, fontWeight: 600, color: '#323130' }}>
                {contact.display_name || '(Sin nombre)'}
              </h2>
              {contact.is_favorite && (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="#ffb900" stroke="#ffb900" strokeWidth="1">
                  <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" />
                </svg>
              )}
            </div>
            {(contact.job_title || contact.company || contact.organization) && (
              <p style={{ margin: '4px 0 0', fontSize: 14, color: '#605e5c' }}>
                {[contact.job_title, contact.company || contact.organization].filter(Boolean).join(' · ')}
              </p>
            )}
            {/* Categorías */}
            {contact.categories?.length > 0 && (
              <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                {contact.categories.map(cat => (
                  <span key={cat.id} style={{
                    fontSize: 11, padding: '2px 8px', borderRadius: 10,
                    background: cat.color + '20', color: cat.color,
                    border: `1px solid ${cat.color}40`,
                  }}>{cat.name}</span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Botones de acción */}
        <div style={{ display: 'flex', gap: 8, marginTop: 20, flexWrap: 'wrap' }}>
          {!isDeleted && (
            <>
              <button onClick={onSendEmail} style={{
                padding: '8px 16px', fontSize: 13, fontWeight: 600,
                border: 'none', borderRadius: 4, background: '#0078d4',
                color: '#fff', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 6,
              }}>
                {mailIcon} Enviar correo
              </button>
              <button onClick={onEdit} style={{
                padding: '8px 16px', fontSize: 13, fontWeight: 600,
                border: '1px solid #8a8886', borderRadius: 4, background: '#fff',
                color: '#323130', cursor: 'pointer',
              }}>Editar</button>
              <button onClick={onDelete} style={{
                padding: '8px 16px', fontSize: 13, fontWeight: 600,
                border: '1px solid #d13438', borderRadius: 4, background: '#fff',
                color: '#d13438', cursor: 'pointer',
              }}>Eliminar</button>
            </>
          )}
          {isDeleted && onRestore && (
            <>
              <button onClick={onRestore} style={{
                padding: '8px 16px', fontSize: 13, fontWeight: 600,
                border: 'none', borderRadius: 4, background: '#0078d4',
                color: '#fff', cursor: 'pointer',
              }}>Restaurar</button>
              <button onClick={onDelete} style={{
                padding: '8px 16px', fontSize: 13, fontWeight: 600,
                border: '1px solid #d13438', borderRadius: 4, background: '#fff',
                color: '#d13438', cursor: 'pointer',
              }}>Eliminar permanente</button>
            </>
          )}
        </div>
      </div>

      {/* Detalles */}
      <div style={{ padding: 32 }}>
        <Section title="Información de contacto">
          <DetailRow icon={mailIcon} label="Email principal" value={contact.email} href={`mailto:${contact.email}`} />
          <DetailRow icon={mailIcon} label="Email 2" value={contact.email2} href={contact.email2 ? `mailto:${contact.email2}` : undefined} />
          <DetailRow icon={mailIcon} label="Email 3" value={contact.email3} href={contact.email3 ? `mailto:${contact.email3}` : undefined} />
          <DetailRow icon={phoneIcon} label="Teléfono" value={contact.phone} />
          <DetailRow icon={phoneIcon} label="Celular" value={contact.phone_mobile} />
          <DetailRow icon={phoneIcon} label="Trabajo" value={contact.phone_work} />
          <DetailRow icon={phoneIcon} label="Casa" value={contact.phone_home} />
        </Section>

        <Section title="Trabajo">
          <DetailRow icon={buildingIcon} label="Empresa" value={contact.company || contact.organization} />
          <DetailRow icon={buildingIcon} label="Cargo" value={contact.job_title} />
          <DetailRow icon={buildingIcon} label="Departamento" value={contact.department} />
        </Section>

        <Section title="Dirección">
          <DetailRow icon={mapIcon} label="Dirección" value={address} />
        </Section>

        <Section title="Personal">
          <DetailRow icon={cakeIcon} label="Cumpleaños" value={contact.birthday ? formatDate(contact.birthday) : ''} />
          <DetailRow icon={globeIcon} label="Sitio web" value={contact.website} href={contact.website} />
        </Section>

        <Section title="Notas">
          <DetailRow icon={noteIcon} label="Notas" value={contact.notes} />
        </Section>

        {/* Recordatorios */}
        <RemindersPanel contactId={contact.id} />

        {/* Relaciones */}
        <RelationshipsPanel contactId={contact.id} onNavigateToContact={onNavigateToContact || (() => {})} />

        {/* Campos personalizados */}
        <CustomFieldsDisplay contactId={contact.id} />

        {/* Datos detectados en firmas */}
        <SignatureEnrichment contactId={contact.id} />

        {/* Notas compartidas */}
        <SharedNotesPanel contactId={contact.id} />

        {/* Historial de interacciones */}
        <InteractionHistory contactId={contact.id} contactEmail={contact.email} />

        {/* Metadata */}
        <div style={{ marginTop: 24, fontSize: 12, color: '#a19f9d', lineHeight: 1.8 }}>
          <div>Creado el {formatDate(contact.created_at)}</div>
          <div>Origen: {sourceLabels[contact.source] || contact.source}</div>
          {contact.last_contacted_at && <div>Último contacto: {formatDate(contact.last_contacted_at)}</div>}
        </div>
      </div>
    </div>
  );
}
