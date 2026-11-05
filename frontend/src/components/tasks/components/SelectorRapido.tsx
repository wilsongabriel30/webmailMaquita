// Botón con ícono y menú corto de la barra para agregar tareas (fecha, recordatorio, repetir), como en Outlook.
// Cada opción da un valor; opcionalmente, un campo para elegir fecha (o fecha y hora) a mano.
// Con un valor elegido, el botón se vuelve una pastilla con borde, ícono y texto («Hoy», «8:30, Hoy»), y el menú
// ofrece quitarlo, como en To Do.
import { useState, type ReactNode } from 'react';
import { COLORS } from '../types';

export interface OpcionRapida { etiqueta: string; valor: () => string }

interface Props {
  titulo: string;
  icono: ReactNode;
  activo: boolean;
  opciones: OpcionRapida[];
  /** Campo para elegir a mano: 'date' o 'datetime-local'. */
  campo?: 'date' | 'datetime-local';
  onElegir: (valor: string) => void;
  /** Texto de lo elegido: con él, el botón se muestra como pastilla. */
  texto?: string;
  /** Opción para quitar lo elegido (p. ej. «Quitar fecha de vencimiento»). */
  quitar?: { etiqueta: string; onQuitar: () => void };
}

const opcion = {
  display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px', fontSize: 13, cursor: 'pointer',
  borderRadius: 4, background: 'none', border: 'none', fontFamily: 'inherit', color: COLORS.text,
} as const;

export function SelectorRapido({ titulo, icono, activo, opciones, campo, onElegir, texto, quitar }: Props) {
  const [abierto, setAbierto] = useState(false);
  const [manual, setManual] = useState('');
  const elegir = (v: string) => { onElegir(v); setAbierto(false); setManual(''); };
  return (
    <div style={{ position: 'relative' }}>
      <button type="button" title={texto ? `${titulo}: ${texto}` : titulo} aria-label={texto ? `${titulo}: ${texto}` : titulo}
        aria-expanded={abierto} onClick={() => setAbierto(!abierto)}
        style={texto ? {
          display: 'flex', alignItems: 'center', gap: 8, height: 32, padding: '0 10px', borderRadius: 4, cursor: 'pointer',
          border: `1px solid ${COLORS.border}`, background: abierto ? COLORS.hoverBg : 'white', color: COLORS.secondary,
          fontFamily: 'inherit', fontSize: 14, whiteSpace: 'nowrap',
        } : {
          display: 'flex', padding: 6, borderRadius: 4, cursor: 'pointer', border: 'none',
          background: abierto ? COLORS.hoverBg : 'none', color: activo ? COLORS.primary : COLORS.secondary,
        }}>
        {icono}
        {texto && <span style={{ color: COLORS.text }}>{texto}</span>}
      </button>
      {abierto && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 99 }} onClick={() => setAbierto(false)} />
          <div role="menu" aria-label={titulo} style={{
            position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 100, minWidth: 210,
            background: 'white', border: `1px solid ${COLORS.border}`, borderRadius: 6, boxShadow: '0 4px 12px rgba(0,0,0,0.15)', padding: 4,
          }}>
            <div style={{ padding: '6px 12px', fontSize: 12, fontWeight: 600, color: COLORS.secondary }}>{titulo}</div>
            {opciones.map(o => (
              <button key={o.etiqueta} type="button" role="menuitem" style={opcion} onClick={() => elegir(o.valor())}
                onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
                onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
                {o.etiqueta}
              </button>
            ))}
            {quitar && activo && (
              <button type="button" role="menuitem" style={{ ...opcion, color: '#a4262c', borderTop: `1px solid ${COLORS.border}`, borderRadius: 0, marginTop: 4 }}
                onClick={() => { quitar.onQuitar(); setAbierto(false); }}
                onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
                onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
                {quitar.etiqueta}
              </button>
            )}
            {campo && (
              <div style={{ borderTop: `1px solid ${COLORS.border}`, marginTop: 4, padding: '8px 8px 4px' }}>
                <input type={campo} aria-label={`${titulo}: elegir a mano`} value={manual} onChange={e => setManual(e.target.value)}
                  style={{ width: '100%', boxSizing: 'border-box', fontSize: 12, border: `1px solid ${COLORS.border}`, borderRadius: 4, padding: '4px 6px' }} />
                <button type="button" disabled={!manual}
                  onClick={() => elegir(campo === 'date' ? manual : new Date(manual).toISOString())}
                  style={{
                    marginTop: 4, width: '100%', padding: 5, fontSize: 12, border: 'none', borderRadius: 4,
                    background: manual ? COLORS.primary : '#f3f2f1', color: manual ? 'white' : COLORS.muted, cursor: manual ? 'pointer' : 'default',
                  }}>
                  Guardar
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
