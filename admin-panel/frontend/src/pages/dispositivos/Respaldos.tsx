import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { Equipo, fechaHora, gigas } from "./tipos";

interface Resp { id: number; tipo: string; estado: string; iniciado_en: string; cerrado_en?: string; archivos_total: number; bytes_total: number; archivos_nuevos: number; bytes_nuevos: number; faltantes: number; resumen: Record<string, { archivos: number; bytes: number }>; errores: string[] }
interface Rest { id: number; destino_id: number; origen_id: number; origen_nombre: string; origen_modelo?: string; destino_nombre: string; destino_modelo?: string; autorizado_por: string; motivo: string; caduca_en: string; anulada_en?: string }
interface Datos { respaldo_activo: boolean; cuota_respaldo_gb: number; respaldo_cierre_en?: string; usado_bytes: number; respaldos: Resp[]; restauraciones: Rest[] }
const CAT: Record<string, string> = { fotos: "Fotos", videos: "Videos", documentos: "Documentos", descargas: "Descargas", contactos: "Contactos", llamadas: "Llamadas", sms: "SMS", whatsapp: "WhatsApp", apps: "Lista de apps", ajustes: "Ajustes", otros: "Otros" };

/** Respaldos del equipo. El panel solo ve fechas, tamaños y totales: el contenido está cifrado. */
export function Respaldos({ equipo }: { equipo: Equipo }) {
  const [d, setD] = useState<Datos | null>(null);
  const [otros, setOtros] = useState<Equipo[]>([]);
  const [origen, setOrigen] = useState("");
  const [cuota, setCuota] = useState(64);
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null);

  const cargar = () => api.get<Datos>(`/dispositivos/equipos/${equipo.id}/respaldos`).then((r) => { setD(r); setCuota(r.cuota_respaldo_gb); }).catch((e) => setMsg({ ok: false, t: e.message }));
  useEffect(() => { cargar(); api.get<{ equipos: Equipo[] }>("/dispositivos/equipos").then((r) => setOtros(r.equipos.filter((x) => x.id !== equipo.id))).catch(() => {}); }, [equipo.id]);
  const fallo = (e: any) => setMsg({ ok: false, t: e.message });

  const pedir = async (tipo: "manual" | "cierre") => {
    const motivo = prompt(tipo === "cierre" ? "Respaldo de cierre (antes de reasignar o restablecer el equipo) — motivo:" : "Respaldar ahora — motivo:"); if (!motivo) return;
    try { await api.post(`/dispositivos/equipos/${equipo.id}/respaldar`, { tipo, motivo }); setMsg({ ok: true, t: "Pedido enviado: el teléfono empieza en su próximo reporte (con Wi-Fi)." }); } catch (e) { fallo(e); }
  };
  const guardar = async (activo: boolean) => { try { await api.put(`/dispositivos/equipos/${equipo.id}/respaldo-config`, { respaldo_activo: activo, cuota_respaldo_gb: cuota }); cargar(); } catch (e) { fallo(e); } };
  const autorizar = async () => {
    const motivo = prompt("Este equipo podrá descargar durante 72 horas los respaldos del equipo elegido. Motivo (queda en la auditoría):"); if (!motivo) return;
    try { await api.post(`/dispositivos/equipos/${equipo.id}/autorizar-restauracion`, { origen_id: Number(origen), motivo }); setOrigen(""); cargar(); setMsg({ ok: true, t: "Autorizado. En la app: Mi equipo → Restaurar." }); } catch (e) { fallo(e); }
  };
  const anular = async (id: number) => { try { await api.del(`/dispositivos/restauraciones/${id}`); cargar(); } catch (e) { fallo(e); } };

  if (!d) return null;
  const pct = Math.min(100, Math.round((d.usado_bytes / (d.cuota_respaldo_gb * 1073741824)) * 100));
  const ultimo = d.respaldos.find((r) => r.estado === "completo");

  return (
    <div>
      <h3 className="text-sm font-semibold mb-2">Respaldos</h3>
      {msg && <div className={`text-sm px-3 py-2 mb-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>{msg.t}</div>}
      <div className="bg-ms-gray-10 rounded p-3 text-sm space-y-2 mb-3">
        <div className="flex flex-wrap items-center gap-3">
          <span>Último completo: <strong>{ultimo ? fechaHora(ultimo.cerrado_en) : "ninguno"}</strong></span>
          <span>Respaldo de cierre: <strong>{d.respaldo_cierre_en ? fechaHora(d.respaldo_cierre_en) : "no hecho"}</strong></span>
          <span>Ocupa {gigas(d.usado_bytes)} de {d.cuota_respaldo_gb} GB ({pct}%)</span>
        </div>
        <div className="h-1.5 bg-white rounded overflow-hidden"><div className={`h-full ${pct > 90 ? "bg-red-500" : "bg-ms-blue"}`} style={{ width: `${pct}%` }} /></div>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={() => pedir("manual")} disabled={!d.respaldo_activo} className="px-3 py-1.5 text-sm rounded border border-ms-gray-40 bg-white hover:bg-ms-gray-10 disabled:opacity-40">Respaldar ahora</button>
          <button onClick={() => pedir("cierre")} disabled={!d.respaldo_activo} title="Hágalo antes de reasignar, restablecer o dar de baja el equipo" className="px-3 py-1.5 text-sm rounded border border-ms-gray-40 bg-white hover:bg-ms-gray-10 disabled:opacity-40">Pedir respaldo de cierre</button>
          <label className="text-xs ml-2">Cuota (GB) <input type="number" min={1} max={2048} value={cuota} onChange={(e) => setCuota(Number(e.target.value))} className="w-20 px-2 py-1 text-sm border border-ms-gray-40 rounded" /></label>
          <button onClick={() => guardar(d.respaldo_activo)} className="text-xs text-ms-blue hover:underline">Guardar cuota</button>
          <button onClick={() => guardar(!d.respaldo_activo)} className="text-xs text-ms-blue hover:underline">{d.respaldo_activo ? "Desactivar respaldos" : "Activar respaldos"}</button>
        </div>
      </div>

      <div className="overflow-x-auto border border-ms-gray-30 rounded mb-3">
        <table className="w-full text-sm">
          <thead><tr className="bg-ms-gray-10">{["Fecha", "Tipo", "Estado", "Archivos", "Tamaño", "Subido esta vez", "Contenido"].map((h) => <th key={h} className="text-left px-3 py-2 font-medium text-ms-gray-90 text-xs">{h}</th>)}</tr></thead>
          <tbody>
            {d.respaldos.map((r) => <tr key={r.id} className="border-t border-ms-gray-20 align-top">
              <td className="px-3 py-2 text-xs">{fechaHora(r.iniciado_en)}</td><td className="px-3 py-2 text-xs">{r.tipo}</td>
              <td className={`px-3 py-2 text-xs ${r.estado === "completo" ? "text-green-700" : r.estado === "abierto" ? "text-ms-gray-90" : "text-amber-700"}`}>{r.estado === "abierto" ? "en curso" : r.estado}{r.faltantes ? ` (faltan ${r.faltantes})` : ""}{r.errores?.length ? ` · ${r.errores.length} avisos` : ""}</td>
              <td className="px-3 py-2">{r.archivos_total.toLocaleString("es-EC")}</td><td className="px-3 py-2">{gigas(r.bytes_total)}</td>
              <td className="px-3 py-2 text-xs">{r.archivos_nuevos.toLocaleString("es-EC")} · {gigas(r.bytes_nuevos)}</td>
              <td className="px-3 py-2 text-xs text-ms-gray-90">{(Object.entries(r.resumen || {}) as [string, { archivos: number }][]).map(([k, v]) => `${CAT[k] || k}: ${v.archivos.toLocaleString("es-EC")}`).join(" · ")}</td>
            </tr>)}
            {!d.respaldos.length && <tr><td colSpan={7} className="px-3 py-5 text-center text-ms-gray-60">Este equipo aún no ha hecho ningún respaldo.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="text-sm">
        <div className="font-medium mb-1">Restaurar en este equipo los respaldos de otro <span className="font-normal text-xs text-ms-gray-60">(teléfono nuevo tras un robo, o reasignación)</span></div>
        <div className="flex flex-wrap items-center gap-2">
          <select value={origen} onChange={(e) => setOrigen(e.target.value)} className="px-2 py-1.5 text-sm border border-ms-gray-40 rounded min-w-64">
            <option value="">Elegir equipo de origen…</option>
            {otros.map((o) => <option key={o.id} value={o.id}>{o.nombre || o.modelo} — {o.custodio_nombre || "sin custodio"} ({o.estado})</option>)}
          </select>
          <button onClick={autorizar} disabled={!origen} className="px-3 py-1.5 text-sm bg-ms-blue text-white rounded hover:bg-ms-blue-dark disabled:opacity-50">Autorizar 72 horas</button>
        </div>
        <ul className="mt-2 space-y-1">{d.restauraciones.map((r) => {
          const vigente = !r.anulada_en && new Date(r.caduca_en) > new Date();
          return <li key={r.id} className="flex justify-between gap-2 text-xs">
            <span>{r.origen_nombre || r.origen_modelo} → {r.destino_nombre || r.destino_modelo} · {r.autorizado_por} · {r.motivo}</span>
            <span className="shrink-0">{vigente ? <>vigente hasta {fechaHora(r.caduca_en)} · <button onClick={() => anular(r.id)} className="text-ms-red hover:underline">anular</button></> : r.anulada_en ? "anulada" : "caducada"}</span></li>;
        })}</ul>
      </div>
    </div>
  );
}
