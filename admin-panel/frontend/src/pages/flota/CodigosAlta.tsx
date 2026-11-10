import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { fechaHora } from "./tipos";

// Códigos de alta de un solo uso: la garantía de que solo entran equipos de la Fundación. Los crea
// Tecnología y se muestran una sola vez (en la base queda solo su huella).

interface Codigo { id: number; prefijo: string; etiqueta: string; creado_por: string; creado_en: string; caduca_en: string; usado_en?: string; ip_uso?: string; anulado_en?: string; equipo_nombre?: string; estado: string }
interface Nuevo { id: number; codigo: string; caduca_en: string }

export function CodigosAlta() {
  const [lista, setLista] = useState<Codigo[]>([]);
  const [f, setF] = useState({ etiqueta: "", dias_validez: 7, cantidad: 1 });
  const [nuevos, setNuevos] = useState<Nuevo[]>([]);
  const [todos, setTodos] = useState(false);
  const [error, setError] = useState("");
  const cargar = () => api.get<{ codigos: Codigo[] }>("/flota/codigos").then((r) => setLista(r.codigos)).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);

  const crear = async () => {
    try { setError(""); const r = await api.post<{ codigos: Nuevo[] }>("/flota/codigos", f); setNuevos(r.codigos); cargar(); }
    catch (e: any) { setError(e.message); }
  };
  const anular = async (c: Codigo) => {
    if (!confirm(`¿Anular el código MQF-${c.prefijo}-••••-••••?`)) return;
    try { await api.del(`/flota/codigos/${c.id}`); cargar(); } catch (e: any) { setError(e.message); }
  };
  const vis = lista.filter((c) => todos || c.estado === "vigente");

  return (
    <div className="space-y-4">
      {error && <div className="text-sm px-3 py-2 rounded bg-red-50 text-red-700">{error}</div>}
      <div className="bg-white rounded-lg border border-ms-gray-30 p-4 space-y-3">
        <h3 className="text-sm font-semibold">Nuevos códigos de alta</h3>
        <p className="text-xs text-ms-gray-60">Un código = un equipo de la Fundación. Se escribe una vez en el equipo (o se pasa al instalador) y la app lo canjea por su identidad en la flota. Si el equipo ya estaba enrolado (reinstalación), conserva su mismo identificador.</p>
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <label className="text-xs">Para qué (opcional)<input value={f.etiqueta} onChange={(e) => setF({ ...f, etiqueta: e.target.value })} placeholder="Ej: portátiles sede Guayaquil" className="mt-1 block w-64 px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded" /></label>
          <label className="text-xs">Cuántos<input type="number" min={1} max={100} value={f.cantidad} onChange={(e) => setF({ ...f, cantidad: Number(e.target.value) })} className="mt-1 block w-20 px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded" /></label>
          <label className="text-xs">Válidos (días)<input type="number" min={1} max={30} value={f.dias_validez} onChange={(e) => setF({ ...f, dias_validez: Number(e.target.value) })} className="mt-1 block w-20 px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded" /></label>
          <button onClick={crear} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">Crear</button>
        </div>
        {nuevos.length > 0 && <div className="bg-amber-50 border border-amber-200 rounded p-3 space-y-1">
          <div className="text-xs text-amber-800">Cópielos ahora: no se volverán a mostrar. Caducan {fechaHora(nuevos[0].caduca_en)}.</div>
          {nuevos.map((n) => <div key={n.id} className="font-mono text-lg tracking-widest">{n.codigo}</div>)}
          <button onClick={() => navigator.clipboard.writeText(nuevos.map((n) => n.codigo).join("\n"))} className="text-xs text-ms-blue hover:underline">Copiar todos</button>
        </div>}
      </div>
      <div className="bg-white rounded-lg border border-ms-gray-30 overflow-x-auto">
        <div className="px-4 py-2 border-b border-ms-gray-20 flex items-center gap-3 text-xs text-ms-gray-60">
          <span>{vis.length} {todos ? "códigos" : "vigentes"}</span>
          <button onClick={() => setTodos(!todos)} className="text-ms-blue hover:underline">{todos ? "Solo vigentes" : "Ver también usados, anulados y caducados"}</button>
        </div>
        <table className="w-full text-sm">
          <thead><tr className="bg-ms-gray-10">{["Código", "Para qué", "Creado", "Caduca", "Estado", "Equipo", ""].map((h) => <th key={h} className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">{h}</th>)}</tr></thead>
          <tbody>
            {vis.map((c) => <tr key={c.id} className="border-t border-ms-gray-20">
              <td className="px-4 py-2 font-mono">MQF-{c.prefijo}-••••-••••</td><td className="px-4 py-2">{c.etiqueta || "—"}</td>
              <td className="px-4 py-2 text-xs">{fechaHora(c.creado_en)}<div className="text-ms-gray-60">{c.creado_por}</div></td>
              <td className="px-4 py-2 text-xs">{fechaHora(c.caduca_en)}</td><td className="px-4 py-2 text-xs">{c.estado}</td>
              <td className="px-4 py-2 text-xs">{c.equipo_nombre ? <>{c.equipo_nombre}<div className="text-ms-gray-60">{fechaHora(c.usado_en)} · {c.ip_uso}</div></> : "—"}</td>
              <td className="px-4 py-2 text-right">{c.estado === "vigente" && <button onClick={() => anular(c)} className="text-xs text-ms-red hover:underline">Anular</button>}</td>
            </tr>)}
            {!vis.length && <tr><td colSpan={7} className="px-4 py-6 text-center text-ms-gray-60">Sin códigos.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
