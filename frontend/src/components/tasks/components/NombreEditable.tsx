// Nombre que se edita en el mismo lugar (listas y grupos): Enter o salir guarda, Esc cancela.
import { useState } from 'react';
import { COLORS } from '../types';

export function NombreEditable({ valor, etiqueta, onGuardar, onCancelar }: {
  valor: string; etiqueta: string; onGuardar: (v: string) => void; onCancelar: () => void;
}) {
  const [texto, setTexto] = useState(valor);
  const guardar = () => { const t = texto.trim(); if (t && t !== valor) onGuardar(t); else onCancelar(); };
  return (
    <input autoFocus aria-label={etiqueta} value={texto} maxLength={120}
      onChange={e => setTexto(e.target.value)}
      onClick={e => e.stopPropagation()}
      onBlur={guardar}
      onKeyDown={e => { if (e.key === 'Enter') guardar(); if (e.key === 'Escape') onCancelar(); }}
      style={{ flex: 1, minWidth: 0, padding: '3px 6px', fontSize: 14, border: `1px solid ${COLORS.primary}`, borderRadius: 4, outline: 'none', fontFamily: 'inherit' }} />
  );
}
