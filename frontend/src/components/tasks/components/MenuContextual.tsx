// Menú contextual de la barra de Tareas (clic derecho o botón «⋯»). Se cierra con Esc o al hacer clic fuera.
import { useEffect, type ReactNode } from 'react';
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
        display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '8px 16px', textAlign: 'left',
        background: 'none', border: 'none', fontSize: 13, fontFamily: 'inherit',
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
