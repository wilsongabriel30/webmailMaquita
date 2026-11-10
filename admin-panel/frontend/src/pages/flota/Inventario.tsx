import { useState } from "react";
import { COLOR, EquipoFlota, fechaHora } from "./tipos";

// Inventario: equipos enrolados (agente) + lo que ya reporta la telemetría de Teams Maquita. Los equipos que
// reportan pero no están enrolados aparecen al final, en gris, para darlos de alta con un código.

interface Props { equipos: EquipoFlota[]; onAbrir: (id: string) => void; onOrden: (ids: string[]) => void }

export function Inventario({ equipos, onAbrir, onOrden }: Props) {
  const [sel, setSel] = useState<string[]>([]);
  const [filtro, setFiltro] = useState("");
  const vis = equipos.filter((e) => !filtro || `${e.nombre} ${e.usuario || ""} ${e.etiqueta || ""}`.toLowerCase().includes(filtro.toLowerCase()));
  const activos = vis.filter((e) => e.enrolado && e.estado === "activo").map((e) => e.equipo_id as string);
  const marcar = (id: string) => setSel(sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]);

  return (
    <div className="bg-white rounded-lg border border-ms-gray-30 overflow-x-auto">
      <div className="px-4 py-2 border-b border-ms-gray-20 flex flex-wrap items-center gap-3 text-xs">
        <input value={filtro} onChange={(e) => setFiltro(e.target.value)} placeholder="Buscar equipo, persona o etiqueta" className="px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded w-64" />
        <span className="text-ms-gray-60">{sel.length} seleccionados</span>
        <button disabled={!sel.length} onClick={() => onOrden(sel)} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-40">Emitir orden a los seleccionados</button>
      </div>
      <table className="w-full text-sm">
        <thead><tr className="bg-ms-gray-10">
          <th className="px-3 py-2.5"><input type="checkbox" checked={activos.length > 0 && activos.every((i) => sel.includes(i))}
            onChange={(e) => setSel(e.target.checked ? activos : [])} /></th>
          {["Equipo", "Persona (app)", "Agente", "App", "Teams", "Windows", "IP", "SSH soporte", "Órdenes vivas", "Estado"].map((h) =>
            <th key={h} className="text-left px-3 py-2.5 font-medium text-ms-gray-90 text-xs">{h}</th>)}
        </tr></thead>
        <tbody>
          {vis.map((e) => {
            const gestionable = e.enrolado && e.estado === "activo";
            return <tr key={e.equipo_id || e.nombre} className={`border-t border-ms-gray-20 ${e.enrolado ? "" : "text-ms-gray-60"}`}>
              <td className="px-3 py-2">{gestionable && <input type="checkbox" checked={sel.includes(e.equipo_id as string)} onChange={() => marcar(e.equipo_id as string)} />}</td>
              <td className="px-3 py-2">{e.enrolado ? <button onClick={() => onAbrir(e.equipo_id as string)} className="text-ms-blue hover:underline font-medium">{e.nombre}</button> : e.nombre}
                {e.etiqueta && <div className="text-xs text-ms-gray-60">{e.etiqueta}</div>}</td>
              <td className="px-3 py-2 text-xs">{e.usuario || "—"}</td>
              <td className="px-3 py-2 text-xs whitespace-nowrap">{e.enrolado ? <><span className={`inline-block w-2 h-2 rounded-full mr-1 ${COLOR[e.semaforo_agente]}`} />{fechaHora(e.ultimo_sondeo)}</> : "sin enrolar"}</td>
              <td className="px-3 py-2 text-xs whitespace-nowrap"><span className={`inline-block w-2 h-2 rounded-full mr-1 ${COLOR[e.semaforo_app]}`} />{fechaHora(e.visto_en)}</td>
              <td className="px-3 py-2 text-xs">{e.version_app || e.version_tel || "—"}</td>
              <td className="px-3 py-2 text-xs">{(e.windows || e.windows_tel || "—").replace("Microsoft Windows NT ", "NT ")}</td>
              <td className="px-3 py-2 text-xs">{e.ultima_ip || e.ip_tel || "—"}</td>
              <td className="px-3 py-2 text-xs" title={e.ssh_detalle || ""}>{e.ssh}{e.ssh_en && <div className="text-ms-gray-60">{fechaHora(e.ssh_en)}</div>}</td>
              <td className="px-3 py-2 text-xs">{e.enrolado ? e.ordenes_vivas : "—"}</td>
              <td className="px-3 py-2 text-xs">{!e.enrolado ? "Pendiente de alta" : e.estado === "activo" ? "Gestionado" : `Retirado ${fechaHora(e.retirado_en)}`}</td>
            </tr>;
          })}
          {!vis.length && <tr><td colSpan={11} className="px-4 py-6 text-center text-ms-gray-60">Sin equipos.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
