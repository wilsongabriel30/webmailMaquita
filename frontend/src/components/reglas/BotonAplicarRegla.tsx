import { useState } from 'react';
import { aplicarConAviso } from '../../lib/reglas/aplicarConAviso';
import type { Regla } from '../../lib/reglas/tipos';

/* Botón «Aplicar ahora» de una regla ya guardada: la pasa por los correos que ya están en la
   Bandeja de entrada (Ajustes › Reglas de correo). */

export function BotonAplicarRegla({ regla, className }: { regla: Regla; className?: string }) {
  const [ocupado, setOcupado] = useState(false);
  const pulsar = async () => {
    if (!window.confirm(`¿Aplicar ahora la regla «${regla.name}» a los correos que ya están en la Bandeja de entrada?`)) return;
    setOcupado(true);
    try { await aplicarConAviso(regla); } finally { setOcupado(false); }
  };
  return (
    <button type="button" onClick={pulsar} disabled={ocupado} title="Aplicar la regla a los correos que ya están en la Bandeja de entrada"
      className={className || 'text-[13px] text-[#0078d4] hover:bg-[#deecf9] px-2 py-1 rounded disabled:opacity-60'}>
      {ocupado ? 'Aplicando…' : 'Aplicar ahora'}
    </button>
  );
}
