/**
 * Selector del área de la firma (09/11/2026).
 *
 * Pedido: «debo poder seleccionar la hoja y dibujar con el ratón el rectángulo donde irá la
 * firma, como en el editor PDF de Raíces; las ubicaciones por defecto no sirven». Muestra la
 * página (imagen que dibuja el servidor), deja pasar de página y arrastrar para dibujar el
 * rectángulo; funciona con ratón y con el dedo (eventos pointer). El rectángulo se guarda en
 * puntos PDF con origen abajo-izquierda, que es lo que Raíces espera.
 */
import { useEffect, useRef, useState } from 'react';
import { cargarPaginaFirma, ErrorFirmaPdf, type AreaFirma, type OrigenPdf, type PaginaFirma } from '../../../lib/firmaPdf';

interface Props {
  origen: OrigenPdf;
  /** Página con la que arrancar (p. ej. la de la firma anterior); -1 = última. */
  paginaInicial?: number;
  area: AreaFirma | null;
  onChange: (area: AreaFirma | null) => void;
  disabled?: boolean;
}

/** Sello por defecto (puntos) cuando la persona solo toca la página sin arrastrar. */
const SELLO_ANCHO_PT = 200;
const SELLO_ALTO_PT = 70;
const MINIMO_ARRASTRE_PX = 12;

interface RectPx { x: number; y: number; w: number; h: number }

