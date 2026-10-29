// Pie de la barra de Tareas: «Nueva lista» y «Nuevo grupo», dos botones claramente distintos
// (texto, ícono y descripción propios). Cada uno abre su campo para escribir el nombre.
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
    <div style={{ padding: '10px 12px', borderTop: `1px solid ${COLORS.border}` }}>
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
        <div style={{ display: 'flex', gap: 8 }}>
          {(['lista', 'grupo'] as Que[]).map(q => (
            <button key={q} type="button" title={TEXTOS[q].ayuda} onClick={() => setAbierto(q)}
              style={{
                flex: q === 'lista' ? 1.4 : 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                padding: '7px 8px', fontSize: 13, fontWeight: 500, cursor: 'pointer', borderRadius: 4, fontFamily: 'inherit',
                color: q === 'lista' ? 'white' : COLORS.primary,
                background: q === 'lista' ? COLORS.primary : 'white',
                border: `1px solid ${COLORS.primary}`,
              }}>
              <SidebarIcon icon={TEXTOS[q].icono} size={16} /> {TEXTOS[q].boton}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
