// «Elige una categoría» en el panel de una tarea (como en Outlook): una o varias categorías de color.
import { useState } from 'react';
import { COLORS } from '../types';
import { CATEGORIAS, colorCategoria } from './categorias';
import { desplegable, filaSeccion, opcion, seccion } from './estiloPanel';

export function CategoriaTarea({ valor, onCambiar }: { valor: string[]; onCambiar: (labels: string[]) => void }) {
  const [abierto, setAbierto] = useState(false);
  const alternar = (nombre: string) =>
    onCambiar(valor.includes(nombre) ? valor.filter(v => v !== nombre) : [...valor, nombre]);

  return (
    <div style={seccion}>
      <button type="button" style={filaSeccion} aria-expanded={abierto} onClick={() => setAbierto(!abierto)}>
        <svg aria-hidden="true" width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={COLORS.secondary} strokeWidth={1.6}>
          <path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z" /><circle cx="7" cy="7" r="1.2" />
        </svg>
        {valor.length === 0 ? <span>Elige una categoría</span> : (
          <span style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {valor.map(v => {
              const c = colorCategoria(v);
              return (
                <span key={v} style={{ fontSize: 12, padding: '2px 8px', borderRadius: 10, background: c.fondo, color: COLORS.text, border: `1px solid ${c.color}` }}>
                  {v}
                </span>
              );
            })}
          </span>
        )}
      </button>
      {abierto && (
        <div role="menu" aria-label="Categorías" style={{ ...desplegable, width: 220 }}>
          {CATEGORIAS.map(c => (
            <button key={c.nombre} type="button" role="menuitemcheckbox" aria-checked={valor.includes(c.nombre)}
              style={{ ...opcion, display: 'flex', alignItems: 'center', gap: 10 }} onClick={() => alternar(c.nombre)}
              onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
              onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
              <span aria-hidden="true" style={{ width: 14, height: 14, borderRadius: 3, background: c.color }} />
              <span style={{ flex: 1 }}>{c.nombre}</span>
              {valor.includes(c.nombre) && <span aria-hidden="true" style={{ color: COLORS.primary }}>✓</span>}
            </button>
          ))}
          {valor.length > 0 && (
            <button type="button" style={{ ...opcion, color: '#d13438' }} onClick={() => { onCambiar([]); setAbierto(false); }}>
              Quitar todas
            </button>
          )}
        </div>
      )}
    </div>
  );
}
