// Pie de la barra de Tareas, como en Outlook (F5): «+ Nueva lista» en texto azul y, a la derecha, un ícono pequeño
// para «Nuevo grupo» (con su descripción al pasar el ratón). Cada uno abre su campo para escribir el nombre.
import { useState } from 'react';
import { COLORS } from '../types';
import { SidebarIcon } from './IconoBarra';

type Que = 'lista' | 'grupo';

const TEXTOS: Record<Que, { boton: string; ayuda: string; campo: string; icono: string }> = {
  lista: { boton: 'Nueva lista', ayuda: 'Crear una lista de tareas', campo: 'Nombre de la lista nueva', icono: 'list-plus' },
  grupo: { boton: 'Nuevo grupo', ayuda: 'Crear un grupo para juntar varias listas', campo: 'Nombre del grupo nuevo', icono: 'folder-plus' },
};

export function BotonesCrear({ onCrearLista, onCrearGrupo }: { onCrearLista: (n: string) => void; onCrearGrupo: (n: string) => void }) {
  const [abierto, setAbierto] = useState<Que | null>(null);
  const [nombre, setNombre] = useState('');
  const cerrar = () => { setAbierto(null); setNombre(''); };
  const crear = () => {
    const n = nombre.trim();
    if (!n || !abierto) return;
    if (abierto === 'lista') onCrearLista(n); else onCrearGrupo(n);
    cerrar();
  };

  return (
    <div style={{ padding: '6px 12px 8px', borderTop: `1px solid ${COLORS.border}`, margin: '0 8px' }}>
      {abierto ? (
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span aria-hidden="true" style={{ display: 'flex', color: COLORS.primary }}><SidebarIcon icon={TEXTOS[abierto].icono} size={18} /></span>
          <input autoFocus aria-label={TEXTOS[abierto].campo} placeholder={TEXTOS[abierto].campo} value={nombre} maxLength={120}
            onChange={e => setNombre(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') crear(); if (e.key === 'Escape') cerrar(); }}
            style={{ flex: 1, minWidth: 0, padding: '6px 8px', fontSize: 13, border: `1px solid ${COLORS.primary}`, borderRadius: 4, outline: 'none', fontFamily: 'inherit' }} />
          <button type="button" onClick={crear} style={{ padding: '6px 10px', fontSize: 13, background: COLORS.primary, color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
            Crear
          </button>
          <button type="button" aria-label="Cancelar" onClick={cerrar} style={{ background: 'none', border: 'none', cursor: 'pointer', color: COLORS.secondary, fontSize: 18, lineHeight: 1 }}>×</button>
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <button type="button" title={TEXTOS.lista.ayuda} onClick={() => setAbierto('lista')}
            style={{
              flex: 1, display: 'flex', alignItems: 'center', gap: 12, padding: '6px 4px', fontSize: 14, cursor: 'pointer',
              fontFamily: 'inherit', color: COLORS.primary, background: 'none', border: 'none', borderRadius: 4, textAlign: 'left',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
            onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
            <svg aria-hidden="true" width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6}>
              <path d="M12 4v16M4 12h16" />
            </svg>
            {TEXTOS.lista.boton}
          </button>
          <button type="button" title={TEXTOS.grupo.ayuda} aria-label={TEXTOS.grupo.boton} onClick={() => setAbierto('grupo')}
            style={{ display: 'flex', padding: 6, cursor: 'pointer', color: COLORS.primary, background: 'none', border: 'none', borderRadius: 4 }}
            onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
            onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
            <SidebarIcon icon={TEXTOS.grupo.icono} size={18} />
          </button>
        </div>
      )}
    </div>
  );
}
