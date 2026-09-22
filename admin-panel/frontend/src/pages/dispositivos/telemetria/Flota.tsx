import { useEffect, useMemo, useState } from "react";
import { api } from "../../../api/client";
import { haceCuanto } from "../tipos";
import { COLOR_SEMAFORO, EquipoFlota, Flota as FlotaDatos, NOMBRE_ALERTA, descargar, gb } from "./tipos";
import { Anclas } from "./Anclas";

// Vista de flota: una fila por equipo con semáforo de último contacto, batería, almacenamiento, red,
// versiones (marcando las atrasadas frente a la publicada), administración, Play Protect, eventos rojos
// de 7 días, urgentes sin acuse y alertas abiertas. Ordenable, filtrable y exportable a CSV.

type Orden = keyof EquipoFlota | "almacenamiento_pct";
const COLUMNAS: { k: Orden; t: string }[] = [
  { k: "nombre", t: "Equipo" }, { k: "custodio_nombre", t: "Custodio" }, { k: "ultimo_contacto", t: "Último contacto" }, { k: "bateria", t: "Batería" },
  { k: "almacenamiento_pct", t: "Almacenamiento libre" }, { k: "red", t: "Red" }, { k: "version_app", t: "App" }, { k: "android", t: "Android" },
  { k: "modo", t: "Modo" }, { k: "admin_activo", t: "Admin." }, { k: "play_protect", t: "Play Protect" }, { k: "eventos_rojos_7d", t: "Eventos 7 d" },
  { k: "urgentes_sin_acuse", t: "Sin acuse" }, { k: "alertas_abiertas", t: "Alertas" },
];
const SI_NO = (v?: boolean | null, malo = "NO") => v == null ? <span className="text-ms-gray-60">—</span> : v ? "sí" : <span className="text-red-600 font-medium">{malo}</span>;

