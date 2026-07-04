import { useState, useEffect, Fragment } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface Entry { ts: string | null; source: string; actor: string; action: string; category: string; target: string | null; ip: string | null; risk: string | null; details: string | null; }
interface Summary { total: number; by_source: { source: string; n: number }[]; failed_logins: number; critical: number; top_actors: { actor: string; n: number }[]; }
interface Facets { actions: string[]; categories: string[]; sources: string[]; risks: string[]; }

const SRC: Record<string, { label: string; cls: string }> = {
  admin: { label: "Admin", cls: "bg-blue-100 text-blue-700" },
  usuario: { label: "Usuario", cls: "bg-ms-gray-20 text-ms-gray-130" },
  seguridad: { label: "Seguridad", cls: "bg-red-100 text-red-700" },
};
const RISK: Record<string, string> = { high: "bg-red-100 text-red-700", medium: "bg-amber-100 text-amber-700", low: "bg-ms-gray-20 text-ms-gray-130" };

export function AdvancedAudit() {
  const [sum, setSum] = useState<Summary | null>(null);
  const [facets, setFacets] = useState<Facets>({ actions: [], categories: [], sources: [], risks: [] });
  const [entries, setEntries] = useState<Entry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage] = useState(50);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [openRow, setOpenRow] = useState<number | null>(null);
  const [retention, setRetention] = useState(0);

  const [f, setF] = useState({ q: "", source: "", action: "", risk: "", date_from: "", date_to: "" });

  const qs = (extra: any = {}) => new URLSearchParams({ ...f, ...extra } as any).toString();

  const load = (p = page) => {
    api.get<{ total: number; entries: Entry[] }>(`/advanced-audit/search?${qs({ page: p, per_page: perPage })}`)
      .then((d) => { setEntries(d.entries); setTotal(d.total); setPage(p); }).catch(() => {});
  };

  useEffect(() => {
    Promise.all([
      api.get<Summary>("/advanced-audit/summary").then(setSum).catch(() => {}),
      api.get<Facets>("/advanced-audit/facets").then(setFacets).catch(() => {}),
      api.get<{ retention_days: number }>("/advanced-audit/retention").then((r) => setRetention(r.retention_days)).catch(() => {}),
      load(1),
    ]).finally(() => setLoading(false));
  }, []);

  const exportCsv = async () => {
    try {
      const r: any = await api.get(`/advanced-audit/export?${qs()}`);
      const blob = new Blob([r.csv], { type: "text/csv;charset=utf-8" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `auditoria_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      setMsg({ ok: true, text: `Exportadas ${r.rows} filas.` });
    } catch (e: any) { setMsg({ ok: false, text: e?.message || "Error al exportar" }); }
  };

  const saveRetention = async () => {
    try { await api.put("/advanced-audit/retention", { retention_days: retention }); setMsg({ ok: true, text: "Retención guardada." }); }
    catch (e: any) { setMsg({ ok: false, text: e?.message || "Error" }); }
  };
  const purge = async () => {
    if (!window.confirm(`¿Borrar registros más antiguos que ${retention} días? Esto es irreversible.`)) return;
    try { const r: any = await api.post("/advanced-audit/retention/purge", {}); setMsg({ ok: !!r.ok, text: r.ok ? `Borrados ${r.deleted} registros.` : (r.reason || "No se borró nada") }); load(1); }
    catch (e: any) { setMsg({ ok: false, text: e?.message || "Error" }); }
  };

  if (loading) return <div className="p-6 text-sm text-ms-gray-110">Cargando…</div>;
  const pages = Math.max(1, Math.ceil(total / perPage));

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-160 mb-1">Auditoría avanzada</h1>
        <SectionHelp titulo="Auditoría avanzada" items={[
          { titulo: "Qué es esta sección", desc: "Registro unificado de TODA la actividad del sistema en un solo lugar: acciones de administradores del panel, actividad de usuarios de correo y eventos de seguridad." },
          { titulo: "Tarjetas de resumen", desc: "Total de eventos registrados, logins fallidos y eventos de riesgo alto de los últimos 30 días, y el actor más activo del período." },
          { titulo: "Búsqueda y filtros", desc: "Busque por actor, acción u objetivo; filtre por origen (admin, usuario, seguridad), tipo de acción, nivel de riesgo y rango de fechas. Enter o el botón Buscar aplican los filtros." },
          { titulo: "Detalle de eventos", desc: "Haga clic en una fila con flecha para desplegar los detalles completos del evento en formato texto." },
          { titulo: "Exportar CSV", desc: "Descarga los eventos que cumplen los filtros actuales como archivo CSV, útil para informes o análisis externo. No modifica nada." },
          { titulo: "Retención", desc: "Define cuántos días se conservan los registros (0 = para siempre). El botón rojo borra de inmediato y de forma irreversible los registros más antiguos que ese plazo." },
        ]} />
      </div>
      <p className="text-sm text-ms-gray-110 mb-4">Registro unificado de toda la actividad: acciones del panel, actividad de usuarios y acciones de seguridad. Con búsqueda, filtros y exportación.</p>
      {msg && <div className={`text-sm mb-4 px-3 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"}`}>{msg.text}</div>}

      {/* Resumen */}
      <div className="grid grid-cols-4 gap-3 mb-5">
        <div className="bg-white border border-ms-gray-30 rounded-lg p-4 text-center"><div className="text-2xl font-bold text-ms-gray-160">{sum?.total || 0}</div><div className="text-xs text-ms-gray-110">Eventos totales</div></div>
        <div className="bg-white border border-ms-gray-30 rounded-lg p-4 text-center"><div className="text-2xl font-bold text-[#d13438]">{sum?.failed_logins || 0}</div><div className="text-xs text-ms-gray-110">Logins fallidos (30d)</div></div>
        <div className="bg-white border border-ms-gray-30 rounded-lg p-4 text-center"><div className="text-2xl font-bold text-[#ca5010]">{sum?.critical || 0}</div><div className="text-xs text-ms-gray-110">Riesgo alto (30d)</div></div>
        <div className="bg-white border border-ms-gray-30 rounded-lg p-4 text-center"><div className="text-sm font-medium text-ms-gray-160 truncate">{sum?.top_actors?.[0]?.actor || "—"}</div><div className="text-xs text-ms-gray-110">Más activo (30d)</div></div>
      </div>

      {/* Filtros */}
      <div className="bg-white border border-ms-gray-30 rounded-lg p-3 mb-4 flex flex-wrap gap-2 items-end">
        <input className="flex-1 min-w-[160px] px-3 py-2 border border-ms-gray-30 rounded text-sm" placeholder="Buscar (actor, acción, objetivo…)" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} onKeyDown={(e) => { if (e.key === "Enter") load(1); }} title="Texto libre a buscar en actor, acción u objetivo de los eventos. Enter ejecuta la búsqueda. Solo lectura." />
        <select className="px-2 py-2 border border-ms-gray-30 rounded text-sm" value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })} title="Filtra por origen del evento: Admin (acciones del panel), Usuario (actividad de correo) o Seguridad (alertas y bloqueos). Vacío = todos."><option value="">Todo origen</option>{facets.sources.map((s) => <option key={s} value={s}>{SRC[s]?.label || s}</option>)}</select>
        <select className="px-2 py-2 border border-ms-gray-30 rounded text-sm max-w-[160px]" value={f.action} onChange={(e) => setF({ ...f, action: e.target.value })} title="Filtra por tipo de acción exacto (login, delete, create, etc.). Vacío = todas las acciones."><option value="">Toda acción</option>{facets.actions.map((a) => <option key={a} value={a}>{a}</option>)}</select>
        <select className="px-2 py-2 border border-ms-gray-30 rounded text-sm" value={f.risk} onChange={(e) => setF({ ...f, risk: e.target.value })} title="Filtra por nivel de riesgo del evento: high (alto), medium (medio) o low (bajo). Vacío = todos."><option value="">Todo riesgo</option>{facets.risks.map((r) => <option key={r} value={r}>{r}</option>)}</select>
        <input type="date" className="px-2 py-2 border border-ms-gray-30 rounded text-sm" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} title="Desde" />
        <input type="date" className="px-2 py-2 border border-ms-gray-30 rounded text-sm" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} title="Hasta" />
        <button onClick={() => load(1)} title="Ejecuta la búsqueda con los filtros seleccionados y muestra la primera página de resultados. Solo lectura, no modifica nada." className="px-4 py-2 bg-ms-blue text-white rounded text-sm font-medium">Buscar</button>
        <button onClick={exportCsv} title="Descarga un archivo CSV con todos los eventos que cumplen los filtros actuales. No modifica ningún registro." className="px-3 py-2 bg-ms-gray-20 text-ms-gray-160 rounded text-sm">Exportar CSV</button>
      </div>

      {/* Tabla */}
      <div className="bg-white border border-ms-gray-30 rounded-lg overflow-hidden mb-3">
        <table className="w-full text-sm">
          <thead className="bg-ms-gray-10 text-ms-gray-110 text-xs">
            <tr><th className="text-left px-3 py-2 font-medium">Fecha</th><th className="text-left px-3 py-2 font-medium">Origen</th><th className="text-left px-3 py-2 font-medium">Actor</th><th className="text-left px-3 py-2 font-medium">Acción</th><th className="text-left px-3 py-2 font-medium">Objetivo</th><th className="text-left px-3 py-2 font-medium">IP</th><th className="px-3 py-2"></th></tr>
          </thead>
          <tbody>
            {entries.length === 0 ? <tr><td colSpan={7} className="p-4 text-ms-gray-110 text-sm">Sin resultados.</td></tr> :
              entries.map((e, i) => (
                <Fragment key={i}>
                  <tr key={i} className="border-t border-ms-gray-10 hover:bg-ms-gray-10 cursor-pointer" onClick={() => setOpenRow(openRow === i ? null : i)} title="Haga clic para mostrar u ocultar los detalles completos de este evento. Solo lectura.">
                    <td className="px-3 py-2 text-ms-gray-110 whitespace-nowrap">{e.ts ? new Date(e.ts).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "short" }) : "—"}</td>
                    <td className="px-3 py-2"><span className={`text-xs rounded px-2 py-0.5 ${SRC[e.source]?.cls || ""}`}>{SRC[e.source]?.label || e.source}</span></td>
                    <td className="px-3 py-2 text-ms-gray-160 max-w-[160px] truncate">{e.actor}</td>
                    <td className="px-3 py-2 text-ms-gray-130">{e.action} {e.risk === "high" && <span className="text-xs bg-red-100 text-red-700 rounded px-1">alto</span>}</td>
                    <td className="px-3 py-2 text-ms-gray-110 max-w-[160px] truncate">{e.target || ""}</td>
                    <td className="px-3 py-2 text-ms-gray-110 text-xs">{e.ip || ""}</td>
                    <td className="px-3 py-2 text-ms-gray-110 text-xs">{e.details ? (openRow === i ? "▲" : "▼") : ""}</td>
                  </tr>
                  {openRow === i && e.details && (
                    <tr key={i + "d"} className="bg-ms-gray-10"><td colSpan={7} className="px-4 py-2"><pre className="text-xs text-ms-gray-130 whitespace-pre-wrap break-all">{e.details}</pre></td></tr>
                  )}
                </Fragment>
              ))}
          </tbody>
        </table>
      </div>

      {/* Paginación */}
      <div className="flex items-center justify-between mb-6">
        <span className="text-xs text-ms-gray-110">{total} eventos · página {page}/{pages}</span>
        <div className="flex gap-1">
          <button disabled={page <= 1} onClick={() => load(page - 1)} title="Muestra la página anterior de resultados. Solo lectura." className="px-3 py-1 border border-ms-gray-30 rounded text-sm disabled:opacity-40">‹ Anterior</button>
          <button disabled={page >= pages} onClick={() => load(page + 1)} title="Muestra la página siguiente de resultados. Solo lectura." className="px-3 py-1 border border-ms-gray-30 rounded text-sm disabled:opacity-40">Siguiente ›</button>
        </div>
      </div>

      {/* Retención */}
      <h2 className="text-base font-semibold text-ms-gray-160 mb-1">Retención de registros</h2>
      <div className="bg-white border border-ms-gray-30 rounded-lg p-4 flex items-center gap-3 flex-wrap">
        <label className="text-sm text-ms-gray-130">Conservar registros por</label>
        <input type="number" min={0} max={3650} className="w-24 px-3 py-2 border border-ms-gray-30 rounded text-sm" value={retention} onChange={(e) => setRetention(parseInt(e.target.value || "0"))} title="Días que se conservan los registros de auditoría (0 a 3650). 0 = conservar siempre. Se aplica al pulsar Guardar." />
        <span className="text-sm text-ms-gray-130">días <span className="text-ms-gray-110 text-xs">(0 = conservar siempre)</span></span>
        <button onClick={saveRetention} title="Guarda la política de retención. No borra nada por sí solo; solo define el plazo de conservación." className="px-3 py-2 bg-ms-blue text-white rounded text-sm">Guardar</button>
        {retention > 0 && <button onClick={purge} title="PRECAUCIÓN: Borra de inmediato todos los registros más antiguos que el plazo configurado. Esta acción es irreversible. Pide confirmación." className="px-3 py-2 bg-red-600 text-white rounded text-sm">Borrar más antiguos ahora</button>}
      </div>
    </div>
  );
}
