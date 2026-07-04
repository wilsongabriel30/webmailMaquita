import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

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
      <div className="flex justify-end">
        <SectionHelp
          titulo="Retención de correo"
          items={[
            { titulo: "Para qué sirve", desc: "Define cuánto tiempo se conservan los correos y qué pasa al vencer ese plazo: eliminarlos o moverlos a otra carpeta. Útil para liberar espacio y cumplir normativas." },
            { titulo: "Tabla de políticas", desc: "Cada fila muestra el estado (activa/inactiva), el alcance (buzones y carpeta), la antigüedad máxima en días y la acción que se ejecuta al vencer." },
            { titulo: "Activar con cuidado", desc: "Las políticas nuevas nacen desactivadas y no hacen nada. Al activar una política de eliminar, los correos más viejos que el límite se borrarán en la próxima ejecución, sin vuelta atrás." },
            { titulo: "Crear una política", desc: "Indica nombre, carpeta (* para todas, o una como Trash), días de antigüedad y la acción. Si eliges Mover, aparece el campo de carpeta destino." },
            { titulo: "Eliminar vs Mover", desc: "Eliminar borra el correo definitivamente. Mover lo conserva pero lo pasa a otra carpeta (ej: Archive), sin destruir información." },
          ]}
        />
      </div>
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
                <td className="px-3 py-2"><button onClick={() => toggle(p)} title="Activa o desactiva la política. PRECAUCIÓN: al activar una política de eliminar, los correos que superen la antigüedad se borrarán definitivamente en la próxima ejecución. Pide confirmación." className="text-xs px-2 py-1 rounded" style={{ background: p.is_active ? "#dff6dd" : "#f3f2f1", color: p.is_active ? "#107c10" : "#605e5c" }}>{p.is_active ? "Activa" : "Inactiva"}</button></td>
                <td className="px-3 py-2 text-ms-gray-160">{p.name}<div className="text-xs text-ms-gray-110">{p.description}</div></td>
                <td className="px-3 py-2 text-ms-gray-110">{p.target} · {p.folder_pattern}</td>
                <td className="px-3 py-2 text-ms-gray-110">{p.max_age_days} días</td>
                <td className="px-3 py-2 text-ms-gray-110">{p.action === "delete" ? "Eliminar" : `Mover → ${p.move_to}`}</td>
                <td className="px-3 py-2 text-right"><button onClick={() => del(p.id)} title="PRECAUCIÓN: Elimina la política definitivamente y deja de aplicarse. No recupera correos ya afectados. Pide confirmación." className="text-xs hover:underline" style={{ color: "#a4262c" }}>Eliminar</button></td>
              </tr>
            ))}
            {!pols.length && <tr><td colSpan={6} className="px-3 py-6 text-center text-ms-gray-110">Sin políticas.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="bg-white border border-ms-gray-30 rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-semibold text-ms-gray-160">Nueva política</h2>
        <div className="grid grid-cols-2 gap-2">
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Nombre" title="Nombre de la nueva política. Obligatorio; identifica la regla en la tabla." className="px-3 py-2 border border-ms-gray-30 rounded text-sm" />
          <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Descripción" title="Descripción opcional del propósito de la política. Solo informativa." className="px-3 py-2 border border-ms-gray-30 rounded text-sm" />
          <input value={form.folder_pattern} onChange={(e) => setForm({ ...form, folder_pattern: e.target.value })} placeholder="Carpeta (ej: * o Trash)" title="Carpeta IMAP a la que aplica: * para todas las carpetas, o un nombre concreto como Trash o Junk." className="px-3 py-2 border border-ms-gray-30 rounded text-sm" />
          <input type="number" value={form.max_age_days} onChange={(e) => setForm({ ...form, max_age_days: Number(e.target.value) })} placeholder="Días" title="Antigüedad máxima en días: los correos más viejos que este valor serán eliminados o movidos cuando la política se ejecute." className="px-3 py-2 border border-ms-gray-30 rounded text-sm" />
          <select value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value })} title="Acción al vencer el plazo: Eliminar borra el correo definitivamente; Mover a carpeta lo conserva en otra carpeta (aparece el campo de destino)." className="px-3 py-2 border border-ms-gray-30 rounded text-sm"><option value="delete">Eliminar</option><option value="move">Mover a carpeta</option></select>
          {form.action === "move" && <input value={form.move_to} onChange={(e) => setForm({ ...form, move_to: e.target.value })} placeholder="Mover a (carpeta)" title="Carpeta destino a la que se moverán los correos vencidos (ej: Archive)." className="px-3 py-2 border border-ms-gray-30 rounded text-sm" />}
        </div>
        <button onClick={create} title="Crea la política con los datos del formulario. Nace desactivada: no borra ni mueve nada hasta que la actives en la tabla." className="text-white text-sm px-4 py-2 rounded" style={{ backgroundColor: "#0078d4" }}>Agregar política</button>
      </div>
    </div>
  );
}
