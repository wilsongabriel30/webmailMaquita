// Franja para activar las notificaciones del navegador (F5): sin permiso, los recordatorios y los avisos de
// «Vence hoy» solo se ven con el webmail en pantalla. Se puede cerrar y no vuelve a salir en este navegador.
import { useState } from 'react';
import { pedirPermisoNotificacion, permisoNotificacion } from '../../../lib/notificacionSegura';
import { COLORS } from '../types';

const CLAVE = 'tareas_aviso_notificaciones_cerrado';

function cerradoAntes(): boolean {
  try { return localStorage.getItem(CLAVE) === '1'; } catch { return false; }
}

export function AvisoNotificaciones() {
  const [visible, setVisible] = useState(() => permisoNotificacion() === 'default' && !cerradoAntes());
  if (!visible) return null;
  const cerrar = () => {
    try { localStorage.setItem(CLAVE, '1'); } catch { /* sin almacenamiento: solo se oculta ahora */ }
    setVisible(false);
  };
  return (
    <div role="note" style={{
      margin: '0 24px 8px', padding: '8px 12px', background: COLORS.activeBg, borderRadius: 4, fontSize: 13,
      color: COLORS.text, display: 'flex', alignItems: 'center', gap: 12,
    }}>
      <span style={{ flex: 1 }}>Activa las notificaciones del navegador para recibir los recordatorios de tus tareas.</span>
      <button type="button" onClick={async () => { await pedirPermisoNotificacion(); setVisible(false); }}
        style={{ background: COLORS.primary, color: 'white', border: 'none', borderRadius: 4, padding: '5px 12px', fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
        Activar
      </button>
      <button type="button" aria-label="No volver a mostrar" onClick={cerrar}
        style={{ background: 'none', border: 'none', cursor: 'pointer', color: COLORS.secondary, fontSize: 16 }}>&times;</button>
    </div>
  );
}
