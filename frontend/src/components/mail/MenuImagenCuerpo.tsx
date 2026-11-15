/**
 * Menú «⋮» de las imágenes del cuerpo de un correo (13/11/2026).
 *
 * Al pasar el cursor sobre una imagen del mensaje aparece un botón «⋮» en su esquina, con
 * «Ver en grande» y «Descargar imagen» (lib/descargarImagen.ts). El correo se pinta dentro de un
 * marco aislado sin programas, así que el botón se dibuja desde fuera, encima de la imagen.
 * En pantallas táctiles la imagen se toca para abrirla en grande, y allí está «Descargar».
 */
import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import { descargarImagenConAviso } from './descargarImagenConAviso';
import { useMenuTeclado } from '../../lib/menuTeclado';

// Iconos, firmas pequeñas y píxeles de seguimiento no llevan menú.
const LADO_MINIMO = 60;
const ESPERA_OCULTAR_MS = 350;

interface Sobre { img: HTMLImageElement; top: number; left: number }

const estiloOpcion: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, width: '100%', textAlign: 'left', padding: '8px 14px',
  border: 'none', fontSize: 13, cursor: 'pointer', whiteSpace: 'nowrap',
};

export function MenuImagenCuerpo({ marco, cargas }: { marco: RefObject<HTMLIFrameElement | null>; cargas: number }) {
  const [sobre, setSobre] = useState<Sobre | null>(null);
  const [abierto, setAbierto] = useState(false);
  const abiertoRef = useRef(false);
  const temporizador = useRef(0);
  const caja = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const cerrar = useCallback(() => { abiertoRef.current = false; setAbierto(false); }, []);
  const quitar = useCallback(() => { window.clearTimeout(temporizador.current); cerrar(); setSobre(null); }, [cerrar]);
  const quitarLuego = useCallback(() => {
    window.clearTimeout(temporizador.current);
    temporizador.current = window.setTimeout(() => { if (!abiertoRef.current) setSobre(null); }, ESPERA_OCULTAR_MS);
  }, []);
  useMenuTeclado(abierto, cerrar, menuRef, caja);

  // Escucha el cursor dentro del marco del correo (se vuelve a enganchar cada vez que el marco carga).
  useEffect(() => {
    const doc = marco.current?.contentDocument;
    if (!doc) return;
    const entrar = (e: Event) => {
      const img = e.target as HTMLImageElement | null;
      const cuadro = marco.current?.getBoundingClientRect();
      if (!img || img.tagName !== 'IMG' || !cuadro || abiertoRef.current) return;
      const r = img.getBoundingClientRect();
      if (r.width < LADO_MINIMO || r.height < LADO_MINIMO || !img.src) return;
      window.clearTimeout(temporizador.current);
      const derecha = Math.min(r.right, doc.documentElement.clientWidth);
      setSobre({ img, top: cuadro.top + Math.max(r.top, 0) + 6, left: cuadro.left + derecha - 34 });
    };
    const salir = (e: Event) => { if ((e.target as HTMLElement | null)?.tagName === 'IMG') quitarLuego(); };
    const pulsar = () => { if (abiertoRef.current) quitar(); };
    doc.addEventListener('mouseover', entrar);
    doc.addEventListener('mouseout', salir);
    doc.addEventListener('mousedown', pulsar);
    doc.addEventListener('scroll', quitar, true);
    return () => {
      doc.removeEventListener('mouseover', entrar);
      doc.removeEventListener('mouseout', salir);
      doc.removeEventListener('mousedown', pulsar);
      doc.removeEventListener('scroll', quitar, true);
    };
  }, [marco, cargas, quitar, quitarLuego]);

  // Fuera del marco: al desplazar la página el botón dejaría de coincidir con la imagen.
  useEffect(() => {
    if (!sobre) return;
    const fuera = (e: MouseEvent) => { if (caja.current && !caja.current.contains(e.target as Node)) quitar(); };
    document.addEventListener('scroll', quitar, true);
    window.addEventListener('resize', quitar);
    document.addEventListener('mousedown', fuera);
    return () => {
      document.removeEventListener('scroll', quitar, true);
      window.removeEventListener('resize', quitar);
      document.removeEventListener('mousedown', fuera);
    };
  }, [sobre, quitar]);

  useEffect(() => () => window.clearTimeout(temporizador.current), []);

  if (!sobre) return null;
  const ampliable = sobre.img.hasAttribute('data-ampliable');
  return (
    <div ref={caja} data-menu-imagen style={{ position: 'fixed', top: sobre.top, left: sobre.left, zIndex: 60 }}
      onMouseEnter={() => window.clearTimeout(temporizador.current)} onMouseLeave={quitarLuego}>
      <button type="button" aria-label="Acciones de la imagen" title="Acciones de la imagen" aria-haspopup="menu" aria-expanded={abierto}
        onClick={() => { abiertoRef.current = !abierto; setAbierto(!abierto); }}
        className="bg-white hover:bg-[#f3f2f1] text-[#323130] border border-[#e1dfdd]"
        style={{ width: 28, height: 28, borderRadius: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 6px rgba(0,0,0,0.25)', padding: 0 }}>
        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><circle cx="8" cy="3" r="1.5" /><circle cx="8" cy="8" r="1.5" /><circle cx="8" cy="13" r="1.5" /></svg>
      </button>
      {abierto && (
        <div ref={menuRef} role="menu" aria-label="Acciones de la imagen" className="bg-white border border-[#e1dfdd]"
          style={{ position: 'absolute', top: 32, right: 0, minWidth: 190, borderRadius: 6, boxShadow: '0 6px 20px rgba(0,0,0,0.14)', padding: '4px 0' }}>
          {ampliable && (
            <button type="button" role="menuitem" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloOpcion}
              onClick={() => { const img = sobre.img; quitar(); img.click(); }}>Ver en grande</button>
          )}
          <button type="button" role="menuitem" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloOpcion}
            onClick={() => { const { src, alt } = sobre.img; quitar(); void descargarImagenConAviso(src, alt); }}>Descargar imagen</button>
        </div>
      )}
    </div>
  );
}
