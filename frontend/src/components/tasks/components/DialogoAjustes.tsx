// Configuración de Tareas (la ⚙ de la barra, como en To Do, F6): confirmar antes de eliminar, importantes arriba,
// sonido al completar, qué listas inteligentes se ven y avisos por correo de las listas compartidas.
import { useEffect } from 'react';
import { COLORS, SMART_LISTS } from '../types';
import type { Ajustes } from '../hooks/useAjustes';

const OCULTABLES = ['important', 'planned', 'assigned', 'flagged'];

function Interruptor({ etiqueta, ayuda, valor, onCambiar }: { etiqueta: string; ayuda?: string; valor: boolean; onCambiar: (v: boolean) => void }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0', cursor: 'pointer' }}>
      <span style={{ flex: 1 }}>
        <span style={{ display: 'block', fontSize: 14, color: COLORS.text }}>{etiqueta}</span>
        {ayuda && <span style={{ display: 'block', fontSize: 12, color: COLORS.secondary }}>{ayuda}</span>}
      </span>
      <input type="checkbox" role="switch" checked={valor} onChange={e => onCambiar(e.target.checked)}
        style={{ width: 18, height: 18, accentColor: COLORS.primary, cursor: 'pointer' }} />
    </label>
  );
}

const titulo = { margin: '16px 0 0', fontSize: 13, fontWeight: 600, color: COLORS.secondary } as const;

export function DialogoAjustes({ ajustes, error, onCambiar, onCerrar }: {
  ajustes: Ajustes; error: string; onCambiar: (c: Partial<Ajustes>) => void; onCerrar: () => void;
}) {
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => { if (e.key === 'Escape') onCerrar(); };
    window.addEventListener('keydown', tecla);
    return () => window.removeEventListener('keydown', tecla);
  }, [onCerrar]);
  const alternarLista = (id: string, ver: boolean) =>
    onCambiar({ listas_ocultas: ver ? ajustes.listas_ocultas.filter(x => x !== id) : [...ajustes.listas_ocultas, id] });

  return (
    <div role="presentation" onClick={onCerrar}
      style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.3)', display: 'flex', justifyContent: 'flex-end' }}>
      <div role="dialog" aria-modal="true" aria-label="Configuración de Tareas" onClick={e => e.stopPropagation()}
        style={{
          width: 360, maxWidth: '100%', height: '100%', overflowY: 'auto', background: 'white', padding: '16px 24px',
          boxSizing: 'border-box', boxShadow: '-4px 0 16px rgba(0,0,0,0.15)', fontFamily: "'Segoe UI', system-ui, sans-serif",
        }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <h2 style={{ flex: 1, margin: 0, fontSize: 18, fontWeight: 600, color: COLORS.text }}>Configuración</h2>
          <button type="button" aria-label="Cerrar" onClick={onCerrar}
            style={{ background: 'none', border: 'none', fontSize: 22, cursor: 'pointer', color: COLORS.secondary }}>&times;</button>
        </div>

        <h3 style={titulo}>General</h3>
        <Interruptor etiqueta="Confirmar antes de eliminar" valor={ajustes.confirmar_eliminar}
          onCambiar={v => onCambiar({ confirmar_eliminar: v })} />
        <Interruptor etiqueta="Mover las tareas con estrella arriba" valor={ajustes.importantes_arriba}
          onCambiar={v => onCambiar({ importantes_arriba: v })} />
        <Interruptor etiqueta="Reproducir sonido al completar" valor={ajustes.sonido_completar}
          onCambiar={v => onCambiar({ sonido_completar: v })} />

        <h3 style={titulo}>Listas inteligentes</h3>
        {SMART_LISTS.filter(s => OCULTABLES.includes(s.id)).map(s => (
          <Interruptor key={s.id} etiqueta={s.name} valor={!ajustes.listas_ocultas.includes(s.id)}
            onCambiar={v => alternarLista(s.id, v)} />
        ))}

        <h3 style={titulo}>Notificaciones</h3>
        <Interruptor etiqueta="Avisos por correo" ayuda="Recibir también por correo los avisos de mis listas compartidas"
          valor={ajustes.avisos_correo} onCambiar={v => onCambiar({ avisos_correo: v })} />

        {error && <div role="alert" style={{ marginTop: 8, fontSize: 12, color: '#d13438' }}>{error}</div>}
      </div>
    </div>
  );
}
