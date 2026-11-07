// Recordatorio de una tarea en el panel de detalle: hoy, mañana, el lunes o una fecha y hora a elección.
import { useState } from 'react';
import { COLORS } from '../types';
import { desplegable, filaSeccion, opcion, quitar, seccion } from './estiloPanel';

const PRESETS = [
  { label: 'Más tarde hoy', offset: 0 },
  { label: 'Mañana 9:00', offset: 1 },
  { label: 'Próximo lunes 9:00', offset: -1 },
];

function formatReminder(r?: string | null) {
  if (!r) return '';
  const d = new Date(r);
  if (isNaN(d.getTime())) return '';
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const rDate = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diff = Math.round((rDate.getTime() - today.getTime()) / 86400000);
  const time = d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
  if (diff === 0) return `Hoy a las ${time}`;
  if (diff === 1) return `Mañana a las ${time}`;
  if (diff === -1) return `Ayer a las ${time}`;
  return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' }) + ` a las ${time}`;
}

function desdePreset(offset: number): Date {
  const now = new Date();
  if (offset === 0) return new Date(now.getTime() + 3 * 3600000);
  if (offset === 1) return new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 9, 0);
  const day = now.getDay();
  const daysUntilMon = day === 0 ? 1 : (8 - day);
  return new Date(now.getFullYear(), now.getMonth(), now.getDate() + daysUntilMon, 9, 0);
}

export function RecordatorioTarea({ valor, onCambiar }: { valor?: string | null; onCambiar: (r: string | null) => void }) {
  const [abierto, setAbierto] = useState(false);
  const [elegido, setElegido] = useState('');
  const poner = (r: string | null) => { onCambiar(r); setAbierto(false); setElegido(''); };

  return (
    <div style={seccion}>
      <div style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
        <button type="button" style={filaSeccion} aria-expanded={abierto} onClick={() => setAbierto(!abierto)}>
          <svg aria-hidden="true" width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={valor ? COLORS.primary : COLORS.secondary} strokeWidth={1.8}>
            <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 01-3.46 0" />
          </svg>
          <span style={{ flex: 1, color: valor ? COLORS.primary : COLORS.text }}>{valor ? formatReminder(valor) : 'Recordarme'}</span>
        </button>
        {valor && <button type="button" style={quitar} onClick={() => poner(null)}>Quitar</button>}
      </div>
      {abierto && (
        <div style={{ ...desplegable, width: 220 }}>
          {PRESETS.map(p => (
            <button key={p.label} type="button" style={opcion} onClick={() => poner(desdePreset(p.offset).toISOString())}
              onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
              onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
              {p.label}
            </button>
          ))}
          <div style={{ borderTop: `1px solid ${COLORS.border}`, margin: '4px 0' }} />
          <div style={{ padding: '4px 8px' }}>
            <input type="datetime-local" aria-label="Fecha y hora del recordatorio" value={elegido} onChange={e => setElegido(e.target.value)}
              style={{ width: '100%', fontSize: 12, border: `1px solid ${COLORS.border}`, borderRadius: 4, padding: '4px 6px' }} />
            {elegido && (
              <button type="button" onClick={() => poner(new Date(elegido).toISOString())}
                style={{ marginTop: 4, width: '100%', padding: 4, fontSize: 12, background: COLORS.primary, color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
                Establecer
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
