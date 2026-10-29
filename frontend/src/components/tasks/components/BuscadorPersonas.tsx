// Buscador de personas del recuadro «Asignar tarea a:». Busca en el directorio (personas de nómina) y, además, acepta
// escribir directamente un correo de la organización (cuentas de área, que no están en
// nómina): aparece la opción «Asignar a <correo>» y Enter lo agrega. El servidor solo acepta correos de la casa.
import { useEffect, useRef, useState } from 'react';
import { tareasApi } from '../../tareas/api';
import type { Persona } from '../../tareas/tipos';
import { COLORS } from '../types';
import { CirculoPersona } from './CirculoPersona';

export const CORREO_VALIDO = /^[a-z0-9._%+'-]+@([a-z0-9-]+\.)+[a-z]{2,}$/;

interface Props {
  valor: string[];
  onChange: (v: string[]) => void;
  /** Lo que está escrito y todavía no se agregó (para no perderlo al pulsar «Enviar»). */
  onTexto?: (t: string) => void;
}

export function BuscadorPersonas({ valor, onChange, onTexto }: Props) {
  const [q, setQ] = useState('');
  const [op, setOp] = useState<Persona[]>([]);
  const [nombres, setNombres] = useState<Record<string, string>>({});
  const reloj = useRef<number | undefined>(undefined);
  const texto = q.trim().toLowerCase();
  const correoEscrito = CORREO_VALIDO.test(texto) && !valor.includes(texto) && !op.some(p => p.email === texto);

  useEffect(() => {
    window.clearTimeout(reloj.current);
    if (q.trim().length < 2) return;
    reloj.current = window.setTimeout(async () => {
      try { setOp((await tareasApi.personas(q.trim())).filter(p => !valor.includes(p.email))); } catch { setOp([]); }
    }, 250);
    return () => window.clearTimeout(reloj.current);
  }, [q, valor]);

  const escribir = (t: string) => { setQ(t); onTexto?.(t); if (t.trim().length < 2) setOp([]); };
  const agregar = (email: string, nombre?: string) => {
    if (nombre) setNombres(n => ({ ...n, [email]: nombre }));
    onChange([...valor, email]);
    escribir('');
  };

  return (
    <div style={{ position: 'relative' }}>
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center', padding: '6px 8px', minHeight: 36, boxSizing: 'border-box',
        border: `1px solid ${COLORS.border}`, borderRadius: 4, background: 'white',
      }}>
        {valor.map(e => (
          <span key={e} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '2px 8px 2px 2px', borderRadius: 14, background: COLORS.activeBg, fontSize: 13, color: COLORS.text }}>
            <CirculoPersona email={e} nombre={nombres[e]} tamano={22} />
            {nombres[e] || e}
            <button type="button" aria-label={`Quitar a ${nombres[e] || e}`} onClick={() => onChange(valor.filter(x => x !== e))}
              style={{ border: 'none', background: 'none', cursor: 'pointer', color: COLORS.secondary, padding: 0, fontSize: 14 }}>&times;</button>
          </span>
        ))}
        <input autoFocus value={q} aria-label="Buscar persona o escribir un correo" placeholder="Nombre, departamento o correo…"
          onChange={e => escribir(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              e.preventDefault();
              if (op.length === 1) agregar(op[0].email, op[0].nombre);
              else if (correoEscrito) agregar(texto);
            }
            if (e.key === 'Backspace' && !q && valor.length) onChange(valor.slice(0, -1));
          }}
          style={{ flex: 1, minWidth: 160, border: 'none', outline: 'none', fontSize: 13, fontFamily: 'inherit', padding: '4px 0' }} />
      </div>
      {(op.length > 0 || correoEscrito) && texto.length >= 2 && (
        <div role="listbox" aria-label="Personas" style={{
          position: 'absolute', left: 0, right: 0, top: '100%', marginTop: 2, zIndex: 10, maxHeight: 240, overflowY: 'auto',
          background: 'white', border: `1px solid ${COLORS.border}`, borderRadius: 4, boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        }}>
          {op.map(p => (
            <button key={p.email} type="button" role="option" aria-selected={false} onClick={() => agregar(p.email, p.nombre)}
              style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '8px 10px', border: 'none', background: 'none', cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit' }}
              onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
              onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
              <CirculoPersona email={p.email} nombre={p.nombre} tamano={28} />
              <span style={{ minWidth: 0 }}>
                <span style={{ display: 'block', fontSize: 13, color: COLORS.text }}>{p.nombre}</span>
                <span style={{ display: 'block', fontSize: 12, color: COLORS.secondary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {[p.email, p.departamento].filter(Boolean).join(' · ')}
                </span>
              </span>
            </button>
          ))}
          {correoEscrito && (
            <button type="button" role="option" aria-selected={false} onClick={() => agregar(texto)}
              style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '8px 10px', border: 'none', borderTop: op.length ? `1px solid ${COLORS.border}` : 'none', background: 'none', cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit', fontSize: 13, color: COLORS.primary }}
              onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
              onMouseLeave={e => (e.currentTarget.style.background = 'none')}>
              <CirculoPersona email={texto} tamano={28} />
              Asignar a {texto}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
