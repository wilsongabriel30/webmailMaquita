// Repetición de una tarea en el panel de detalle (como en To Do): diaria, laborables, semanal, mensual, anual o
// personalizada (cada N días, semanas, meses o años; en semanas, qué días). Al completarla se crea la siguiente.
import { useState } from 'react';
import { COLORS } from '../types';
import {
  DIAS_SEMANA, REPETICIONES_SIMPLES, UNIDADES, escribirPersonalizada, etiquetaRepeticion, leerPersonalizada,
  type ReglaPersonalizada, type Unidad,
} from './repeticion';
import { desplegable, filaSeccion, opcion, quitar, seccion } from './estiloPanel';

function Personalizada({ inicial, onGuardar, onCancelar }: {
  inicial: ReglaPersonalizada; onGuardar: (regla: string) => void; onCancelar: () => void;
}) {
  const [r, setR] = useState(inicial);
  const unidad = UNIDADES.find(u => u.valor === r.unidad)!;
  const alternarDia = (d: number) => setR(x => ({ ...x, dias: x.dias.includes(d) ? x.dias.filter(y => y !== d) : [...x.dias, d] }));
  return (
    <div role="group" aria-label="Repetición personalizada" style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
        Cada
        <input type="number" min={1} max={999} value={r.cada} aria-label="Cada cuánto"
          onChange={e => setR(x => ({ ...x, cada: Number(e.target.value) }))}
          style={{ width: 56, fontSize: 13, padding: '3px 6px', border: `1px solid ${COLORS.border}`, borderRadius: 4 }} />
        <select value={r.unidad} aria-label="Unidad" onChange={e => setR(x => ({ ...x, unidad: e.target.value as Unidad }))}
          style={{ fontSize: 13, padding: '3px 6px', border: `1px solid ${COLORS.border}`, borderRadius: 4 }}>
          {UNIDADES.map(u => <option key={u.valor} value={u.valor}>{r.cada === 1 ? u.singular : u.plural}</option>)}
        </select>
      </div>
      {unidad.valor === 'semana' && (
        <div style={{ display: 'flex', gap: 4 }}>
          {DIAS_SEMANA.map((d, i) => {
            const activo = r.dias.includes(i);
            return (
              <button key={d} type="button" aria-pressed={activo} onClick={() => alternarDia(i)}
                style={{
                  width: 26, height: 26, borderRadius: '50%', fontSize: 11, cursor: 'pointer', padding: 0, fontFamily: 'inherit',
                  border: `1px solid ${activo ? COLORS.primary : COLORS.border}`,
                  background: activo ? COLORS.primary : 'white', color: activo ? 'white' : COLORS.text,
                }}>{d}</button>
            );
          })}
        </div>
      )}
      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
        <button type="button" onClick={onCancelar}
          style={{ fontSize: 12, padding: '4px 10px', background: 'white', border: `1px solid ${COLORS.border}`, borderRadius: 4, cursor: 'pointer' }}>
          Cancelar
        </button>
        <button type="button" onClick={() => onGuardar(escribirPersonalizada(r))}
          style={{ fontSize: 12, padding: '4px 10px', background: COLORS.primary, color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
          Guardar
        </button>
      </div>
    </div>
  );
}

export function RepeticionTarea({ valor, onCambiar }: { valor?: string | null; onCambiar: (regla: string | null) => void }) {
  const [abierto, setAbierto] = useState(false);
  const [personalizando, setPersonalizando] = useState(false);
  const poner = (regla: string | null) => { onCambiar(regla); setAbierto(false); setPersonalizando(false); };
  const actual = leerPersonalizada(valor) || { cada: 1, unidad: 'semana' as Unidad, dias: [] };

  return (
    <div style={seccion}>
      <div style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
        <button type="button" style={filaSeccion} aria-expanded={abierto} onClick={() => { setAbierto(!abierto); setPersonalizando(false); }}>
          <svg aria-hidden="true" width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={valor ? COLORS.primary : COLORS.secondary} strokeWidth={1.8}>
            <polyline points="17 1 21 5 17 9" /><path d="M3 11V9a4 4 0 014-4h14" />
            <polyline points="7 23 3 19 7 15" /><path d="M21 13v2a4 4 0 01-4 4H3" />
          </svg>
          <span style={{ flex: 1, color: valor ? COLORS.primary : COLORS.text }}>{valor ? etiquetaRepeticion(valor) : 'Repetir'}</span>
        </button>
        {valor && <button type="button" style={quitar} onClick={() => poner(null)}>Quitar</button>}
      </div>
      {abierto && (
        <div style={{ ...desplegable, width: 240 }}>
          {personalizando ? (
            <Personalizada inicial={actual} onGuardar={poner} onCancelar={() => setPersonalizando(false)} />
          ) : (
            <>
              {REPETICIONES_SIMPLES.map(o => (
                <button key={o.valor} type="button" onClick={() => poner(o.valor)}
                  style={{ ...opcion, fontWeight: valor === o.valor ? 600 : 400, color: valor === o.valor ? COLORS.primary : COLORS.text }}
                  onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
                  onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
                  {o.etiqueta}
                </button>
              ))}
              <div style={{ borderTop: `1px solid ${COLORS.border}`, margin: '4px 0' }} />
              <button type="button" onClick={() => setPersonalizando(true)}
                style={{ ...opcion, fontWeight: leerPersonalizada(valor) ? 600 : 400 }}
                onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
                onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
                Personalizada…
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
