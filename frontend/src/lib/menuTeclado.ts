/**
 * Teclado en los menús desplegables («⋯» del correo, «▾» del adjunto, «Ordenar»; 08/11/2026).
 *
 * Al abrirse, el foco pasa a la primera opción; ↑/↓ recorren las opciones (dando la vuelta),
 * Inicio/Fin van a la primera/última, Escape o Tab cierran y el foco vuelve al botón que abrió.
 * El ratón sigue funcionando igual: esto solo suma el teclado (accesibilidad).
 */
import { useEffect, type RefObject } from 'react';

const OPCIONES = '[role="menuitem"],[role="menuitemradio"],[role="menuitemcheckbox"]';

function opciones(menu: HTMLElement | null): HTMLElement[] {
  return menu ? Array.from(menu.querySelectorAll<HTMLElement>(OPCIONES)).filter(o => !o.hasAttribute('disabled')) : [];
}

export function useMenuTeclado(
  abierto: boolean,
  cerrar: () => void,
  menuRef: RefObject<HTMLElement | null>,
  cajaRef: RefObject<HTMLElement | null>,
): void {
  useEffect(() => {
    if (!abierto) return;
    const boton = cajaRef.current?.querySelector<HTMLElement>('[aria-haspopup="menu"]') ?? null;
    // Las opciones se enfocan con tabIndex -1 para no alargar el recorrido con Tab.
    const lista = opciones(menuRef.current);
    lista.forEach(o => { if (!o.hasAttribute('tabindex')) o.tabIndex = -1; });
    const primero = window.setTimeout(() => lista[0]?.focus(), 0);

    const alTeclear = (e: KeyboardEvent) => {
      const items = opciones(menuRef.current);
      if (!items.length) return;
      const idx = items.indexOf(document.activeElement as HTMLElement);
      const ir = (i: number) => { e.preventDefault(); items[(i + items.length) % items.length]?.focus(); };
      switch (e.key) {
        case 'ArrowDown': ir(idx + 1); break;
        case 'ArrowUp': ir(idx - 1); break;
        case 'Home': ir(0); break;
        case 'End': ir(items.length - 1); break;
        case 'Escape': e.preventDefault(); cerrar(); boton?.focus(); break;
        case 'Tab': cerrar(); break;
        default: return;
      }
    };
    document.addEventListener('keydown', alTeclear);
    return () => { window.clearTimeout(primero); document.removeEventListener('keydown', alTeclear); };
  }, [abierto, cerrar, menuRef, cajaRef]);
}
