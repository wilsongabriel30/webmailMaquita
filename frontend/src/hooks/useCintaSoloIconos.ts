/**
 * Cinta en ventanas angostas (pedido de Dirección, 19/11/2026).
 *
 * Al achicar la ventana, la cinta no debe perder acciones: cuando sus botones ya no caben con
 * el nombre debajo, se quedan solo los iconos (el nombre sigue saliendo al pasar el ratón), que
 * es lo que hace el correo de escritorio. Al volver a haber sitio, regresan los nombres.
 *
 * Se mide el propio contenedor de la cinta: si desborda con los nombres, se anota el ancho que
 * necesitaría y se pasa a «solo iconos»; se vuelve atrás cuando el contenedor alcanza ese ancho.
 * `clave` cambia cuando cambia lo que se dibuja (pestaña, cinta contraída…) y reinicia la medida.
 */
import { useEffect, useRef, useState, type RefObject } from 'react';

export function useCintaSoloIconos(ref: RefObject<HTMLElement | null>, clave: string): boolean {
  const [solo, setSolo] = useState(false);
  const necesario = useRef(0);
  const claveMedida = useRef(clave);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (claveMedida.current !== clave) {
      claveMedida.current = clave;
      necesario.current = 0;
      if (solo) {
        // eslint-disable-next-line react-hooks/set-state-in-effect -- otra pestaña: se vuelve a medir con los nombres
        setSolo(false);
        return;
      }
    }
    const medir = () => {
      if (!solo) {
        if (el.scrollWidth > el.clientWidth + 2) {
          necesario.current = el.scrollWidth;
          setSolo(true);
        }
      } else if (necesario.current > 0 && el.clientWidth >= necesario.current) {
        setSolo(false);
      }
    };
    medir();
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', medir);
      return () => window.removeEventListener('resize', medir);
    }
    const observador = new ResizeObserver(medir);
    observador.observe(el);
    return () => observador.disconnect();
  }, [ref, clave, solo]);

  return solo;
}
