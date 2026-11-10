import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

import { colocarMenu, colocarSubmenu, type Colocacion, type ColocacionSubmenu } from '../../lib/posicionMenu';

export interface MenuItem {
  label: string;
  icon?: string;
  onClick: () => void;
  danger?: boolean;
  divider?: boolean;
  disabled?: boolean;
  children?: MenuItem[];
  /** Panel propio como submenú (p. ej. el árbol de carpetas de «Mover a…»); tiene prioridad sobre children. */
  contenido?: ReactNode;
}

interface Props {
  x: number;
  y: number;
  items: MenuItem[];
  onClose: () => void;
}

/** Submenú de un elemento: se abre al lado que tenga sitio y sube si se saldría por abajo. */
function Submenu({ items, contenido, onClose }: { items: MenuItem[]; contenido?: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [sitio, setSitio] = useState<ColocacionSubmenu | null>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    const padre = el?.parentElement;
    if (!el || !padre) return;
    const caja = padre.getBoundingClientRect();
    setSitio(
      colocarSubmenu(
        { left: caja.left, right: caja.right, top: caja.top },
        { ancho: el.offsetWidth, alto: el.offsetHeight },
        { ancho: window.innerWidth, alto: window.innerHeight },
      ),
    );
  }, [items, contenido]);

  const estilo: React.CSSProperties = sitio
    ? {
        [sitio.aLaDerecha ? 'left' : 'right']: '100%',
        top: sitio.desplazamientoY - 4,
        maxHeight: sitio.maxAlto,
        overflowY: 'auto',
      }
    : { left: '100%', top: -4, visibility: 'hidden' };

  return (
    <div ref={ref} style={estilo}
      className="absolute min-w-[220px] bg-white rounded-md shadow-xl border border-[#e1dfdd] py-1 z-[10000]">
      {contenido}
      {!contenido && items.map((child, childIndex) => {
        if (child.divider) return <div key={childIndex} className="h-px bg-[#edebe9] my-1" />;
        return (
          <button
            key={childIndex}
            onClick={() => { child.onClick(); onClose(); }}
            disabled={child.disabled}
            className={`w-full flex items-center gap-2.5 px-3 py-[6px] text-[13px] transition-colors text-left ${
              child.disabled ? 'text-[#c8c6c4] cursor-default' :
              child.danger ? 'text-[#a4262c] hover:bg-[#fde7e9]' :
              'text-[#323130] hover:bg-[#f3f2f1]'
            }`}
          >
            {child.icon && (
              <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={child.icon} />
              </svg>
            )}
            {child.label}
          </button>
        );
      })}
    </div>
  );
}

