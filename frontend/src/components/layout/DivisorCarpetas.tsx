/**
 * Barra para ensanchar o estrechar el panel de carpetas (11/11/2026).
 *
 * Pedido de Gerencia de Agro: con nombres de carpeta largos no había forma de ver el nombre completo,
 * porque entre las carpetas y la lista no existía un borde arrastrable. Va pegada al borde derecho del
 * panel; el ancho se recuerda (mailStore.anchoCarpetas). Doble clic: vuelve al ancho normal.
 */
import React from 'react';
import { ANCHO_CARPETAS_NORMAL, useMailStore } from '../../store/mailStore';

export function DivisorCarpetas() {
  const alPulsar = (e: React.MouseEvent) => {
    e.preventDefault();
    const x0 = e.clientX;
    const ancho0 = useMailStore.getState().anchoCarpetas;
    const mover = (ev: MouseEvent) => useMailStore.getState().setAnchoCarpetas(ancho0 + (ev.clientX - x0));
    const soltar = () => {
      window.removeEventListener('mousemove', mover);
      window.removeEventListener('mouseup', soltar);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('mousemove', mover);
    window.addEventListener('mouseup', soltar);
  };
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Ancho del panel de carpetas"
      title="Arrastre para ajustar el ancho de las carpetas (doble clic: ancho normal)"
      onMouseDown={alPulsar}
      onDoubleClick={() => useMailStore.getState().setAnchoCarpetas(ANCHO_CARPETAS_NORMAL)}
      className="absolute top-0 right-0 bottom-0 w-[6px] cursor-col-resize bg-transparent hover:bg-[#0078d4]/40 active:bg-[#0078d4]/60 transition-colors z-30 max-md:hidden"
    />
  );
}
