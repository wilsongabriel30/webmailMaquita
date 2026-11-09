import { Fragment, useState } from "react";
import { api } from "../../api/client";
import { Orden, estadoOrden, fechaHora } from "./tipos";

// Tabla de órdenes (todas o las de un equipo). «Anular» deja de entregarla; si el agente ya la había
// recibido, su resultado posterior queda en el registro como rechazado por el servidor (409).

interface Props { ordenes: Orden[]; conEquipo?: boolean; onCambio: () => void }

const COLORES: Record<string, string> = { ok: "text-green-700", error: "text-red-700", rechazada: "text-red-700", anulada: "text-ms-gray-60" };

export function TablaOrdenes({ ordenes, conEquipo, onCambio }: Props) {
  const [abierta, setAbierta] = useState<string | null>(null);
  const [error, setError] = useState("");
  const anular = async (o: Orden) => {
    if (!confirm(`¿Anular la orden «${o.tipo}»${o.nombre ? ` de ${o.nombre}` : ""}?`)) return;
    try { await api.del(`/flota/ordenes/${o.orden_id}`); onCambio(); } catch (e: any) { setError(e.message); }
  };
  return (
    <div className="bg-white rounded-lg border border-ms-gray-30 overflow-x-auto">
      {error && <div className="text-sm px-3 py-2 bg-red-50 text-red-700">{error}</div>}
      <table className="w-full text-sm">
        <thead><tr className="bg-ms-gray-10">{[...(conEquipo ? ["Equipo"] : []), "Orden", "Motivo", "Emitida", "Estado", "Entregas", "Resultado", ""].map((h) =>
          <th key={h} className="text-left px-3 py-2.5 font-medium text-ms-gray-90 text-xs">{h}</th>)}</tr></thead>
        <tbody>
          {ordenes.map((o) => <Fragment key={o.orden_id}>
            <tr className="border-t border-ms-gray-20">
              {conEquipo && <td className="px-3 py-2 font-medium">{o.nombre}</td>}
              <td className="px-3 py-2">{o.tipo}{Object.keys(o.parametros || {}).length > 0 && <span className="text-xs text-ms-gray-60"> {JSON.stringify(o.parametros)}</span>}</td>
              <td className="px-3 py-2 text-xs">{o.motivo}</td>
              <td className="px-3 py-2 text-xs whitespace-nowrap">{fechaHora(o.emitida_en)}<div className="text-ms-gray-60">{o.emitida_por}</div></td>
              <td className={`px-3 py-2 text-xs ${COLORES[o.estado] || ""}`}>{estadoOrden(o)}</td>
              <td className="px-3 py-2 text-xs">{o.entregas}</td>
              <td className="px-3 py-2 text-xs whitespace-nowrap">{fechaHora(o.resultado_en)}</td>
              <td className="px-3 py-2 text-right whitespace-nowrap text-xs">
                {o.registro && <button onClick={() => setAbierta(abierta === o.orden_id ? null : o.orden_id)} className="text-ms-blue hover:underline mr-3">Registro</button>}
                {["pendiente", "entregada", "recibida", "ejecutando"].includes(o.estado) && !o.caducada &&
                  <button onClick={() => anular(o)} className="text-ms-red hover:underline">Anular</button>}
              </td>
            </tr>
            {abierta === o.orden_id && <tr><td colSpan={conEquipo ? 8 : 7} className="px-3 pb-3">
              <pre className="text-xs bg-ms-gray-10 rounded p-2 whitespace-pre-wrap max-h-64 overflow-auto">{o.registro}</pre></td></tr>}
          </Fragment>)}
          {!ordenes.length && <tr><td colSpan={8} className="px-4 py-6 text-center text-ms-gray-60">Sin órdenes.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
