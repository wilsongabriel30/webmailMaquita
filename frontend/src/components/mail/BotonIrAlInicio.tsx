/** «Ir al inicio»: aparece cuando la lista está muy abajo y la devuelve arriba (11/11/2026). */
import React from 'react';

export function BotonIrAlInicio({ contenedor }: { contenedor: React.RefObject<HTMLDivElement | null> }) {
  const [visible, setVisible] = React.useState(false);
  React.useEffect(() => {
    const el = contenedor.current;
    if (!el) return;
    const alDesplazar = () => setVisible(el.scrollTop > 800);
    el.addEventListener('scroll', alDesplazar, { passive: true });
    alDesplazar();
    return () => el.removeEventListener('scroll', alDesplazar);
  }, [contenedor]);
  if (!visible) return null;
  return (
    <div className="sticky top-2 z-10 h-0 flex justify-end pr-4 pointer-events-none">
      <button type="button" title="Volver al inicio de la lista"
        onClick={() => contenedor.current?.scrollTo({ top: 0, behavior: 'smooth' })}
        className="pointer-events-auto h-7 px-3 rounded-full bg-white border border-[#c8c6c4] shadow text-[12px] text-[#0078d4] hover:bg-[#f3f2f1]">
        ↑ Ir al inicio
      </button>
    </div>
  );
}
