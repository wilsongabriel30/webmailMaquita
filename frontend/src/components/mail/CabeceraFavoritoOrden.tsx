/**
 * ⭐ «Agregar a Favoritos» y ↑↓ «Ordenar» de la cabecera de la lista (07/11/2026, como Outlook).
 */
import { useEffect, useRef, useState } from 'react';
import { FAVORITAS_FIJAS, alternarFavorita, useCarpetasFavoritas } from '../../lib/carpetasFavoritas';
import { NOMBRES_ORDEN, fijarOrden, useOrdenLista, type CampoOrden } from '../../lib/ordenLista';
import { showToast } from '../common/Toast';

export function BotonFavoritoCarpeta({ carpeta }: { carpeta: string }) {
  const favoritas = useCarpetasFavoritas();
  if (!carpeta || carpeta.startsWith('Virtual.')) return null;
  const fija = FAVORITAS_FIJAS.includes(carpeta);
  const es = fija || favoritas.includes(carpeta);
  return (
    <button type="button" disabled={fija}
      onClick={() => showToast(alternarFavorita(carpeta) ? 'Agregada a Favoritos' : 'Quitada de Favoritos')}
      title={fija ? 'Siempre está en Favoritos' : es ? 'Quitar de Favoritos' : 'Agregar a Favoritos'}
      aria-label={es ? 'Quitar de Favoritos' : 'Agregar a Favoritos'} aria-pressed={es}
      className="p-0.5 rounded shrink-0 hover:bg-[#f3f2f1] disabled:cursor-default disabled:hover:bg-transparent"
      style={{ color: es ? '#c19c00' : '#8a8886', lineHeight: 0 }}>
      <svg width="15" height="15" viewBox="0 0 16 16" fill={es ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" aria-hidden="true">
        <path d="M8 1.8l1.9 3.9 4.3.6-3.1 3 .7 4.3L8 11.6l-3.8 2 .7-4.3-3.1-3 4.3-.6z" />
      </svg>
    </button>
  );
}

const CAMPOS: CampoOrden[] = ['fecha', 'remitente', 'asunto', 'tamano'];
const estiloOpcion: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8, width: '100%', textAlign: 'left', padding: '7px 14px',
  border: 'none', fontSize: 13, color: '#323130', cursor: 'pointer', whiteSpace: 'nowrap',
};

export function BotonOrdenLista() {
  const orden = useOrdenLista();
  const [abierto, setAbierto] = useState(false);
  const caja = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: MouseEvent) => { if (caja.current && !caja.current.contains(e.target as Node)) setAbierto(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setAbierto(false); };
    document.addEventListener('mousedown', fuera);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', fuera); document.removeEventListener('keydown', esc); };
  }, [abierto]);
  const cambiado = orden.campo !== 'fecha' || orden.inverso;
  const marca = (si: boolean) => <span style={{ width: 14, color: '#0078d4' }}>{si ? '✓' : ''}</span>;
  const textoDir = orden.campo === 'fecha' || orden.campo === 'tamano'
    ? [orden.campo === 'fecha' ? 'Más recientes arriba' : 'Más grandes arriba', orden.campo === 'fecha' ? 'Más antiguos arriba' : 'Más pequeños arriba']
    : ['De la A a la Z', 'De la Z a la A'];
  return (
    <div ref={caja} className="relative shrink-0">
      <button type="button" onClick={() => setAbierto(v => !v)} aria-haspopup="menu" aria-expanded={abierto}
        title={`Ordenar (ahora: ${NOMBRES_ORDEN[orden.campo]})`} aria-label="Ordenar"
        className={`p-1 rounded hover:bg-[#f3f2f1] ${cambiado ? 'text-[#0078d4]' : 'text-[#605e5c]'}`} style={{ lineHeight: 0 }}>
        <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M4.5 13V3M2 5.5L4.5 3 7 5.5M11.5 3v10M9 10.5l2.5 2.5 2.5-2.5" />
        </svg>
      </button>
      {abierto && (
        <div role="menu" className="absolute right-0 top-full mt-1 z-50 bg-white border border-[#e1dfdd] rounded-md py-1 min-w-[210px]"
          style={{ boxShadow: '0 6px 20px rgba(0,0,0,0.14)' }}>
          <div style={{ padding: '4px 14px 2px', fontSize: 11, fontWeight: 600, color: '#605e5c' }}>Ordenar por</div>
          {CAMPOS.map(c => (
            <button key={c} type="button" role="menuitemradio" aria-checked={orden.campo === c} className="bg-transparent hover:bg-[#f3f2f1]" style={estiloOpcion}
              onClick={() => { fijarOrden({ campo: c, inverso: false }); setAbierto(false); }}>{marca(orden.campo === c)}{NOMBRES_ORDEN[c]}</button>
          ))}
          <div style={{ height: 1, background: '#edebe9', margin: '4px 0' }} />
          {[false, true].map(inv => (
            <button key={String(inv)} type="button" role="menuitemradio" aria-checked={orden.inverso === inv} className="bg-transparent hover:bg-[#f3f2f1]" style={estiloOpcion}
              onClick={() => { fijarOrden({ campo: orden.campo, inverso: inv }); setAbierto(false); }}>{marca(orden.inverso === inv)}{textoDir[inv ? 1 : 0]}</button>
          ))}
          <div style={{ padding: '4px 14px', fontSize: 11, color: '#8a8886', whiteSpace: 'normal' }}>Ordena los correos cargados en la lista.</div>
        </div>
      )}
    </div>
  );
}
