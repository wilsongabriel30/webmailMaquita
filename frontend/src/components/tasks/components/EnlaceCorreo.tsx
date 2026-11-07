// Tarea que salió de un correo marcado con bandera: de quién es y un enlace para abrir el mensaje.
import type { CorreoTarea } from '../types';
import { COLORS } from '../types';
import { urlCorreo } from './urlCorreo';

export function EnlaceCorreo({ correo }: { correo: CorreoTarea }) {
  return (
    <div style={{ padding: '12px 16px', fontSize: 13 }}>
      {correo.remitente && (
        <div style={{ color: COLORS.secondary, marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          De: {correo.remitente}
        </div>
      )}
      <a href={urlCorreo(correo)} style={{ color: COLORS.primary, display: 'inline-flex', alignItems: 'center', gap: 6, textDecoration: 'none' }}>
        <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
          <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22,6 12,13 2,6" />
        </svg>
        Abrir el correo
      </a>
    </div>
  );
}
