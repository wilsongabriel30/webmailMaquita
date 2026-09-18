import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { Equipo, fechaHora } from "./tipos";

interface App { paquete: string; nombre?: string; version?: string; instalador?: string; permisos: string[]; sistema: boolean; veredicto: string; motivo?: string; vista_en: string }
const COLOR: Record<string, string> = { bloqueada: "bg-red-50 text-red-700", sospechosa: "bg-amber-50 text-amber-800", ok: "text-ms-gray-90" };

/** Apps instaladas en el equipo, con las de riesgo primero. En control completo se pueden desinstalar. */
export function Apps({ equipo }: { equipo: Equipo }) {
  const [apps, setApps] = useState<App[]>([]);
  const [soloRiesgo, setSoloRiesgo] = useState(true);
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null);
  const completo = equipo.modo === "propietario";

  const cargar = () => api.get<{ apps: App[] }>(`/dispositivos/equipos/${equipo.id}/apps`).then((r) => setApps(r.apps)).catch((e) => setMsg({ ok: false, t: e.message }));
  useEffect(() => { cargar(); }, [equipo.id]);

  const accion = async (paquete: string, accion: "desinstalar" | "bloquear_app") => {
    const motivo = prompt(`${accion === "desinstalar" ? "Desinstalar" : "Bloquear"} «${paquete}» en el teléfono — motivo (queda en la auditoría):`); if (!motivo) return;
    try { await api.post(`/dispositivos/equipos/${equipo.id}/apps/${encodeURIComponent(paquete)}/comando`, { accion, motivo }); setMsg({ ok: true, t: "Enviado: se ejecuta en el próximo reporte del teléfono." }); }
    catch (e: any) { setMsg({ ok: false, t: e.message }); }
  };
  const visibles = soloRiesgo ? apps.filter((a) => a.veredicto !== "ok") : apps;
  const riesgo = apps.filter((a) => a.veredicto !== "ok").length;

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold">Aplicaciones {riesgo > 0 && <span className="text-red-700">· {riesgo} de riesgo</span>}</h3>
        <label className="text-xs flex items-center gap-1.5"><input type="checkbox" checked={soloRiesgo} onChange={(e) => setSoloRiesgo(e.target.checked)} />Solo las de riesgo</label>
      </div>
      {msg && <div className={`text-sm px-3 py-2 mb-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>{msg.t}</div>}
      {equipo.play_protect === false && <div className="text-sm px-3 py-2 mb-2 rounded bg-amber-50 text-amber-800">Play Protect está desactivado en este teléfono: pídale al custodio que lo active (Play Store → perfil → Play Protect).</div>}
      <div className="overflow-x-auto border border-ms-gray-30 rounded">
        <table className="w-full text-sm">
          <thead><tr className="bg-ms-gray-10">{["Aplicación", "Origen", "Motivo", "Vista", ""].map((h) => <th key={h} className="text-left px-3 py-2 font-medium text-ms-gray-90 text-xs">{h}</th>)}</tr></thead>
          <tbody>
            {visibles.map((a) => <tr key={a.paquete} className="border-t border-ms-gray-20 align-top">
              <td className="px-3 py-2"><span className={`px-1.5 py-0.5 rounded text-xs ${COLOR[a.veredicto] || ""}`}>{a.nombre || a.paquete}</span><div className="text-xs text-ms-gray-60">{a.paquete} {a.version}</div></td>
              <td className="px-3 py-2 text-xs">{a.instalador || "desconocido"}{a.sistema ? " · sistema" : ""}</td>
              <td className="px-3 py-2 text-xs text-ms-gray-90">{a.motivo || ""}</td>
              <td className="px-3 py-2 text-xs">{fechaHora(a.vista_en)}</td>
              <td className="px-3 py-2 text-right">{a.veredicto !== "ok" && completo && <div className="flex gap-2 justify-end">
                <button onClick={() => accion(a.paquete, "desinstalar")} className="text-xs text-ms-red hover:underline">Desinstalar</button></div>}</td>
            </tr>)}
            {!visibles.length && <tr><td colSpan={5} className="px-3 py-5 text-center text-ms-gray-60">{apps.length ? "Sin apps de riesgo." : "El teléfono aún no ha enviado su lista de apps."}</td></tr>}
          </tbody>
        </table>
      </div>
      {!completo && riesgo > 0 && <p className="text-xs text-ms-gray-60 mt-2">Equipo en modo limitado: al custodio le llega el aviso para desinstalar, pero no se puede quitar a distancia.</p>}
    </div>
  );
}
