/**
 * Cuadro propio para escribir o cambiar la dirección de un enlace del mensaje (en lugar de la
 * ventana del navegador). Intro acepta y Esc cancela. Se abre con `pedirEnlace`.
 */
import { useEffect, useRef, useState } from 'react';
import { normalizarEnlace } from './enlaces';

export interface PropsCuadroEnlace { inicial: string; permiteVacio: boolean; alTerminar: (valor: string | null) => void }

export function CuadroEnlace({ inicial, permiteVacio, alTerminar }: PropsCuadroEnlace) {
  const [valor, setValor] = useState(inicial);
  const entrada = useRef<HTMLInputElement>(null);
  useEffect(() => { entrada.current?.focus(); entrada.current?.select(); }, []);
  const aceptar = () => {
    const url = normalizarEnlace(valor);
    if (!url && !permiteVacio) { entrada.current?.focus(); return; }
    alTerminar(url);
  };
  const boton: React.CSSProperties = { padding: '6px 14px', borderRadius: 4, fontSize: 13, cursor: 'pointer', border: '1px solid #d2d0ce', background: '#fff', color: '#323130' };
  return (
    <div
      onMouseDown={e => { if (e.target === e.currentTarget) alTerminar(null); }}
      style={{ position: 'fixed', inset: 0, zIndex: 10000, background: 'rgba(0,0,0,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="cuadro-enlace-titulo"
        onKeyDown={e => {
          if (e.key === 'Escape') { e.stopPropagation(); alTerminar(null); }
          if (e.key === 'Enter') { e.preventDefault(); aceptar(); }
        }}
        style={{ width: 'min(440px, 100%)', background: '#fff', borderRadius: 8, boxShadow: '0 8px 32px rgba(0,0,0,0.25)', padding: 20 }}
      >
        <div id="cuadro-enlace-titulo" style={{ fontSize: 15, fontWeight: 600, color: '#323130', marginBottom: 10 }}>Dirección del enlace</div>
        <input
          ref={entrada}
          type="text"
          inputMode="url"
          value={valor}
          onChange={e => setValor(e.target.value)}
          placeholder="https://…"
          aria-label="Dirección del enlace"
          style={{ width: '100%', boxSizing: 'border-box', padding: '7px 9px', fontSize: 14, border: '1px solid #8a8886', borderRadius: 4, outline: 'none', color: '#323130' }}
        />
        <div style={{ fontSize: 12, color: '#605e5c', marginTop: 6 }}>
          {permiteVacio ? 'Si la deja vacía, se quita el enlace y el texto se conserva.' : 'Puede escribirla sin «https://»; se completa sola.'}
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
          <button type="button" style={boton} onClick={() => alTerminar(null)}>Cancelar</button>
          <button type="button" style={{ ...boton, background: '#0f6cbd', borderColor: '#0f6cbd', color: '#fff' }} onClick={aceptar}>Aceptar</button>
        </div>
      </div>
    </div>
  );
}
