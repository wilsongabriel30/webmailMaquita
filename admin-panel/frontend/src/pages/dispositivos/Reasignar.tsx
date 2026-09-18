import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { Equipo, fechaHora } from "./tipos";

interface Tramo { id: number; custodio_nombre?: string; custodio_email?: string; centro_costo?: string; sede?: string; desde: string; hasta?: string; asignado_por: string; motivo?: string }

/** Reasignar el equipo a otra persona (jefe → subordinado → técnico) y ver quién lo tuvo. */
export function Reasignar({ equipo, onCambio }: { equipo: Equipo; onCambio: () => void }) {
  const [hist, setHist] = useState<Tramo[]>([]);
  const [abrir, setAbrir] = useState(false);
  const [f, setF] = useState({ custodio_nombre: "", custodio_email: "", centro_costo: equipo.centro_costo || "", sede: equipo.sede || "", motivo: "", respaldo_cierre: true });
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null);

  const cargar = () => api.get<{ custodia: Tramo[] }>(`/dispositivos/equipos/${equipo.id}/custodia`).then((r) => setHist(r.custodia)).catch(() => {});
  useEffect(() => { cargar(); }, [equipo.id]);

  const reasignar = async () => {
    if (!f.custodio_nombre.trim() && !f.custodio_email.trim()) { setMsg({ ok: false, t: "Indique el nuevo custodio." }); return; }
    if (!f.motivo.trim()) { setMsg({ ok: false, t: "Indique el motivo." }); return; }
    try { const r = await api.post<{ respaldo_cierre_encolado: boolean }>(`/dispositivos/equipos/${equipo.id}/reasignar`, f);
      setMsg({ ok: true, t: r.respaldo_cierre_encolado ? "Reasignado. Se pidió el respaldo de cierre del custodio anterior." : "Reasignado." });
      setAbrir(false); setF({ ...f, custodio_nombre: "", custodio_email: "", motivo: "" }); cargar(); onCambio(); }
    catch (e: any) { setMsg({ ok: false, t: e.message }); }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold">Custodia y reasignación</h3>
        <button onClick={() => setAbrir(!abrir)} disabled={equipo.estado === "revocado"} className="text-xs text-ms-blue hover:underline disabled:opacity-40">{abrir ? "Cancelar" : "Reasignar a otra persona"}</button>
      </div>
      {msg && <div className={`text-sm px-3 py-2 mb-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>{msg.t}</div>}
      <div className="text-sm text-ms-gray-90 mb-2">Custodio actual: <strong>{equipo.custodio_nombre || equipo.custodio_email || "sin asignar"}</strong>{equipo.centro_costo ? ` · ${equipo.centro_costo}` : ""}</div>
      {abrir && <div className="bg-ms-gray-10 rounded p-3 mb-3 grid md:grid-cols-2 gap-2 text-sm">
        <label className="text-xs">Nuevo custodio (nombre)<input value={f.custodio_nombre} onChange={(e) => setF({ ...f, custodio_nombre: e.target.value })} className="mt-1 w-full px-2.5 py-1.5 border border-ms-gray-40 rounded" /></label>
        <label className="text-xs">Nuevo custodio (correo)<input type="email" value={f.custodio_email} onChange={(e) => setF({ ...f, custodio_email: e.target.value })} className="mt-1 w-full px-2.5 py-1.5 border border-ms-gray-40 rounded" /></label>
        <label className="text-xs">Centro de costo<input value={f.centro_costo} onChange={(e) => setF({ ...f, centro_costo: e.target.value })} className="mt-1 w-full px-2.5 py-1.5 border border-ms-gray-40 rounded" /></label>
        <label className="text-xs">Sede<input value={f.sede} onChange={(e) => setF({ ...f, sede: e.target.value })} className="mt-1 w-full px-2.5 py-1.5 border border-ms-gray-40 rounded" /></label>
        <label className="text-xs md:col-span-2">Motivo<input value={f.motivo} onChange={(e) => setF({ ...f, motivo: e.target.value })} placeholder="Ej: el jefe entrega su equipo anterior al asistente" className="mt-1 w-full px-2.5 py-1.5 border border-ms-gray-40 rounded" /></label>
        <label className="text-xs md:col-span-2 flex items-center gap-1.5"><input type="checkbox" checked={f.respaldo_cierre} onChange={(e) => setF({ ...f, respaldo_cierre: e.target.checked })} />Pedir el respaldo de cierre del custodio anterior antes de entregar</label>
        <div className="md:col-span-2"><button onClick={reasignar} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">Reasignar</button></div>
      </div>}
      {hist.length > 0 && <ol className="text-sm border-l-2 border-ms-gray-30 ml-1 pl-3 space-y-1.5">
        {hist.map((t) => <li key={t.id}>
          <span className="font-medium">{t.custodio_nombre || t.custodio_email || "sin asignar"}</span>
          <span className="text-xs text-ms-gray-60"> · {fechaHora(t.desde)} → {t.hasta ? fechaHora(t.hasta) : "actual"}{t.centro_costo ? ` · ${t.centro_costo}` : ""}{t.motivo ? ` · ${t.motivo}` : ""} · asignó {t.asignado_por}</span>
        </li>)}
      </ol>}
    </div>
  );
}