export function Flota({ onAbrir }: { onAbrir: (id: number) => void }) {
  const [d, setD] = useState<FlotaDatos | null>(null);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [sede, setSede] = useState("");
  const [estado, setEstado] = useState("");
  const [orden, setOrden] = useState<{ k: Orden; asc: boolean }>({ k: "ultimo_contacto", asc: false });

  const cargar = () => api.get<FlotaDatos>("/dispositivos/telemetria/flota").then(setD).catch((e) => setError(e.message));
  useEffect(() => { cargar(); const t = setInterval(cargar, 60000); return () => clearInterval(t); }, []);

  const sedes = useMemo(() => Array.from(new Set((d?.equipos || []).map((e) => e.sede).filter(Boolean))) as string[], [d]);
  const filas = useMemo(() => {
    const t = q.trim().toLowerCase();
    const lista = (d?.equipos || []).filter((e) =>
      (!sede || e.sede === sede) && (!estado || (estado === "alertas" ? e.alertas_abiertas > 0 : e.semaforo === estado)) &&
      (!t || [e.nombre, e.modelo, e.fabricante, e.custodio_nombre, e.custodio_email, e.sede, e.centro_costo].some((v) => (v || "").toLowerCase().includes(t))));
    const val = (e: EquipoFlota) => { const v = e[orden.k as keyof EquipoFlota]; return v == null ? (orden.asc ? Infinity : -Infinity) : typeof v === "boolean" ? Number(v) : v; };
    return lista.sort((a, b) => { const x = val(a), y = val(b); return (x < y ? -1 : x > y ? 1 : 0) * (orden.asc ? 1 : -1); });
  }, [d, q, sede, estado, orden]);

  const exportar = async () => { try { await descargar("/dispositivos/telemetria/flota.csv", `telemetria-telefonos-${new Date().toISOString().slice(0, 10)}.csv`); } catch (e: any) { setError(e.message); } };
  const clic = (k: Orden) => setOrden((o) => ({ k, asc: o.k === k ? !o.asc : true }));

  if (!d) return <div className="p-6 text-sm text-ms-gray-60">{error || "Cargando…"}</div>;
  const T = d.totales;
  return (
    <div className="space-y-4">
      {error && <div className="text-sm px-3 py-2 rounded bg-red-50 text-red-700">{error}</div>}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {([["Equipos", T.equipos, false], ["Reportando hoy", T.reportando_hoy, false], ["En rojo (sin reportar > 24 h)", T.rojo, T.rojo > 0], ["Con alertas abiertas", T.con_alertas, T.con_alertas > 0]] as [string, number, boolean][]).map(([t, n, mal]) => (
          <div key={t} className={`rounded-lg border p-3 ${mal ? "bg-red-50 border-red-200" : "bg-white border-ms-gray-30"}`}><div className="text-2xl font-semibold">{n}</div><div className="text-xs text-ms-gray-60">{t}</div></div>))}
      </div>
      <div className="bg-white rounded-lg border border-ms-gray-30">
        <div className="p-3 border-b border-ms-gray-30 flex flex-wrap items-center gap-2 text-sm">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar equipo, custodio, modelo, sede…" className="flex-1 min-w-[200px] max-w-md px-3 py-1.5 border border-ms-gray-40 rounded" />
          <select value={sede} onChange={(e) => setSede(e.target.value)} className="px-2 py-1.5 border border-ms-gray-40 rounded"><option value="">Todas las sedes</option>{sedes.map((s) => <option key={s} value={s}>{s}</option>)}</select>
          <select value={estado} onChange={(e) => setEstado(e.target.value)} className="px-2 py-1.5 border border-ms-gray-40 rounded">
            <option value="">Todos los estados</option><option value="verde">Verde (&lt; 1 h)</option><option value="amarillo">Amarillo (&lt; 24 h)</option><option value="rojo">Rojo (&gt; 24 h o nunca)</option><option value="alertas">Con alertas abiertas</option></select>
          <span className="text-xs text-ms-gray-60">App publicada: <strong>{d.publicada.versionName || "?"}</strong>{d.publicada.fecha ? ` (${d.publicada.fecha})` : ""}</span>
          <button onClick={exportar} className="ml-auto px-3 py-1.5 border border-ms-gray-40 rounded hover:bg-ms-gray-10" title="Queda en la auditoría">Exportar CSV</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="bg-ms-gray-10">{COLUMNAS.map((c) => <th key={c.k} onClick={() => clic(c.k)} className="text-left px-3 py-2.5 font-medium text-ms-gray-90 text-xs cursor-pointer select-none whitespace-nowrap">{c.t}{orden.k === c.k ? (orden.asc ? " ▲" : " ▼") : ""}</th>)}</tr></thead>
            <tbody>
              {filas.map((e) => {
                const hc = haceCuanto(e.ultimo_contacto);
                return <tr key={e.id} onClick={() => onAbrir(e.id)} className="border-t border-ms-gray-20 hover:bg-ms-gray-10 cursor-pointer">
                  <td className="px-3 py-2"><div className="font-medium text-ms-gray-130">{e.nombre || `${e.fabricante || ""} ${e.modelo || "Equipo"}`.trim()}</div><div className="text-xs text-ms-gray-60">{e.fabricante} {e.modelo}{e.sede ? ` · ${e.sede}` : ""}{e.estado !== "activo" ? ` · ${e.estado}` : ""}</div></td>
                  <td className="px-3 py-2"><div>{e.custodio_nombre || "—"}</div><div className="text-xs text-ms-gray-60">{e.custodio_email}</div></td>
                  <td className="px-3 py-2 whitespace-nowrap"><span className={`inline-block w-2.5 h-2.5 rounded-full mr-1.5 ${COLOR_SEMAFORO[e.semaforo]}`} />{hc.texto}</td>
                  <td className="px-3 py-2">{e.bateria != null ? <span className={e.bateria < 15 && !e.cargando ? "text-red-600 font-medium" : ""}>{e.bateria}%{e.cargando ? " ⚡" : ""}</span> : "—"}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{e.almacenamiento_pct != null ? <span className={e.almacenamiento_pct < 10 ? "text-red-600 font-medium" : ""}>{e.almacenamiento_pct}% · {gb(e.almacenamiento_libre)}</span> : "—"}</td>
                  <td className="px-3 py-2">{e.red || "—"}{e.wifi_ssid && (e.red || "").toLowerCase().includes("wifi") && <div className="text-xs text-ms-gray-60">«{e.wifi_ssid}»</div>}{e.ancla_sede && <div className="text-xs text-blue-700" title="Reporta desde la red de esa sede (ancla de red)">en {e.ancla_sede}</div>}</td>
                  <td className="px-3 py-2">{e.version_app ? <span className={e.version_atrasada ? "text-amber-700 font-medium" : ""} title={e.version_atrasada ? `Atrasada: la publicada es ${d.publicada.versionName}` : ""}>{e.version_app}{e.version_atrasada ? " ↓" : ""}</span> : "—"}</td>
                  <td className="px-3 py-2">{e.android || "—"}</td>
                  <td className="px-3 py-2 text-xs">{e.modo === "propietario" ? "Completo" : "Limitado"}</td>
                  <td className="px-3 py-2">{SI_NO(e.admin_activo)}</td>
                  <td className="px-3 py-2">{SI_NO(e.play_protect, "APAGADO")}</td>
                  <td className="px-3 py-2">{e.eventos_rojos_7d ? <span className="text-red-600 font-medium">{e.eventos_rojos_7d}</span> : 0}</td>
                  <td className="px-3 py-2">{e.urgentes_sin_acuse ? <span className="text-red-600 font-medium">{e.urgentes_sin_acuse}</span> : 0}</td>
                  <td className="px-3 py-2 text-xs">{e.alertas?.length ? e.alertas.map((a) => <div key={a.tipo} className="text-red-700">{NOMBRE_ALERTA[a.tipo] || a.tipo}</div>) : <span className="text-ms-gray-60">ninguna</span>}</td>
                </tr>;
              })}
              {!filas.length && <tr><td colSpan={COLUMNAS.length} className="px-4 py-8 text-center text-ms-gray-60">Ningún equipo coincide.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      <Anclas />
      <p className="text-xs text-ms-gray-60">Semáforo: verde reportó hace menos de 1 h · amarillo menos de 24 h · rojo más de 24 h o nunca. Telemetría del equipo, no de la persona: aquí no hay contenido, apps de uso, navegación ni ubicación.</p>
    </div>
  );
}
