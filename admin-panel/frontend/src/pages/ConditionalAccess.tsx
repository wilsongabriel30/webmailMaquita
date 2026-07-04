import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface Policy { id: number; name: string; condition: string; action: string; enabled: boolean; }

const CONDS: Record<string, string> = {
  riesgo_alto: "Login de riesgo alto",
  pais_no_confiable: "País no confiable",
  viaje_imposible: "Viaje imposible (geo)",
};
const ACTS: Record<string, string> = {
  bloquear: "Bloquear cuenta",
  requerir_2fa: "Requerir 2FA",
  alertar: "Solo alertar",
};

export function ConditionalAccess() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [name, setName] = useState("");
  const [cond, setCond] = useState("riesgo_alto");
  const [act, setAct] = useState("alertar");

  const load = () => api.get<{ policies: Policy[] }>("/conditional-access/policies").then((r) => setPolicies(r?.policies || [])).catch(() => {});
  useEffect(load, []);

  const toggle = async (p: Policy) => {
    if (!p.enabled && p.action === "bloquear" && !confirm(`Activar "${p.name}": BLOQUEARÁ cuentas automáticamente al cumplirse la condición. ¿Continuar?`)) return;
    await api.post("/conditional-access/toggle", { id: p.id, enabled: !p.enabled }); load();
  };
  const add = async () => {
    if (!name.trim()) return;
    await api.post("/conditional-access/policies", { name, condition: cond, action: act });
    setName(""); load();
  };
  const del = async (id: number) => { if (!confirm("¿Eliminar la política?")) return; await api.post("/conditional-access/delete", { id }); load(); };

  return (
    <div className="p-6 max-w-3xl space-y-5">
      <div className="flex justify-end">
        <SectionHelp
          titulo="Acceso Condicional"
          items={[
            { titulo: "¿Qué es?", desc: "Reglas del tipo «si pasa X, entonces haz Y» que se evalúan en cada inicio de sesión. Sirven para reaccionar automáticamente ante accesos sospechosos." },
            { titulo: "Condiciones (Si…)", desc: "Login de riesgo alto (puntuación de riesgo elevada), país no confiable (conexión desde un país fuera de la lista segura) o viaje imposible (dos accesos desde lugares demasiado lejanos en poco tiempo)." },
            { titulo: "Acciones (Entonces)", desc: "«Solo alertar» avisa al administrador sin tocar nada; «Requerir 2FA» exige segundo factor; «Bloquear cuenta» desactiva el buzón automáticamente (la más drástica)." },
            { titulo: "Activar con cuidado", desc: "Todas las políticas vienen inactivas. El botón de estado las enciende o apaga; al activar una que bloquea cuentas se pide confirmación porque puede dejar usuarios legítimos sin acceso." },
            { titulo: "Recomendación", desc: "Empieza con «Solo alertar» unos días para ver cuántos avisos genera antes de pasar a acciones que bloquean." },
          ]}
        />
      </div>
      <div>
        <h1 className="text-xl font-semibold text-ms-gray-160">Acceso Condicional</h1>
        <p className="text-sm text-ms-gray-110">Políticas que actúan sobre los inicios de sesión según el riesgo. Todas vienen desactivadas; actívalas con cuidado.</p>
      </div>

      <div className="bg-white border border-ms-gray-30 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-ms-gray-10 text-ms-gray-110">
            <tr>
              <th className="text-left px-3 py-2">Estado</th><th className="text-left px-3 py-2">Política</th>
              <th className="text-left px-3 py-2">Si…</th><th className="text-left px-3 py-2">Entonces</th><th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {policies.map((p) => (
              <tr key={p.id} className="border-t border-ms-gray-30">
                <td className="px-3 py-2">
                  <button onClick={() => toggle(p)}
                    title="Activa o desactiva esta política. Al activarla empieza a aplicarse en cada inicio de sesión; si su acción es bloquear cuentas, se pide confirmación porque podría dejar usuarios sin acceso automáticamente."
                    className="text-xs px-2 py-1 rounded"
                    style={{ background: p.enabled ? "#dff6dd" : "#f3f2f1", color: p.enabled ? "#107c10" : "#605e5c" }}>
                    {p.enabled ? "Activa" : "Inactiva"}
                  </button>
                </td>
                <td className="px-3 py-2 text-ms-gray-160">{p.name}</td>
                <td className="px-3 py-2 text-ms-gray-110">{CONDS[p.condition] || p.condition}</td>
                <td className="px-3 py-2 text-ms-gray-110">{ACTS[p.action] || p.action}</td>
                <td className="px-3 py-2 text-right"><button onClick={() => del(p.id)} title="Elimina esta política de forma permanente; dejará de evaluarse en los inicios de sesión. Pide confirmación y no se puede deshacer." className="text-xs hover:underline" style={{ color: "#a4262c" }}>Eliminar</button></td>
              </tr>
            ))}
            {!policies.length && <tr><td colSpan={5} className="px-3 py-6 text-center text-ms-gray-110">Sin políticas.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="bg-white border border-ms-gray-30 rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-semibold text-ms-gray-160">Nueva política</h2>
        <div className="flex flex-wrap gap-2 items-end">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nombre" title="Nombre descriptivo de la nueva política para reconocerla en la tabla (ej.: Bloquear logins desde países no confiables). Es obligatorio para agregarla." className="px-3 py-2 border border-ms-gray-30 rounded text-sm flex-1" style={{ minWidth: "10rem" }} />
          <div><label className="block text-xs text-ms-gray-110">Si…</label>
            <select value={cond} onChange={(e) => setCond(e.target.value)} title="Condición que dispara la política en cada inicio de sesión: riesgo alto (puntuación elevada), país no confiable o viaje imposible (dos accesos desde lugares muy lejanos en poco tiempo)." className="border border-ms-gray-30 rounded px-2 py-2 text-sm">{Object.entries(CONDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
          <div><label className="block text-xs text-ms-gray-110">Entonces</label>
            <select value={act} onChange={(e) => setAct(e.target.value)} title="Acción a ejecutar cuando se cumpla la condición: solo alertar al administrador, exigir segundo factor (2FA) o bloquear la cuenta automáticamente (la más drástica)." className="border border-ms-gray-30 rounded px-2 py-2 text-sm">{Object.entries(ACTS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
          <button onClick={add} title="Crea la política con el nombre, la condición y la acción elegidas. Se guarda desactivada: no hará nada hasta que la actives desde la tabla." className="text-white text-sm px-4 py-2 rounded" style={{ backgroundColor: "#0078d4" }}>Agregar</button>
        </div>
      </div>
    </div>
  );
}
