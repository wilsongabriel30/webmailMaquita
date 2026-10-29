// Panel «Sugerencias» de Mi día (como en To Do, F6): tareas que todavía no están en Mi día, agrupadas en vencidas,
// de hoy, próximas y agregadas recientemente. «+» la suma a Mi día; el círculo la completa.
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../../api/client';
import type { Task } from '../types';
import { COLORS } from '../types';

interface Sugerencias { vencidas: Task[]; hoy: Task[]; proximas: Task[]; recientes: Task[] }

const GRUPOS: { clave: keyof Sugerencias; titulo: string }[] = [
  { clave: 'vencidas', titulo: 'Vencidas' },
  { clave: 'hoy', titulo: 'Vencen hoy' },
  { clave: 'proximas', titulo: 'Próximas' },
  { clave: 'recientes', titulo: 'Agregadas recientemente' },
];

interface Props {
  onCerrar: () => void;
  onAgregarAMiDia: (id: string) => Promise<void> | void;
  onCompletar: (id: string) => Promise<void> | void;
}

function fecha(d?: string | null): string {
  if (!d) return '';
  const [a, m, dia] = d.slice(0, 10).split('-').map(Number);
  return new Date(a, m - 1, dia).toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short' });
}

export function PanelSugerencias({ onCerrar, onAgregarAMiDia, onCompletar }: Props) {
  const [datos, setDatos] = useState<Sugerencias | null>(null);
  const [error, setError] = useState('');

  const cargar = useCallback(() => {
    api.get<Sugerencias>('/tasks/sugerencias').then(d => { setDatos(d); setError(''); })
      .catch(() => setError('No se pudieron cargar las sugerencias'));
  }, []);
  useEffect(() => {
    let vigente = true;
    api.get<Sugerencias>('/tasks/sugerencias').then(d => { if (vigente) setDatos(d); })
      .catch(() => { if (vigente) setError('No se pudieron cargar las sugerencias'); });
    return () => { vigente = false; };
  }, []);

  // Se quita al momento y luego se pide de nuevo (otra sugerencia puede ocupar su lugar).
  const quitar = async (id: string, accion: (id: string) => Promise<void> | void) => {
    setDatos(d => d && Object.fromEntries(Object.entries(d).map(([k, v]) => [k, (v as Task[]).filter(t => t.id !== id)])) as unknown as Sugerencias);
    await accion(id);
    cargar();
  };

  const vacio = datos && GRUPOS.every(g => datos[g.clave].length === 0);
  return (
    <aside aria-label="Sugerencias" style={{
      width: 360, minWidth: 360, background: '#faf9f8', borderLeft: `1px solid ${COLORS.border}`, height: '100%',
      display: 'flex', flexDirection: 'column', fontFamily: "'Segoe UI', system-ui, sans-serif",
    }}>
      <div style={{ display: 'flex', alignItems: 'center', padding: '20px 20px 8px' }}>
        <h2 style={{ flex: 1, margin: 0, fontSize: 20, fontWeight: 600, color: COLORS.text }}>Sugerencias</h2>
        <button type="button" aria-label="Cerrar sugerencias" onClick={onCerrar}
          style={{ background: 'none', border: 'none', fontSize: 22, cursor: 'pointer', color: COLORS.secondary }}>&times;</button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 16px 16px' }}>
        {error && <div role="alert" style={{ fontSize: 13, color: '#d13438', padding: 8 }}>{error}</div>}
        {!datos && !error && <div style={{ fontSize: 13, color: COLORS.secondary, padding: 8 }}>Cargando…</div>}
        {vacio && (
          <div style={{ fontSize: 13, color: COLORS.secondary, padding: '24px 8px', textAlign: 'center' }}>
            No hay sugerencias por ahora: todo lo pendiente ya está en Mi día o no tiene fecha próxima.
          </div>
        )}
        {datos && GRUPOS.filter(g => datos[g.clave].length > 0).map(g => (
          <section key={g.clave} aria-label={g.titulo}>
            <h3 style={{ margin: '16px 4px 8px', fontSize: 14, fontWeight: 600, color: g.clave === 'vencidas' ? '#d13438' : COLORS.text }}>{g.titulo}</h3>
            {datos[g.clave].map(t => (
              <div key={t.id} style={{
                display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', marginBottom: 6, background: 'white',
                borderRadius: 4, boxShadow: '0 1px 2px rgba(0,0,0,0.08)',
              }}>
                <button type="button" aria-label={`Completar ${t.title}`} onClick={() => quitar(t.id, onCompletar)}
                  style={{ width: 18, height: 18, borderRadius: '50%', border: `1.5px solid ${COLORS.primary}`, background: 'none', padding: 0, cursor: 'pointer', flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, color: COLORS.text }}>{t.title}</div>
                  <div style={{ fontSize: 12, color: COLORS.secondary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {[t.list_name, fecha(t.due_date)].filter(Boolean).join(' • ')}
                  </div>
                </div>
                <button type="button" aria-label={`Agregar ${t.title} a Mi día`} title="Agregar a Mi día" onClick={() => quitar(t.id, onAgregarAMiDia)}
                  style={{ display: 'flex', background: 'none', border: 'none', cursor: 'pointer', color: COLORS.primary, padding: 4 }}>
                  <svg aria-hidden="true" width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6}><path d="M12 4v16M4 12h16" /></svg>
                </button>
              </div>
            ))}
          </section>
        ))}
      </div>
    </aside>
  );
}
