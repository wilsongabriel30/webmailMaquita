import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { fechaHora } from "./tipos";

interface Codigo { id: number; prefijo: string; etiqueta: string; modo: string; usos_max: number; usos: number; creado_por: string; creado_en: string; caduca_en?: string; revocado_en?: string }

export function Codigos() {
  const [lista, setLista] = useState<Codigo[]>([]);
  const [f, setF] = useState({ etiqueta: "", modo: "propietario", usos_max: 1, horas_validez: 72 });
  const [nuevo, setNuevo] = useState<{ codigo: string; caduca_en: string } | null>(null);
  const [error, setError] = useState("");

  const cargar = () => api.get<{ codigos: Codigo[] }>("/dispositivos/codigos").then((r) => setLista(r.codigos)).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);

  const crear = async () => {
    try { setError(""); setNuevo(await api.post("/dispositivos/codigos", f)); cargar(); }
    catch (e: any) { setError(e.message); }
  };
  const revocar = async (id: number) => { if (confirm("¿Anular este código? Los equipos ya enrolados con él no se ven afectados.")) { await api.del(`/dispositivos/codigos/${id}`); cargar(); } };
  const estado = (c: Codigo) => c.revocado_en ? "anulado" : c.usos >= c.usos_max ? "agotado" : c.caduca_en && new Date(c.caduca_en) < new Date() ? "caducado" : "vigente";

  return (
    <div className="space-y-4">
      {error && <div className="text-sm px-3 py-2 rounded bg-red-50 text-red-700">{error}</div>}
      <div className="bg-white rounded-lg border border-ms-gray-30 p-4 space-y-3">
        <h3 className="text-sm font-semibold">Nuevo código de enrolamiento</h3>
        <p className="text-xs text-ms-gray-60">Es la contraseña de instalación: sin un código vigente, la app no activa la gestión del equipo. Solo Tecnología los crea y se muestran una única vez.</p>
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <label className="text-xs">Para qué es<input value={f.etiqueta} onChange={(e) => setF({ ...f, etiqueta: e.target.value })} placeholder="Ej: Samsung A16 Ventas (compra sep-2026)" className="mt-1 block w-72 px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded" /></label>
          <label className="text-xs">Tipo<select value={f.modo} onChange={(e) => setF({ ...f, modo: e.target.value })} className="mt-1 block px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded">
            <option value="propietario">Equipo restaurado de fábrica (control completo)</option><option value="limitado">Teléfono ya en uso (modo limitado)</option></select></label>
          <label className="text-xs">Equipos<input type="number" min={1} max={500} value={f.usos_max} onChange={(e) => setF({ ...f, usos_max: Number(e.target.value) })} className="mt-1 block w-20 px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded" /></label>
          <label className="text-xs">Válido (horas)<input type="number" min={1} max={2160} value={f.horas_validez} onChange={(e) => setF({ ...f, horas_validez: Number(e.target.value) })} className="mt-1 block w-24 px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded" /></label>
          <button onClick={crear} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">Crear código</button>
        </div>
        {nuevo && <div className="bg-amber-50 border border-amber-200 rounded p-3">
          <div className="text-xs text-amber-800 mb-1">Cópielo ahora: no se volverá a mostrar. Caduca {fechaHora(nuevo.caduca_en)}.</div>
          <div className="flex items-center gap-3"><code className="text-2xl font-mono tracking-widest">{nuevo.codigo}</code>
            <button onClick={() => navigator.clipboard.writeText(nuevo.codigo)} className="text-xs text-ms-blue hover:underline">Copiar</button></div>
        </div>}
      </div>
      <div className="bg-white rounded-lg border border-ms-gray-30 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="bg-ms-gray-10">{["Código", "Para qué", "Tipo", "Usos", "Creado", "Caduca", "Estado", ""].map((h) => <th key={h} className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">{h}</th>)}</tr></thead>
          <tbody>
            {lista.map((c) => <tr key={c.id} className="border-t border-ms-gray-20">
              <td className="px-4 py-2.5 font-mono">{c.prefijo}-••••-••••</td><td className="px-4 py-2.5">{c.etiqueta || "—"}</td>
              <td className="px-4 py-2.5 text-xs">{c.modo === "propietario" ? "Control completo" : "Limitado"}</td><td className="px-4 py-2.5">{c.usos} / {c.usos_max}</td>
              <td className="px-4 py-2.5 text-xs">{fechaHora(c.creado_en)}<div className="text-ms-gray-60">{c.creado_por}</div></td>
              <td className="px-4 py-2.5 text-xs">{fechaHora(c.caduca_en)}</td><td className="px-4 py-2.5 text-xs">{estado(c)}</td>
              <td className="px-4 py-2.5 text-right">{estado(c) === "vigente" && <button onClick={() => revocar(c.id)} className="text-xs text-ms-red hover:underline">Anular</button>}</td>
            </tr>)}
            {!lista.length && <tr><td colSpan={8} className="px-4 py-6 text-center text-ms-gray-60">Sin códigos todavía.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
