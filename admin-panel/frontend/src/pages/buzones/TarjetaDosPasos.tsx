import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useResumenDosPasos } from "./DosPasos";

// Tarjeta del tablero inicial: cuántas cuentas tienen la verificación en dos pasos activa.
// Lleva a la lista de buzones ya filtrada por las que aún no la tienen.
const fecha = (iso: string) => iso.slice(0, 10).split("-").reverse().join("/");

export function TarjetaDosPasos() {
  const { resumen, recargar } = useResumenDosPasos();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { recargar(); }, []);
  if (!resumen || !resumen.cuentas_activas) return null;
  const porcentaje = Math.round((resumen.con_dos_pasos / resumen.cuentas_activas) * 100);
  return (
    <Link to="/mailboxes?dos_pasos=sin"
      title="Ver los buzones que todavía no tienen la verificación en dos pasos"
      className="block bg-white rounded-lg shadow-sm border border-ms-gray-30 p-4 hover:border-ms-blue transition-colors">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="text-sm font-semibold text-ms-gray-130">Verificación en dos pasos</h3>
        <span className="text-xs text-ms-blue">Ver quiénes faltan →</span>
      </div>
      <div className="mt-2 flex flex-wrap items-baseline gap-x-2">
        <span className="text-2xl font-semibold text-ms-gray-130">{resumen.con_dos_pasos}</span>
        <span className="text-sm text-ms-gray-90">de {resumen.cuentas_activas} cuentas activas la tienen activa ({porcentaje} %)</span>
      </div>
      <div className="mt-2 h-2 rounded bg-ms-gray-20 overflow-hidden" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={porcentaje}
        aria-label="Cuentas con la verificación en dos pasos activa">
        <div className="h-full bg-ms-green" style={{ width: `${Math.max(porcentaje, 1)}%` }} />
      </div>
      <div className="mt-2 text-xs text-ms-gray-90">
        <span>{resumen.sin_dos_pasos} cuentas aún sin activarla</span>
        {resumen.obligadas_sin_activar > 0 && (
          <span className="text-ms-red"> · {resumen.obligadas_sin_activar} de {resumen.obligadas} cuentas obligadas sin activarla</span>
        )}
        {resumen.exigida_a_todas && (
          <span> · {resumen.fecha_limite ? `Obligatoria para todas desde el ${fecha(resumen.fecha_limite)}` : "Obligatoria para todas las cuentas"}</span>
        )}
      </div>
    </Link>
  );
}
