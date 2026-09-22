import { useEffect, useLayoutEffect, useRef, useState } from 'react';

import { colocarMenu, colocarSubmenu, type Colocacion, type ColocacionSubmenu } from '../../lib/posicionMenu';

export interface MenuItem {
  label: string;
  icon?: string;
  onClick: () => void;
  danger?: boolean;
  divider?: boolean;
  disabled?: boolean;
  children?: MenuItem[];
}

interface Props {
  x: number;
  y: number;
  items: MenuItem[];
  onClose: () => void;
}

/** Submenú de un elemento: se abre al lado que tenga sitio y sube si se saldría por abajo. */
function Submenu({ items, onClose }: { items: MenuItem[]; onClose: () => void }) {
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
  }, [items]);

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
      {items.map((child, childIndex) => {
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

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('mousedown', handle);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', handle); document.removeEventListener('keydown', esc); };
  }, [onClose]);

  // Se mide el menú ya dibujado y se coloca donde entre entero: hacia arriba si no hay hueco
  // abajo, hacia la izquierda si no lo hay a la derecha. Antes se pintaba siempre en el punto
  // del clic y cerca del borde inferior las ultimas opciones quedaban fuera de la pantalla.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const medir = () => {
      // offsetHeight ya viene recortado si hay maxHeight puesto; scrollHeight es el alto real.
      const alto = Math.max(el.offsetHeight, el.scrollHeight);
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

  return (
    <div ref={ref} style={style}
      className="min-w-[200px] bg-white rounded-md shadow-xl border border-[#e1dfdd] py-1 animate-in fade-in duration-100">
      {items.map((item, i) => {
        if (item.divider) return <div key={i} className="h-px bg-[#edebe9] my-1" />;
        const hasChildren = !!item.children?.length;
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
                  setOpenSubmenu((current) => (current === i ? null : i));
                  return;
                }
                item.onClick();
                onClose();
              }}
              disabled={item.disabled}
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
              <Submenu items={item.children!} onClose={onClose} />
            )}
          </div>
        );
      })}
    </div>
  );
}
