// Menú contextual de la barra de Tareas (clic derecho o botón «⋯»). Se cierra con Esc o al hacer clic fuera.
import { useEffect, useState, type ReactNode } from 'react';
import { COLORS } from '../types';

export function MenuContextual({ x, y, etiqueta, onCerrar, children }: {
  x: number; y: number; etiqueta: string; onCerrar: () => void; children: ReactNode;
}) {
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => { if (e.key === 'Escape') onCerrar(); };
    window.addEventListener('keydown', tecla);
    return () => window.removeEventListener('keydown', tecla);
  }, [onCerrar]);
  const izquierda = Math.min(x, window.innerWidth - 240);
  const arriba = Math.min(y, window.innerHeight - 320);
  return (
    <>
      <div style={{ position: 'fixed', inset: 0, zIndex: 999 }} onClick={onCerrar} onContextMenu={e => { e.preventDefault(); onCerrar(); }} />
      <div role="menu" aria-label={etiqueta} style={{
        position: 'fixed', left: Math.max(8, izquierda), top: Math.max(8, arriba), zIndex: 1000, minWidth: 220,
        background: 'white', border: `1px solid ${COLORS.border}`, borderRadius: 6,
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)', padding: '4px 0', fontSize: 13,
      }}>
        {children}
      </div>
    </>
  );
}

export function OpcionMenu({ children, onClick, peligro, deshabilitada, titulo }: {
  children: ReactNode; onClick: () => void; peligro?: boolean; deshabilitada?: boolean; titulo?: string;
}) {
  return (
    <button type="button" role="menuitem" disabled={deshabilitada} title={titulo} onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 12, width: '100%', padding: '9px 16px', textAlign: 'left',
        background: 'none', border: 'none', fontSize: 14, fontFamily: 'inherit',
        cursor: deshabilitada ? 'default' : 'pointer',
        color: deshabilitada ? COLORS.muted : peligro ? '#d13438' : COLORS.text,
      }}
      onMouseEnter={e => { if (!deshabilitada) e.currentTarget.style.background = COLORS.hoverBg; }}
      onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
      {children}
    </button>
  );
}

export function TituloMenu({ children }: { children: ReactNode }) {
  return <div style={{ padding: '6px 16px 2px', fontSize: 11, color: COLORS.secondary, textTransform: 'uppercase', letterSpacing: 0.4 }}>{children}</div>;
}

export function SeparadorMenu() {
  return <div style={{ height: 1, background: COLORS.border, margin: '4px 0' }} />;
}

/** Opción con submenú a la derecha (p. ej. «Mover la lista a…»): se abre al pasar el ratón o con clic. */
export function SubmenuOpcion({ etiqueta, icono, children }: { etiqueta: string; icono?: ReactNode; children: ReactNode }) {
  const [abierto, setAbierto] = useState(false);
  const alLado = typeof window !== 'undefined' && window.innerWidth < 520;
  return (
    <div style={{ position: 'relative' }} onMouseEnter={() => setAbierto(true)} onMouseLeave={() => setAbierto(false)}>
      <OpcionMenu onClick={() => setAbierto(a => !a)}>
        {icono}
        <span style={{ flex: 1 }}>{etiqueta}</span>
        <svg aria-hidden="true" width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><polyline points="9 6 15 12 9 18" /></svg>
      </OpcionMenu>
      {abierto && (
        <div role="menu" aria-label={etiqueta} style={{
          position: 'absolute', top: alLado ? '100%' : -4, left: alLado ? 16 : '100%', minWidth: 200, zIndex: 1001,
          background: 'white', border: `1px solid ${COLORS.border}`, borderRadius: 6,
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)', padding: '4px 0',
        }}>
          {children}
        </div>
      )}
    </div>
  );
}
