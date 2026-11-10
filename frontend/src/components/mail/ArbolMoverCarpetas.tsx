import { useMemo, useState, type ReactNode } from 'react';
import { getFolderDisplayName } from '../../folders';
import { construirArbolCarpetas, rutaLegible, type NodoCarpeta } from '../../lib/arbolCarpetas';
import type { Folder } from '../../types';

/* Lista en cascada para «Mover a…»: cada carpeta madre muestra una flecha para desplegar sus hijas
   (cerradas al abrir el menú) y un cuadro de búsqueda para buzones con decenas de carpetas.
   Equipo de Tecnología Maquita. */

const ICONO_CARPETA = 'M3.75 9.776c.112-.017.227-.026.344-.026h15.812c.117 0 .232.009.344.026m-16.5 0a2.25 2.25 0 00-1.883 2.542l.857 6a2.25 2.25 0 002.227 1.932H19.05a2.25 2.25 0 002.227-1.932l.857-6a2.25 2.25 0 00-1.883-2.542m-16.5 0V6A2.25 2.25 0 016 3.75h3.879a1.5 1.5 0 011.06.44l2.122 2.12a1.5 1.5 0 001.06.44H18A2.25 2.25 0 0120.25 9v.776';

function normalizar(t: string): string {
  return t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

function Flecha({ abierta }: { abierta: boolean }) {
  return (
    <svg width="12" height="12" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"
      style={{ transform: abierta ? 'rotate(90deg)' : 'none', transition: 'transform .12s' }}>
      <path fillRule="evenodd" d="M7.3 5.3a1 1 0 011.4 0l4 4a1 1 0 010 1.4l-4 4a1 1 0 01-1.4-1.4L10.6 10 7.3 6.7a1 1 0 010-1.4z" clipRule="evenodd" />
    </svg>
  );
}

function IconoCarpeta() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#605e5c" strokeWidth={1.5}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0"><path d={ICONO_CARPETA} /></svg>
  );
}

export function ArbolMoverCarpetas({ carpetas, carpetaActual, onElegir, compacto = true }: {
  carpetas: (Folder | string)[];
  carpetaActual: string;
  onElegir: (nombre: string) => void;
  compacto?: boolean;
}) {
  const [abiertas, setAbiertas] = useState<Record<string, boolean>>({});
  const [filtro, setFiltro] = useState('');
  const arbol = useMemo(() => construirArbolCarpetas(carpetas), [carpetas]);
  const planas = useMemo(() => (carpetas || []).map(f => (typeof f === 'string' ? f : f.name)).filter(Boolean), [carpetas]);
  const claseFila = compacto
    ? 'w-full text-left py-1.5 pr-3 text-[13px] flex items-center gap-2 hover:bg-[#f3f2f1] text-[#323130]'
    : 'w-full text-left py-3 pr-4 text-[14px] flex items-center gap-3 hover:bg-[#f3f2f1] active:bg-[#e1dfdd] text-[#323130]';

  const alternar = (nombre: string) => setAbiertas(a => ({ ...a, [nombre]: !a[nombre] }));

  const pintar = (nodo: NodoCarpeta): ReactNode => {
    const esActual = nodo.nombre === carpetaActual;
    const tieneHijas = nodo.hijas.length > 0;
    const abierta = !!abiertas[nodo.nombre];
    return (
      <div key={nodo.nombre} role="treeitem" aria-expanded={tieneHijas ? abierta : undefined} aria-selected={esActual}>
        <div className={`${claseFila} ${esActual ? 'opacity-50' : ''}`} style={{ paddingLeft: 8 + nodo.nivel * 16 }}>
          <button type="button" aria-label={abierta ? 'Contraer' : 'Desplegar'} tabIndex={tieneHijas ? 0 : -1}
            className={`w-5 h-5 flex items-center justify-center rounded text-[#605e5c] hover:bg-[#e1dfdd] shrink-0 ${tieneHijas ? '' : 'invisible'}`}
            onClick={(e) => { e.stopPropagation(); alternar(nodo.nombre); }}>
            <Flecha abierta={abierta} />
          </button>
          <button type="button" disabled={esActual} title={rutaLegible(nodo.nombre, getFolderDisplayName)}
            className="flex-1 min-w-0 flex items-center gap-2 text-left disabled:cursor-default"
            onClick={() => onElegir(nodo.nombre)}>
            <IconoCarpeta />
            <span className="truncate">{getFolderDisplayName(nodo.nombre)}</span>
            {tieneHijas && !abierta && <span className="text-[11px] text-[#8a8886] shrink-0">({nodo.hijas.length})</span>}
          </button>
        </div>
        {tieneHijas && abierta && <div role="group">{nodo.hijas.map(pintar)}</div>}
      </div>
    );
  };

  const texto = normalizar(filtro.trim());
  const coincidencias = texto
    ? planas.filter(n => n !== carpetaActual && normalizar(rutaLegible(n, getFolderDisplayName)).includes(texto))
    : [];

  return (
    <div className="min-w-[260px] max-w-[360px]">
      <div className="px-2 pt-1 pb-1.5 sticky top-0 bg-white z-10 border-b border-[#edebe9]">
        <input type="search" value={filtro} onChange={e => setFiltro(e.target.value)} autoFocus={compacto}
          placeholder="Buscar carpeta…" aria-label="Buscar carpeta de destino"
          className="w-full h-7 px-2 text-[13px] border border-[#c8c6c4] rounded focus:outline-none focus:border-[#0078d4]"
          onKeyDown={e => { if (e.key === 'Enter' && coincidencias.length === 1) onElegir(coincidencias[0]); }} />
      </div>
      {texto ? (
        coincidencias.length === 0
          ? <div className="px-3 py-2 text-[13px] text-[#8a8886]">Sin carpetas con «{filtro.trim()}»</div>
          : coincidencias.map(n => (
            <button key={n} type="button" className={`${claseFila} pl-3`} onClick={() => onElegir(n)}>
              <IconoCarpeta />
              <span className="truncate">{rutaLegible(n, getFolderDisplayName)}</span>
            </button>
          ))
      ) : (
        <div role="tree" aria-label="Carpetas de destino">{arbol.map(pintar)}</div>
      )}
    </div>
  );
}