export function ContextMenu({ x, y, items, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [openSubmenu, setOpenSubmenu] = useState<number | null>(null);
  // Timer para cerrar el submenu con retraso (permite mover el mouse hacia el)
  const cerrarSubmenuRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Dónde cabe de verdad el menú. Hasta medirlo no se pinta, para no verlo saltar.
  const [sitio, setSitio] = useState<Colocacion | null>(null);
  // Solo si no cabe entero se le pone scroll propio: con scroll, los submenús (que salen por
  // el lateral) quedarían recortados, así que no se activa cuando no hace falta.
  const [desborda, setDesborda] = useState(false);

  // Se cierra con cualquier clic fuera del menú. Se escucha en fase de captura: antes, una zona que
  // cortaba la propagación del mousedown (o el correo abierto, que va en un iframe y no avisa al
  // documento) dejaba el menú fijo en pantalla hasta volver a hacer clic en el mismo correo
  // (queja de usuarios, 05/11/2026). El iframe se cubre con «blur»: al hacer clic dentro, la ventana
  // pierde el foco. También se cierra al desplazar la página fuera del menú o cambiar de pestaña.
  useEffect(() => {
    const fuera = (e: Event) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    const cerrar = () => onClose();
    document.addEventListener('pointerdown', fuera, true);
    document.addEventListener('mousedown', fuera, true);
    document.addEventListener('wheel', fuera, { capture: true, passive: true });
    document.addEventListener('keydown', esc);
    window.addEventListener('blur', cerrar);
    document.addEventListener('visibilitychange', cerrar);
    return () => {
      document.removeEventListener('pointerdown', fuera, true);
      document.removeEventListener('mousedown', fuera, true);
      document.removeEventListener('wheel', fuera, true);
      document.removeEventListener('keydown', esc);
      window.removeEventListener('blur', cerrar);
      document.removeEventListener('visibilitychange', cerrar);
    };
  }, [onClose]);

  // Se mide el menú ya dibujado y se coloca donde entre entero: hacia arriba si no hay hueco
  // abajo, hacia la izquierda si no lo hay a la derecha. Antes se pintaba siempre en el punto
  // del clic y cerca del borde inferior las ultimas opciones quedaban fuera de la pantalla.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const medir = () => {
      // Alto propio = suma de las filas (py-1 arriba y abajo). No vale scrollHeight: incluía el
      // submenú abierto (el árbol de «Mover a…» mide 2000 px antes de recortarse) y el menú se
      // ponía scroll a sí mismo, lo que ocultaba el submenú (10/11/2026).
      const filas = Array.from(el.children).reduce((suma, hijo) => suma + (hijo as HTMLElement).offsetHeight, 0);
      const alto = Math.max(el.offsetHeight, filas + 8);
      const colocacion = colocarMenu(x, y, { ancho: el.offsetWidth, alto },
        { ancho: window.innerWidth, alto: window.innerHeight });
      setSitio(colocacion);
      setDesborda(alto > colocacion.maxAlto);
    };
    medir();
    window.addEventListener('resize', medir);
    return () => window.removeEventListener('resize', medir);
  }, [x, y, items]);

  const style: React.CSSProperties = {
    position: 'fixed',
    zIndex: 9999,
    left: sitio ? sitio.left : x,
    top: sitio ? sitio.top : y,
    // Menú más largo que la pantalla (muchas carpetas en «Mover a»): se desplaza por dentro.
    maxHeight: desborda ? sitio?.maxAlto : undefined,
    overflowY: desborda ? 'auto' : undefined,
    // Sin medir aún: ocupa sitio para poder medirlo, pero no se ve.
    visibility: sitio ? 'visible' : 'hidden',
  };

  // Se dibuja en <body>: dentro de la lista quedaba en su capa y la barra superior lo tapaba
  // al abrirse hacia arriba (04/11/2026).
  return createPortal(
    <div ref={ref} style={style}
      className="min-w-[200px] bg-white rounded-md shadow-xl border border-[#e1dfdd] py-1 animate-in fade-in duration-100">
      {items.map((item, i) => {
        if (item.divider) return <div key={i} className="h-px bg-[#edebe9] my-1" />;
        const hasChildren = !!item.children?.length || !!item.contenido;
        return (
          <div
            key={i}
            className="relative"
            onMouseEnter={() => {
              if (cerrarSubmenuRef.current) { clearTimeout(cerrarSubmenuRef.current); cerrarSubmenuRef.current = null; }
              setOpenSubmenu(hasChildren ? i : null);
            }}
            onMouseLeave={() => {
              // Retraso: da tiempo a llegar al submenu sin que se cierre
              if (cerrarSubmenuRef.current) clearTimeout(cerrarSubmenuRef.current);
              cerrarSubmenuRef.current = setTimeout(() => {
                setOpenSubmenu((current) => (current === i ? null : current));
              }, 300);
            }}
          >
            <button
              onClick={() => {
                if (hasChildren) {
                  // Abrir siempre, nunca alternar: el puntero ya lo abrió al pasar por encima y
                  // el clic de quien quiere elegir carpeta lo cerraba (revisión 04/11/2026, n.º 14).
                  setOpenSubmenu(i);
                  return;
                }
                item.onClick();
                onClose();
              }}
              disabled={item.disabled}
              aria-haspopup={hasChildren ? 'menu' : undefined}
              aria-expanded={hasChildren ? openSubmenu === i : undefined}
              className={`w-full flex items-center gap-2.5 px-3 py-[6px] text-[13px] transition-colors text-left ${
                item.disabled ? 'text-[#c8c6c4] cursor-default' :
                item.danger ? 'text-[#a4262c] hover:bg-[#fde7e9]' :
                'text-[#323130] hover:bg-[#f3f2f1]'
              }`}
            >
              {item.icon && (
                <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
                </svg>
              )}
              <span className="flex-1">{item.label}</span>
              {hasChildren && (
                <svg className="w-3.5 h-3.5 shrink-0 text-[#605e5c]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 6l6 6-6 6" />
                </svg>
              )}
            </button>
            {hasChildren && openSubmenu === i && (
              <Submenu items={item.children || []} contenido={item.contenido} onClose={onClose} />
            )}
          </div>
        );
      })}
    </div>
  , document.body);
}
