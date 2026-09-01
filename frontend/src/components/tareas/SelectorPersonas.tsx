// Selector de personas (correos del directorio) con búsqueda; fichas removibles.
import { useEffect, useRef, useState } from 'react';
import { tareasApi } from './api';
import type { Persona } from './tipos';
import { nombreDe } from './tipos';

interface Props { valor: string[]; onChange: (v: string[]) => void; multiple?: boolean; placeholder?: string; autoFocus?: boolean }

export function SelectorPersonas({ valor, onChange, multiple = true, placeholder = 'Escribe un nombre o correo…', autoFocus }: Props) {
  const [q, setQ] = useState('');
  const [op, setOp] = useState<Persona[]>([]);
  const [abierto, setAbierto] = useState(false);
  const t = useRef<number | undefined>(undefined);

  useEffect(() => {
    window.clearTimeout(t.current);
    if (q.trim().length < 2) { setOp([]); return; }
    t.current = window.setTimeout(async () => {
      try { setOp((await tareasApi.personas(q)).filter(p => !valor.includes(p.email))); setAbierto(true); } catch { setOp([]); }
    }, 250);
    return () => window.clearTimeout(t.current);
  }, [q, valor]);

  const agregar = (email: string) => {
    onChange(multiple ? [...valor, email] : [email]);
    setQ(''); setOp([]); setAbierto(false);
  };

  return (
    <div style={{ position: 'relative' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center', border: '1px solid #c8c6c4', borderRadius: 4, padding: '4px 6px', background: '#fff' }}>
        {valor.map(v => (
          <span key={v} title={v} style={{ background: '#eff6fc', color: '#004578', borderRadius: 12, padding: '2px 8px', fontSize: 13, display: 'flex', gap: 4, alignItems: 'center' }}>
            {nombreDe(v)}
            <button type="button" onClick={() => onChange(valor.filter(x => x !== v))} style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#605e5c', padding: 0 }} aria-label="Quitar">×</button>
          </span>
        ))}
        {(multiple || valor.length === 0) && (
          <input value={q} onChange={e => setQ(e.target.value)} placeholder={placeholder} autoFocus={autoFocus}
            onFocus={() => op.length && setAbierto(true)} onBlur={() => setTimeout(() => setAbierto(false), 150)}
            onKeyDown={e => { if (e.key === 'Enter' && q.includes('@')) { e.preventDefault(); agregar(q.trim().toLowerCase()); } }}
            style={{ border: 'none', outline: 'none', flex: 1, minWidth: 160, fontSize: 14, padding: 4 }} />
        )}
      </div>
      {abierto && op.length > 0 && (
        <div style={{ position: 'absolute', zIndex: 20, left: 0, right: 0, background: '#fff', border: '1px solid #c8c6c4', borderRadius: 4, boxShadow: '0 4px 12px rgba(0,0,0,.12)', maxHeight: 220, overflowY: 'auto' }}>
          {op.map(p => (
            <div key={p.email} onMouseDown={() => agregar(p.email)} style={{ padding: '6px 10px', cursor: 'pointer', fontSize: 13 }}
              onMouseEnter={e => (e.currentTarget.style.background = '#f3f2f1')} onMouseLeave={e => (e.currentTarget.style.background = '')}>
              <div style={{ fontWeight: 600 }}>{p.nombre || nombreDe(p.email)}</div>
              <div style={{ color: '#605e5c' }}>{p.email}{p.departamento ? ' · ' + p.departamento : ''}{p.cargo ? ' · ' + p.cargo : ''}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
