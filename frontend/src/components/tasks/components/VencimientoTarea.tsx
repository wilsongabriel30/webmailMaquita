// Fecha de vencimiento en el panel de una tarea (como en Outlook): «Hoy», «Mañana», «La próxima semana» o una
// fecha a elección. La fila muestra «Hoy», «Mañana» o la fecha; sin fecha, «Agregar fecha de vencimiento».
import { useState } from 'react';
import { COLORS } from '../types';
import { desplegable, filaSeccion, opcion, quitar, seccion } from './estiloPanel';

function aTexto(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${String(d.getDate()).padStart(2, '0')}`;
}

function enDias(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return aTexto(d);
}

/** Próximo lunes (como «La próxima semana» de To Do). */
function proximaSemana(): string {
  const dia = new Date().getDay();
  return enDias(dia === 0 ? 1 : 8 - dia);
}

function etiquetaVencimiento(fecha: string): string {
  if (!fecha) return '';
  if (fecha === enDias(0)) return 'Hoy';
  if (fecha === enDias(1)) return 'Mañana';
  if (fecha === enDias(-1)) return 'Ayer';
  const [a, m, d] = fecha.split('-').map(Number);
  const texto = new Date(a, m - 1, d).toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short' });
  return `Vence el ${texto}`;
}

export function VencimientoTarea({ valor, onCambiar }: { valor: string; onCambiar: (fecha: string | null) => void }) {
  const [abierto, setAbierto] = useState(false);
  const [elegida, setElegida] = useState('');
  const poner = (f: string | null) => { onCambiar(f); setAbierto(false); setElegida(''); };
  const vencida = !!valor && valor < enDias(0);
  const color = vencida ? '#d13438' : valor ? COLORS.primary : COLORS.text;
  const presets = [
    { label: 'Hoy', fecha: enDias(0) },
    { label: 'Mañana', fecha: enDias(1) },
    { label: 'La próxima semana', fecha: proximaSemana() },
  ];

  return (
    <div style={seccion}>
      <div style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
        <button type="button" style={filaSeccion} aria-expanded={abierto} onClick={() => setAbierto(!abierto)}>
          <svg aria-hidden="true" width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={valor ? color : COLORS.secondary} strokeWidth={1.6}>
            <rect x="3" y="4" width="18" height="17" rx="2" /><path d="M3 9h18M8 13h.01M12 13h.01M16 13h.01M8 17h.01M12 17h.01" />
          </svg>
          <span style={{ flex: 1, color }}>{valor ? etiquetaVencimiento(valor) : 'Agregar fecha de vencimiento'}</span>
        </button>
        {valor && <button type="button" style={quitar} aria-label="Quitar fecha de vencimiento" onClick={() => poner(null)}>Quitar</button>}
      </div>
      {abierto && (
        <div style={{ ...desplegable, width: 220 }}>
          {presets.map(p => (
            <button key={p.label} type="button" style={opcion} onClick={() => poner(p.fecha)}
              onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
              onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
              {p.label}
            </button>
          ))}
          <div style={{ borderTop: `1px solid ${COLORS.border}`, margin: '4px 0' }} />
          <div style={{ padding: '4px 8px' }}>
            <input type="date" aria-label="Elegir una fecha" value={elegida || valor} onChange={e => setElegida(e.target.value)}
              style={{ width: '100%', fontSize: 12, border: `1px solid ${COLORS.border}`, borderRadius: 4, padding: '4px 6px' }} />
            {elegida && (
              <button type="button" onClick={() => poner(elegida)}
                style={{ marginTop: 4, width: '100%', padding: 4, fontSize: 12, background: COLORS.primary, color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
                Guardar
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
