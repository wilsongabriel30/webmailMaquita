// «Cuadrícula | Lista» junto al título de la lista de tareas (como en Outlook).
import { COLORS } from '../types';
import type { ModoVista } from './modoVista';

const OPCIONES: { valor: ModoVista; etiqueta: string; icono: string }[] = [
  { valor: 'cuadricula', etiqueta: 'Cuadrícula', icono: 'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z' },
  { valor: 'lista', etiqueta: 'Lista', icono: 'M4 6h16M4 12h10M4 18h16' },
];

export function SelectorVista({ modo, onCambiar }: { modo: ModoVista; onCambiar: (m: ModoVista) => void }) {
  return (
    <div role="tablist" aria-label="Vista de las tareas" style={{ display: 'flex', alignItems: 'center', gap: 4, marginLeft: 12 }}>
      {OPCIONES.map(o => {
        const activo = modo === o.valor;
        return (
          <button key={o.valor} role="tab" aria-selected={activo} onClick={() => onCambiar(o.valor)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px 4px', fontSize: 14,
              background: 'transparent', border: 'none', cursor: 'pointer', color: COLORS.text,
              borderBottom: `2px solid ${activo ? COLORS.text : 'transparent'}`, fontWeight: activo ? 600 : 400,
            }}>
            <svg width={16} height={16} viewBox="0 0 24 24" fill={activo && o.valor === 'cuadricula' ? COLORS.text : 'none'}
              stroke="currentColor" strokeWidth={1.8} strokeLinejoin="round" strokeLinecap="round">
              <path d={o.icono} />
            </svg>
            {o.etiqueta}
          </button>
        );
      })}
    </div>
  );
}
