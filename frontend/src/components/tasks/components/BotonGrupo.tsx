// Botón «Grupo» de la cabecera (como en Outlook, F6): elegir cómo se agrupan las tareas pendientes.
import { useState } from 'react';
import { COLORS } from '../types';
import { AGRUPACIONES, type Agrupacion } from './agruparTareas';

export function BotonGrupo({ valor, onCambiar }: { valor: Agrupacion; onCambiar: (a: Agrupacion) => void }) {
  const [abierto, setAbierto] = useState(false);
  const actual = AGRUPACIONES.find(a => a.valor === valor);
  return (
    <div style={{ position: 'relative' }}>
      <button type="button" aria-expanded={abierto} onClick={() => setAbierto(!abierto)} title="Agrupar las tareas"
        style={{
          display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', fontSize: 13, color: COLORS.secondary,
          background: abierto ? COLORS.hoverBg : 'transparent', border: 'none', cursor: 'pointer', borderRadius: 4, fontFamily: 'inherit',
        }}>
        <svg aria-hidden="true" width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <rect x="4" y="3" width="16" height="18" rx="2" /><path d="M9 3v18" />
        </svg>
        <span>Grupo</span>
        {valor !== 'ninguno' && <span style={{ fontSize: 11, color: COLORS.primary, fontWeight: 500 }}>({actual?.etiqueta})</span>}
      </button>
      {abierto && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 99 }} onClick={() => setAbierto(false)} />
          <div role="menu" aria-label="Agrupar por" style={{
            position: 'absolute', right: 0, top: '100%', marginTop: 4, zIndex: 100, minWidth: 200,
            background: 'white', border: `1px solid ${COLORS.border}`, borderRadius: 6, boxShadow: '0 4px 12px rgba(0,0,0,0.15)', padding: 4,
          }}>
            <div style={{ padding: '6px 12px', fontSize: 12, fontWeight: 600, color: COLORS.secondary }}>Agrupar por</div>
            {AGRUPACIONES.map(a => (
              <button key={a.valor} type="button" role="menuitemradio" aria-checked={valor === a.valor}
                onClick={() => { onCambiar(a.valor); setAbierto(false); }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '8px 12px', fontSize: 13, border: 'none',
                  background: 'none', cursor: 'pointer', borderRadius: 4, fontFamily: 'inherit', textAlign: 'left',
                  color: valor === a.valor ? COLORS.primary : COLORS.text, fontWeight: valor === a.valor ? 600 : 400,
                }}
                onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
                onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
                <span style={{ width: 14 }}>{valor === a.valor ? '✓' : ''}</span>{a.etiqueta}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
