// Visor de imágenes incrustadas en el cuerpo del correo (08/10/2026). Antes solo se veían al tamaño que
// venían en el mensaje; ahora un clic las abre en grande, con anterior/siguiente, zoom al tamaño real y descarga.
import { useEffect, useState } from 'react';

export interface ImagenCuerpo { src: string; alt: string }

interface Props {
  imagenes: ImagenCuerpo[];
  indice: number;
  onCerrar: () => void;
  onIr: (indice: number) => void;
}

export default function VisorImagenCuerpo({ imagenes, indice, onCerrar, onIr }: Props) {
  const [real, setReal] = useState(false);       // false = ajustada a la pantalla; true = tamaño real
  const [cargando, setCargando] = useState(true);
  const total = imagenes.length;
  const actual = imagenes[indice];

  // Al cambiar de imagen se vuelve a «ajustada» y se muestra el giro de carga (sin efecto: se hace al navegar)
  const ir = (i: number) => { setCargando(true); setReal(false); onIr(i); };

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); onCerrar(); }
      else if (e.key === 'ArrowRight' && indice < total - 1) ir(indice + 1);
      else if (e.key === 'ArrowLeft' && indice > 0) ir(indice - 1);
    };
    // captura: el Escape del visor no debe cerrar también el mensaje de fondo
    window.addEventListener('keydown', h, true);
    return () => window.removeEventListener('keydown', h, true);
  }, [indice, total, onCerrar, onIr]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!actual) return null;
  const nombre = actual.alt || `imagen ${indice + 1}`;
  const boton = 'p-2 rounded text-white bg-white/10 hover:bg-white/25 disabled:opacity-30 disabled:cursor-default';

  return (
    <div
      data-visor-imagen
      className="fixed inset-0 z-[100] flex flex-col bg-black/85"
      onClick={onCerrar}
      role="dialog"
      aria-label={`Imagen ${indice + 1} de ${total}`}
    >
      {/* Barra superior */}
      <div className="flex items-center justify-between px-3 py-2 text-white text-[13px]" onClick={e => e.stopPropagation()}>
        <span className="truncate">{nombre}{total > 1 ? ` · ${indice + 1} de ${total}` : ''}</span>
        <div className="flex items-center gap-1">
          <button className={boton} onClick={() => setReal(v => !v)} title={real ? 'Ajustar a la pantalla' : 'Tamaño real'}>
            {real ? 'Ajustar' : 'Tamaño real'}
          </button>
          <a className={boton} href={actual.src} download target="_blank" rel="noopener noreferrer" title="Descargar">Descargar</a>
          <button className={boton} onClick={onCerrar} aria-label="Cerrar" title="Cerrar (Esc)">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
      </div>

      {/* Imagen */}
      <div className={`flex-1 min-h-0 flex items-center justify-center p-2 ${real ? 'overflow-auto' : 'overflow-hidden'}`}>
        {cargando && <div className="absolute animate-spin rounded-full h-8 w-8 border-2 border-white border-t-transparent" />}
        <img
          src={actual.src}
          alt={nombre}
          onClick={e => { e.stopPropagation(); setReal(v => !v); }}
          onLoad={() => setCargando(false)}
          onError={() => setCargando(false)}
          className={real ? 'max-w-none cursor-zoom-out' : 'max-w-full max-h-full object-contain cursor-zoom-in'}
          style={{ visibility: cargando ? 'hidden' : 'visible' }}
        />
      </div>

      {/* Anterior / siguiente */}
      {total > 1 && (
        <>
          <button className={`${boton} absolute left-2 top-1/2 -translate-y-1/2`} disabled={indice === 0} onClick={e => { e.stopPropagation(); ir(indice - 1); }} aria-label="Anterior">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" /></svg>
          </button>
          <button className={`${boton} absolute right-2 top-1/2 -translate-y-1/2`} disabled={indice === total - 1} onClick={e => { e.stopPropagation(); ir(indice + 1); }} aria-label="Siguiente">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
          </button>
        </>
      )}
    </div>
  );
}
