import { useEffect, useState } from "react";
import { api } from "../api/client";

interface Pol { id: number; name: string; description: string; target: string; folder_pattern: string; max_age_days: number; action: string; move_to: string; is_active: boolean; messages_affected: number; last_run: string | null; }

export function Retention() {
  const [pols, setPols] = useState<Pol[]>([]);
  const [form, setForm] = useState({ name: "", description: "", target: "all", folder_pattern: "*", max_age_days: 365, action: "delete", move_to: "" });

  const load = () => api.get<{ policies: Pol[] }>("/retention/policies").then((r) => setPols(r?.policies || [])).catch(() => {});
  useEffect(load, []);

  const toggle = async (p: Pol) => {
    if (!p.is_active && p.action === "delete" && !confirm(`Activar "${p.name}": ELIMINARÁ correos de más de ${p.max_age_days} días al ejecutarse. ¿Continuar?`)) return;
    await api.post("/retention/toggle", { id: p.id, is_active: !p.is_active }); load();
  };
  const create = async () => {
    if (!form.name.trim()) return;
    await api.post("/retention/policies", form); setForm({ ...form, name: "", description: "" }); load();
  };
  const del = async (id: number) => { if (!confirm("¿Eliminar la política?")) return; await api.post("/retention/delete", { id }); load(); };

  return (
    <div className="p-6 max-w-4xl space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-ms-gray-160">Retención de correo</h1>
        <p className="text-sm text-ms-gray-110">Políticas de retención (E5 Compliance): cuánto se conservan los correos y qué se hace al vencer. Vienen desactivadas; actívalas con cuidado.</p>
      </div>

      <div className="bg-white border border-ms-gray-30 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-ms-gray-10 text-ms-gray-110">
            <tr>
              <th className="text-left px-3 py-2">Estado</th><th className="text-left px-3 py-2">Política</th>
              <th className="text-left px-3 py-2">Alcance</th><th className="text-left px-3 py-2">Antigüedad</th>
              <th className="text-left px-3 py-2">Acción</th><th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {pols.map((p) => (
              <tr key={p.id} className="border-t border-ms-gray-30">
                <td className="px-3 py-2"><button onClick={() => toggle(p)} className="text-xs px-2 py-1 rounded" style={{ background: p.is_active ? "#dff6dd" : "#f3f2f1", color: p.is_active ? "#107c10" : "#605e5c" }}>{p.is_active ? "Activa" : "Inactiva"}</button></td>
                <td className="px-3 py-2 text-ms-gray-160">{p.name}<div className="text-xs text-ms-gray-110">{p.description}</div></td>
                <td className="px-3 py-2 text-ms-gray-110">{p.target} · {p.folder_pattern}</td>
                <td className="px-3 py-2 text-ms-gray-110">{p.max_age_days} días</td>
                <td className="px-3 py-2 text-ms-gray-110">{p.action === "delete" ? "Eliminar" : `Mover → ${p.move_to}`}</td>
                <td className="px-3 py-2 text-right"><button onClick={() => del(p.id)} className="text-xs hover:underline" style={{ color: "#a4262c" }}>Eliminar</button></td>
              </tr>
            ))}
            {!pols.length && <tr><td colSpan={6} className="px-3 py-6 text-center text-ms-gray-110">Sin políticas.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="bg-white border border-ms-gray-30 rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-semibold text-ms-gray-160">Nueva política</h2>
        <div className="grid grid-cols-2 gap-2">
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Nombre" className="px-3 py-2 border border-ms-gray-30 rounded text-sm" />
          <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Descripción" className="px-3 py-2 border border-ms-gray-30 rounded text-sm" />
          <input value={form.folder_pattern} onChange={(e) => setForm({ ...form, folder_pattern: e.target.value })} placeholder="Carpeta (ej: * o Trash)" className="px-3 py-2 border border-ms-gray-30 rounded text-sm" />
          <input type="number" value={form.max_age_days} onChange={(e) => setForm({ ...form, max_age_days: Number(e.target.value) })} placeholder="Días" className="px-3 py-2 border border-ms-gray-30 rounded text-sm" />
          <select value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value })} className="px-3 py-2 border border-ms-gray-30 rounded text-sm"><option value="delete">Eliminar</option><option value="move">Mover a carpeta</option></select>
          {form.action === "move" && <input value={form.move_to} onChange={(e) => setForm({ ...form, move_to: e.target.value })} placeholder="Mover a (carpeta)" className="px-3 py-2 border border-ms-gray-30 rounded text-sm" />}
        </div>
        <button onClick={create} className="text-white text-sm px-4 py-2 rounded" style={{ backgroundColor: "#0078d4" }}>Agregar política</button>
      </div>
    </div>
  );
}
