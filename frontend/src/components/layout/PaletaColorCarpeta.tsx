/** Paleta para elegir el color de una carpeta (clic derecho → «Color de la carpeta»). */
import { useEffect, useRef } from 'react';
import { PALETA_CARPETAS } from '../../lib/coloresCarpetas';

export function PaletaColorCarpeta({ x, y, actual, onElegir, onCerrar }: {
  x: number; y: number; actual?: string; onElegir: (color: string | null) => void; onCerrar: () => void;
}) {
  const caja = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const fuera = (e: MouseEvent) => { if (caja.current && !caja.current.contains(e.target as Node)) onCerrar(); };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onCerrar(); };
    document.addEventListener('mousedown', fuera);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', fuera); document.removeEventListener('keydown', esc); };
  }, [onCerrar]);
  const izquierda = Math.min(x, window.innerWidth - 230);
  const arriba = Math.min(y, window.innerHeight - 130);
  return (
    <div ref={caja} role="dialog" aria-label="Color de la carpeta" className="bg-white border border-[#e1dfdd]"
      style={{ position: 'fixed', left: izquierda, top: arriba, zIndex: 9999, padding: 10, borderRadius: 6, boxShadow: '0 6px 18px rgba(0,0,0,.2)', width: 214 }}>
      <div style={{ fontSize: 12, color: '#605e5c', marginBottom: 8 }}>Color de la carpeta</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8 }}>
        {PALETA_CARPETAS.map((c) => (
          <button key={c.valor} type="button" title={c.nombre} aria-label={c.nombre} aria-pressed={actual === c.valor}
            onClick={() => { onElegir(c.valor); onCerrar(); }}
            style={{
              width: 30, height: 30, borderRadius: 15, background: c.valor, cursor: 'pointer',
              border: actual === c.valor ? '3px solid #201f1e' : '2px solid #fff', boxShadow: '0 0 0 1px #c8c6c4',
            }} />
        ))}
      </div>
      <button type="button" onClick={() => { onElegir(null); onCerrar(); }} className="hover:bg-[#f3f2f1]"
        style={{ marginTop: 10, width: '100%', fontSize: 12, padding: '5px 0', border: '1px solid #d2d0ce', borderRadius: 4, background: '#fff', color: '#323130', cursor: 'pointer' }}>
        Sin color
      </button>
    </div>
  );
}
