import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { TablaOrdenes } from "./TablaOrdenes";
import { TablaRegistro } from "./TablaRegistro";
import { Asiento, Orden, fechaHora } from "./tipos";

// Ficha de un equipo enrolado: datos del enrolamiento, último inventario que devolvió el agente,
// sus órdenes y su registro. Desde aquí se le emite una orden o se le retira de la flota.

interface Equipo {
  equipo_id: string; machine_guid: string; nombre: string; etiqueta: string; estado: string; windows: string; version_app: string;
  inventario?: Record<string, unknown> | null; inventario_en?: string; enrolado_en: string; reenrolado_en?: string;
  ultimo_sondeo?: string; ultima_ip: string; retirado_en?: string; retirado_por?: string; motivo_retiro?: string;
}

interface Props { id: string; onCerrar: () => void; onOrden: (ids: string[]) => void; onCambio: () => void }

export function FichaEquipo({ id, onCerrar, onOrden, onCambio }: Props) {
  const [d, setD] = useState<{ equipo: Equipo; ordenes: Orden[]; registro: Asiento[] } | null>(null);
  const [error, setError] = useState("");
  const cargar = () => api.get<{ equipo: Equipo; ordenes: Orden[]; registro: Asiento[] }>(`/flota/equipos/${id}`).then(setD).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, [id]);

  const retirar = async () => {
    const motivo = prompt("Motivo del retiro (deja de recibir órdenes; para volver a gestionarlo hará falta un código nuevo):");
    if (!motivo) return;
    try { await api.post(`/flota/equipos/${id}/retirar`, { motivo }); cargar(); onCambio(); } catch (e: any) { setError(e.message); }
  };

  if (!d) return <div className="text-sm text-ms-gray-60">{error || "Cargando…"}</div>;
  const e = d.equipo;
  const datos: [string, string][] = [
    ["Etiqueta", e.etiqueta || "—"], ["Estado", e.estado === "activo" ? "Gestionado" : `Retirado ${fechaHora(e.retirado_en)} por ${e.retirado_por}: ${e.motivo_retiro}`],
    ["equipo_id", e.equipo_id], ["MachineGuid", e.machine_guid], ["Windows", e.windows || "—"], ["App de escritorio", e.version_app || "—"],
    ["Enrolado", `${fechaHora(e.enrolado_en)}${e.reenrolado_en ? ` · reenrolado ${fechaHora(e.reenrolado_en)}` : ""}`],
    ["Último sondeo del agente", `${fechaHora(e.ultimo_sondeo)} desde ${e.ultima_ip || "—"}`], ["Inventario", fechaHora(e.inventario_en)],
  ];
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <button onClick={onCerrar} className="text-sm text-ms-blue hover:underline">← Volver</button>
        <h2 className="text-lg font-semibold">{e.nombre}</h2>
        {e.estado === "activo" && <>
          <button onClick={() => onOrden([e.equipo_id])} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm">Emitir orden</button>
          <button onClick={retirar} className="px-3 py-1.5 border border-red-300 text-red-700 rounded text-sm">Retirar de la flota</button></>}
      </div>
      {error && <div className="text-sm px-3 py-2 rounded bg-red-50 text-red-700">{error}</div>}
      <div className="bg-white rounded-lg border border-ms-gray-30 p-4 grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1 text-sm">
        {datos.map(([k, v]) => <div key={k}><span className="text-xs text-ms-gray-60">{k}: </span><span className="break-all">{v}</span></div>)}
      </div>
      {e.inventario && <details className="bg-white rounded-lg border border-ms-gray-30 p-4"><summary className="text-sm font-semibold cursor-pointer">Último inventario del agente</summary>
        <pre className="text-xs mt-2 whitespace-pre-wrap max-h-96 overflow-auto">{JSON.stringify(e.inventario, null, 2)}</pre></details>}
      <h3 className="text-sm font-semibold">Órdenes</h3>
      <TablaOrdenes ordenes={d.ordenes} onCambio={cargar} />
      <h3 className="text-sm font-semibold">Registro</h3>
      <TablaRegistro registro={d.registro} />
    </div>
  );
}
