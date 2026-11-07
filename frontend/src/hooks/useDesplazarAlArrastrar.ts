// Desplazamiento automático al ARRASTRAR (06/11/2026, reporte de Karen Armas: «no me deja bajar en
// el listado de carpetas para mover correos»). Al arrastrar un correo (o una carpeta) cerca del borde
// superior o inferior de un contenedor con scroll, el contenedor se desplaza solo, más rápido cuanto
// más cerca del borde. No depende del navegador ni de la app de Windows (WebView2), que no siempre lo hacen.
import { useEffect, type RefObject } from 'react';

const ZONA = 56;          // px desde el borde (por dentro) donde empieza a desplazarse
const FUERA = 70;         // px por fuera del borde que también cuentan (p. ej. sobre las etiquetas de abajo)
const MAX_VEL = 18;       // px por cuadro a máxima velocidad
const SIN_EVENTOS_MS = 160;

export function useDesplazarAlArrastrar(ref: RefObject<HTMLElement | null>) {
  useEffect(() => {
    let vel = 0;
    let cuadro = 0;
    let ultimo = 0;

    const parar = () => { vel = 0; if (cuadro) { cancelAnimationFrame(cuadro); cuadro = 0; } };
    const paso = () => {
      const el = ref.current;
      if (!el || vel === 0 || performance.now() - ultimo > SIN_EVENTOS_MS) { parar(); return; }
      el.scrollTop += vel;
      cuadro = requestAnimationFrame(paso);
    };

    const alArrastrar = (e: DragEvent) => {
      const el = ref.current;
      if (!el || el.scrollHeight <= el.clientHeight) return;
      const r = el.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right) { vel = 0; return; }
      const y = e.clientY;
      let v = 0;
      if (y >= r.top - FUERA && y < r.top + ZONA) v = -Math.ceil(MAX_VEL * Math.min(1, (r.top + ZONA - y) / ZONA));
      else if (y > r.bottom - ZONA && y <= r.bottom + FUERA) v = Math.ceil(MAX_VEL * Math.min(1, (y - (r.bottom - ZONA)) / ZONA));
      vel = v;
      ultimo = performance.now();
      if (v !== 0 && !cuadro) cuadro = requestAnimationFrame(paso);
    };

    document.addEventListener('dragover', alArrastrar, true);
    document.addEventListener('drop', parar, true);
    document.addEventListener('dragend', parar, true);
    return () => {
      document.removeEventListener('dragover', alArrastrar, true);
      document.removeEventListener('drop', parar, true);
      document.removeEventListener('dragend', parar, true);
      parar();
    };
  }, [ref]);
}
