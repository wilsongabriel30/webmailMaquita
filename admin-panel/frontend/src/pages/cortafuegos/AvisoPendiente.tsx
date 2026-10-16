import { useEffect, useState } from "react";

/* Cuenta atrás tras aplicar: sin confirmar en 60 s, el servidor vuelve solo a la configuración anterior. */
export function AvisoPendiente({ hasta, onConfirmar, onDeshacer }: { hasta: number; onConfirmar: () => void; onDeshacer: () => void }) {
  const [quedan, setQuedan] = useState(Math.max(0, hasta - Math.floor(Date.now() / 1000)));
  useEffect(() => {
    const t = setInterval(() => setQuedan(Math.max(0, hasta - Math.floor(Date.now() / 1000))), 1000);
    return () => clearInterval(t);
  }, [hasta]);
  return (
    <div className="bg-amber-50 border border-amber-300 rounded p-4 flex flex-wrap items-center gap-3">
      <div className="flex-1 min-w-[16rem] text-sm text-ms-gray-130">
        <strong>Cambios aplicados a prueba.</strong> Si todo funciona (puede seguir usando el panel), confírmelos.
        Si no se confirman, se deshacen solos en <strong>{quedan} s</strong>.
      </div>
      <button onClick={onConfirmar} className="px-4 py-2 bg-ms-blue text-white rounded text-sm">Confirmar</button>
      <button onClick={onDeshacer} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Deshacer ahora</button>
    </div>
  );
}
