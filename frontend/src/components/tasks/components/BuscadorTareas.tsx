// Buscar en todas las tareas (título, nota y pasos), como en To Do. Busca al dejar de escribir; Esc la borra.
import { useEffect, useState } from 'react';
import { COLORS } from '../types';

export function BuscadorTareas({ valor, onBuscar }: { valor: string; onBuscar: (texto: string) => void }) {
  const [texto, setTexto] = useState(valor);
  const [anterior, setAnterior] = useState(valor);
  if (anterior !== valor) { setAnterior(valor); setTexto(valor); } // se borró desde fuera (al cambiar de lista)

  useEffect(() => {
    if (texto === valor) return;
    const t = setTimeout(() => onBuscar(texto), 300);
    return () => clearTimeout(t);
  }, [texto, valor, onBuscar]);

  return (
    <div role="search" style={{
      flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 6, padding: '4px 8px',
      border: `1px solid ${COLORS.border}`, borderRadius: 4, background: COLORS.hoverBg,
    }}>
      <svg aria-hidden="true" width={14} height={14} viewBox="0 0 24 24" fill="none" stroke={COLORS.secondary} strokeWidth={2}>
        <circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" />
      </svg>
      <input type="search" value={texto} aria-label="Buscar tareas" placeholder="Buscar tareas"
        onChange={e => setTexto(e.target.value)}
        onKeyDown={e => { if (e.key === 'Escape') { setTexto(''); onBuscar(''); } if (e.key === 'Enter') onBuscar(texto); }}
        style={{ flex: 1, minWidth: 0, border: 'none', outline: 'none', background: 'transparent', fontSize: 13, fontFamily: 'inherit', color: COLORS.text }} />
      {texto && (
        <button type="button" aria-label="Borrar búsqueda" title="Borrar búsqueda" onClick={() => { setTexto(''); onBuscar(''); }}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: COLORS.secondary, fontSize: 16, lineHeight: 1, padding: 0 }}>
          &times;
        </button>
      )}
    </div>
  );
}
