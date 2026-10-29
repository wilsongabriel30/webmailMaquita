// Tareas completadas al final de la lista, plegadas (como en To Do). Se recuerda si se dejaron abiertas.
import { useState, type ReactNode } from 'react';
import { COLORS } from '../types';

const CLAVE = 'tareas-completadas-abiertas';

function leerAbierta(): boolean {
  try { return localStorage.getItem(CLAVE) === '1'; } catch { return false; }
}

export function SeccionCompletadas({ cantidad, children }: { cantidad: number; children: ReactNode }) {
  const [abierta, setAbierta] = useState(leerAbierta);
  if (cantidad === 0) return null;
  const alternar = () => {
    const nueva = !abierta;
    setAbierta(nueva);
    try { localStorage.setItem(CLAVE, nueva ? '1' : '0'); } catch { /* sin almacenamiento: solo esta vez */ }
  };
  return (
    <div style={{ marginTop: 8 }}>
      <button type="button" onClick={alternar} aria-expanded={abierta}
        style={{
          display: 'flex', alignItems: 'center', gap: 8, margin: '4px 24px', padding: '6px 8px',
          background: 'none', border: 'none', borderRadius: 4, cursor: 'pointer',
          fontSize: 14, fontWeight: 600, color: COLORS.text, fontFamily: 'inherit',
        }}
        onMouseEnter={e => (e.currentTarget.style.background = COLORS.border)}
        onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
        <svg aria-hidden="true" width={12} height={12} viewBox="0 0 24 24" fill="none" stroke={COLORS.secondary} strokeWidth={2.5}
          style={{ transform: abierta ? 'none' : 'rotate(-90deg)', transition: 'transform 0.15s' }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
        Completadas
        <span style={{ fontWeight: 400, color: COLORS.secondary }}>{cantidad}</span>
      </button>
      {abierta && children}
    </div>
  );
}