export function SelectorAreaFirma({ origen, paginaInicial = -1, area, onChange, disabled }: Props) {
  const [pagina, setPagina] = useState(paginaInicial);   // -1 = última (lo habitual al firmar)
  const [info, setInfo] = useState<PaginaFirma | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [borrador, setBorrador] = useState<RectPx | null>(null);
  const contenedor = useRef<HTMLDivElement>(null);
  const imagen = useRef<HTMLImageElement>(null);
  const inicio = useRef<{ x: number; y: number } | null>(null);
  const urlActual = useRef<string>('');

  // Cargar la página (al cambiar de página se vuelve a pedir; el ancho se ajusta al contenedor).
  useEffect(() => {
    let vigente = true;
    setCargando(true); setError('');
    const anchoCss = contenedor.current?.clientWidth || 520;
    const anchoPx = Math.min(1600, Math.round(anchoCss * Math.min(window.devicePixelRatio || 1, 2)));
    cargarPaginaFirma(origen, pagina, anchoPx)
      .then(p => {
        if (!vigente) { URL.revokeObjectURL(p.url); return; }
        if (urlActual.current) URL.revokeObjectURL(urlActual.current);
        urlActual.current = p.url;
        setInfo(p);
        if (pagina === -1 || p.pagina !== pagina) setPagina(p.pagina);
      })
      .catch((e: unknown) => {
        if (!vigente) return;
        setError(e instanceof ErrorFirmaPdf ? e.message : 'No se pudo mostrar la página del PDF.');
      })
      .finally(() => { if (vigente) setCargando(false); });
    return () => { vigente = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [origen, pagina]);

  useEffect(() => () => { if (urlActual.current) URL.revokeObjectURL(urlActual.current); }, []);

  const irA = (n: number) => {
    if (!info) return;
    const destino = Math.max(1, Math.min(info.paginas, n));
    if (destino === info.pagina) return;
    onChange(null);                 // el área pertenece a una página concreta
    setBorrador(null);
    setPagina(destino);
  };

  // ---- conversión píxeles (imagen mostrada) ↔ puntos PDF ----
  const escala = () => {
    const img = imagen.current;
    if (!img || !info || !img.clientWidth) return 1;
    return info.anchoPt / img.clientWidth;     // puntos por píxel CSS
  };
  const aPuntos = (r: RectPx): AreaFirma | null => {
    if (!info) return null;
    const s = escala();
    return {
      pagina: info.pagina,
      x: r.x * s,
      y: info.altoPt - (r.y + r.h) * s,
      ancho: r.w * s,
      alto: r.h * s,
    };
  };
  const aPixeles = (a: AreaFirma): RectPx | null => {
    if (!info || a.pagina !== info.pagina) return null;
    const s = escala();
    if (!s) return null;
    return { x: a.x / s, y: (info.altoPt - a.y - a.alto) / s, w: a.ancho / s, h: a.alto / s };
  };

  const puntoLocal = (e: React.PointerEvent) => {
    const r = imagen.current!.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(r.width, e.clientX - r.left)),
      y: Math.max(0, Math.min(r.height, e.clientY - r.top)),
      w: r.width, h: r.height,
    };
  };

  const alPresionar = (e: React.PointerEvent<HTMLDivElement>) => {
    if (disabled || !info || !imagen.current) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    const p = puntoLocal(e);
    inicio.current = { x: p.x, y: p.y };
    setBorrador({ x: p.x, y: p.y, w: 0, h: 0 });
  };
  const alMover = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!inicio.current) return;
    const p = puntoLocal(e);
    const { x: x0, y: y0 } = inicio.current;
    setBorrador({ x: Math.min(x0, p.x), y: Math.min(y0, p.y), w: Math.abs(p.x - x0), h: Math.abs(p.y - y0) });
  };
  const alSoltar = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!inicio.current || !info) return;
    const p = puntoLocal(e);
    const { x: x0, y: y0 } = inicio.current;
    inicio.current = null;
    let r: RectPx = { x: Math.min(x0, p.x), y: Math.min(y0, p.y), w: Math.abs(p.x - x0), h: Math.abs(p.y - y0) };
    if (r.w < MINIMO_ARRASTRE_PX || r.h < MINIMO_ARRASTRE_PX) {
      // Un toque: sello de tamaño estándar centrado donde se tocó, sin salirse de la hoja.
      const s = escala();
      const w = Math.min(p.w, SELLO_ANCHO_PT / s), h = Math.min(p.h, SELLO_ALTO_PT / s);
      r = { x: Math.max(0, Math.min(p.w - w, p.x - w / 2)), y: Math.max(0, Math.min(p.h - h, p.y - h / 2)), w, h };
    }
    setBorrador(null);
    onChange(aPuntos(r));
  };

  const rect = borrador || (area ? aPixeles(area) : null);
  const botonNav = 'h-[34px] min-w-[34px] px-2 rounded border border-[#8a8886] bg-white dark:bg-[#1e1e1e] text-[13px] disabled:opacity-40';

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <span className="text-[12px] font-medium text-[#605e5c] dark:text-[#aaa]">Dónde va la firma</span>
        <div className="flex items-center gap-1 text-[13px]">
          <button type="button" className={botonNav} onClick={() => irA((info?.pagina || 1) - 1)}
            disabled={!info || info.pagina <= 1 || cargando} aria-label="Página anterior">◀</button>
          <span className="px-1 whitespace-nowrap">
            Página{' '}
            <input type="number" min={1} max={info?.paginas || 1} value={info?.pagina || ''} aria-label="Número de página"
              onChange={e => irA(Number(e.target.value))} disabled={!info || cargando}
              className="w-[52px] h-[34px] px-1 text-center rounded border border-[#8a8886] bg-white dark:bg-[#1e1e1e]" />
            {' '}de {info?.paginas || '…'}
          </span>
          <button type="button" className={botonNav} onClick={() => irA((info?.pagina || 1) + 1)}
            disabled={!info || info.pagina >= info.paginas || cargando} aria-label="Página siguiente">▶</button>
        </div>
      </div>

      <div ref={contenedor} className="relative w-full border border-[#8a8886] dark:border-[#555] rounded bg-[#f3f2f1] dark:bg-[#1e1e1e] overflow-hidden"
        style={{ minHeight: 160 }}>
        {info && (
          <img ref={imagen} src={info.url} alt={`Página ${info.pagina}`} draggable={false}
            className={'block w-full select-none ' + (cargando ? 'opacity-50' : '')} />
        )}
        {info && (
          <div className="absolute inset-0" style={{ touchAction: 'none', cursor: disabled ? 'default' : 'crosshair' }}
            onPointerDown={alPresionar} onPointerMove={alMover} onPointerUp={alSoltar} onPointerCancel={() => { inicio.current = null; setBorrador(null); }}
            role="application" aria-label="Arrastre para dibujar el área de la firma">
            {rect && rect.w > 0 && rect.h > 0 && (
              <div className="absolute border-2 border-[#0078d4] bg-[#0078d4]/15 flex items-center justify-center pointer-events-none"
                style={{ left: rect.x, top: rect.y, width: rect.w, height: rect.h }}>
                <span className="text-[11px] font-semibold text-[#0b57c9] bg-white/80 px-1 rounded">Firma</span>
              </div>
            )}
          </div>
        )}
        {cargando && (
          <div className="absolute inset-0 flex items-center justify-center gap-2 text-[13px] text-[#605e5c]">
            <div className="animate-spin w-5 h-5 border-2 border-[#0078d4] border-t-transparent rounded-full" />
            Cargando la página…
          </div>
        )}
        {error && !cargando && (
          <p role="alert" className="absolute inset-0 flex items-center justify-center p-4 text-center text-[13px] text-[#a4262c]">{error}</p>
        )}
      </div>

      <p className="text-[12px] text-[#605e5c] dark:text-[#aaa]">
        {area
          ? <>Firma en la página {area.pagina}. Vuelva a arrastrar para cambiar el lugar.{' '}
              <button type="button" className="text-[#0078d4] hover:underline" onClick={() => { onChange(null); setBorrador(null); }}>Quitar</button></>
          : 'Arrastre sobre la hoja (con el ratón o el dedo) para dibujar el rectángulo donde irá la firma. Un toque coloca un sello de tamaño normal.'}
      </p>
    </div>
  );
}
