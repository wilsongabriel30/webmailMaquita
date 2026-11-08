/**
 * Mientras el asistente responde (08/11/2026): cuenta los segundos, avisa si tarda y deja cancelar.
 * Antes solo decía «Revisando tus correos…» y, con 20-35 s de espera, la gente recargaba la página
 * sin saber que la respuesta venía en camino.
 */
import { useEffect, useState } from 'react';

export function EsperaRespuesta({ onCancelar }: { onCancelar: () => void }) {
  const [segundos, setSegundos] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => setSegundos((s) => s + 1), 1000);
    return () => window.clearInterval(t);
  }, []);
  return (
    <div className="flex items-center gap-2 text-xs text-[#605e5c]" role="status">
      <span className="inline-block w-3 h-3 rounded-full border-2 border-[#0078d4] border-t-transparent animate-spin" aria-hidden="true" />
      <span className="flex-1">
        {segundos < 8 ? 'Revisando tus correos…' : `La IA sigue trabajando (${segundos} s). Puede tardar hasta un minuto; no hace falta recargar.`}
      </span>
      <button type="button" onClick={onCancelar} className="text-[11px] text-[#0078d4] hover:underline shrink-0">Cancelar</button>
    </div>
  );
}
