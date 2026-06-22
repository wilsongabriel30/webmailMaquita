import { useEffect, useState } from "react";
import { api } from "../api/client";

interface Incident {
  id: number; action: string; username: string; detail: string;
  auto: boolean; severity: string; created_at: string | null;
}

const SEV: Record<string, { bg: string; text: string; label: string }> = {
  high: { bg: "#fde7e9", text: "#a4262c", label: "Alta" },
  medium: { bg: "#fff4ce", text: "#7a6400", label: "Media" },
  low: { bg: "#f3f2f1", text: "#605e5c", label: "Baja" },
};

export function Air() {
  const [items, setItems] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [out, setOut] = useState("");
  const [hours, setHours] = useState(168);

  const load = () => {
    setLoading(true);
    api.get<{ incidents: Incident[] }>(`/air/incidents?hours=${hours}`)
      .then((r) => setItems(r?.incidents || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };
  useEffect(load, [hours]);

  const investigate = async () => {
    setRunning(true); setOut("");
    try {
      const r = await api.post<{ ok: boolean; output: string }>(`/air/investigate?hours=24`, {});
      setOut(r?.output || "");
      load();
    } catch {
      setOut("Error al investigar.");
    }
    setRunning(false);
  };

  const lock = async (username: string) => {
    if (!confirm(`¿Contener (desactivar) el buzón ${username}?`)) return;
    await api.post(`/air/lock`, { username });
    load();
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-semibold text-[#323130]">AIR — Investigación y respuesta automática</h1>
          <p className="text-sm text-[#605e5c]">Incidentes correlacionados con triage de IA local (Qwen). Detecta y recomienda; contiene bajo control.</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={hours} onChange={(e) => setHours(Number(e.target.value))} className="border border-[#d2d0ce] rounded px-2 py-1 text-sm">
            <option value={24}>24 h</option>
            <option value={168}>7 días</option>
            <option value={720}>30 días</option>
          </select>
          <button onClick={investigate} disabled={running}
            className="bg-[#0078d4] text-white text-sm px-4 py-2 rounded disabled:opacity-50">
            {running ? "Investigando…" : "Investigar ahora"}
          </button>
        </div>
      </div>

      {out && <pre className="bg-[#1e1e1e] text-[#e0e0e0] text-xs p-3 rounded mb-4 whitespace-pre-wrap max-h-48 overflow-auto">{out}</pre>}

      <div className="bg-white border border-[#edebe9] rounded overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#faf9f8] text-[#605e5c]">
            <tr>
              <th className="text-left px-3 py-2">Severidad</th>
              <th className="text-left px-3 py-2">Buzón</th>
              <th className="text-left px-3 py-2">Detalle (señales + IA)</th>
              <th className="text-left px-3 py-2">Cuándo</th>
              <th className="text-left px-3 py-2">Acción</th>
            </tr>
          </thead>
          <tbody>
            {items.map((i) => {
              const s = SEV[i.severity] || SEV.low;
              return (
                <tr key={i.id} className="border-t border-[#edebe9]">
                  <td className="px-3 py-2">
                    <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ background: s.bg, color: s.text }}>{s.label}</span>
                    {i.action === "account_locked" && <span className="ml-1 text-xs text-[#a4262c]">contenido</span>}
                  </td>
                  <td className="px-3 py-2 font-medium text-[#323130]">{i.username || "—"}</td>
                  <td className="px-3 py-2 text-[#605e5c]">{i.detail}</td>
                  <td className="px-3 py-2 text-[#605e5c] whitespace-nowrap">{i.created_at ? new Date(i.created_at).toLocaleString() : ""}</td>
                  <td className="px-3 py-2">
                    {i.action !== "account_locked" &&
                      <button onClick={() => lock(i.username)} className="text-[#a4262c] text-xs hover:underline">Contener</button>}
                  </td>
                </tr>
              );
            })}
            {!items.length && (
              <tr><td colSpan={5} className="px-3 py-6 text-center text-[#605e5c]">{loading ? "Cargando…" : "Sin incidentes en el período."}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
