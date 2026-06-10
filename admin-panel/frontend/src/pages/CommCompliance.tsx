import { useState, useEffect } from "react";
import { api } from "../api/client";

interface Policy { id: number; name: string; description: string; terms: string[]; scope: string; severity: string; enabled: boolean; }
interface Flag { id: number; policy_name: string; username: string; direction: string; recipients: string[]; subject: string; snippet: string; matched_terms: string[]; severity: string; status: string; created_at: string | null; }

const SEV: Record<string, string> = { alta: "bg-red-100 text-red-700", media: "bg-amber-100 text-amber-700", baja: "bg-ms-gray-20 text-ms-gray-130" };
const SCOPE_LBL: Record<string, string> = { outbound: "Salientes", inbound: "Entrantes", all: "Todos" };
const inputCls = "w-full px-3 py-2 border border-ms-gray-30 rounded text-sm";

export function CommCompliance() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [flags, setFlags] = useState<Flag[]>([]);
  const [openCount, setOpenCount] = useState(0);
  const [filter, setFilter] = useState("open");
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // nueva politica
  const [np, setNp] = useState<{ name: string; description: string; scope: string; severity: string; termsInput: string }>({ name: "", description: "", scope: "outbound", severity: "media", termsInput: "" });

  const loadFlags = (f = filter) => api.get<{ flags: Flag[]; open_count: number }>(`/comm-compliance/flags?status=${f}`).then((r) => { setFlags(r.flags || []); setOpenCount(r.open_count || 0); }).catch(() => {});
  const loadPolicies = () => api.get<{ policies: Policy[] }>("/comm-compliance/policies").then((r) => setPolicies(r.policies || [])).catch(() => {});

  useEffect(() => { Promise.all([loadPolicies(), loadFlags()]).finally(() => setLoading(false)); }, []);

  const toggleEnabled = async (p: Policy) => {
    try { await api.put(`/comm-compliance/policies/${p.id}`, { ...p, enabled: !p.enabled }); await loadPolicies(); }
    catch (e: any) { setMsg({ ok: false, text: e?.message || "Error" }); }
  };
  const removePolicy = async (p: Policy) => {
    if (!window.confirm(`¿Eliminar la política «${p.name}»?`)) return;
    try { await api.del(`/comm-compliance/policies/${p.id}`); await loadPolicies(); } catch {}
  };
  const createPolicy = async () => {
    const terms = np.termsInput.split(",").map((t) => t.trim()).filter(Boolean);
    if (!np.name.trim() || terms.length === 0) { setMsg({ ok: false, text: "Indica nombre y al menos un término." }); return; }
    try {
      await api.post("/comm-compliance/policies", { name: np.name, description: np.description, terms, scope: np.scope, severity: np.severity, enabled: true });
      setNp({ name: "", description: "", scope: "outbound", severity: "media", termsInput: "" });
      setMsg({ ok: true, text: "Política creada y activada." }); await loadPolicies();
    } catch (e: any) { setMsg({ ok: false, text: e?.message || "Error" }); }
  };
  const setFlagStatus = async (f: Flag, status: string) => {
    try { await api.post(`/comm-compliance/flags/${f.id}/status`, { status }); await loadFlags(); } catch {}
  };

  if (loading) return <div className="p-6 text-sm text-ms-gray-110">Cargando…</div>;

  return (
    <div className="max-w-4xl">
      <h1 className="text-xl font-semibold text-ms-gray-160 mb-1">Cumplimiento de comunicaciones</h1>
      <p className="text-sm text-ms-gray-110 mb-4">
        Monitorea los correos según las políticas que definas (conducta, términos confidenciales…). Cuando un
        correo coincide, queda en una <b>cola de revisión</b> para el área de cumplimiento. <b>No bloquea el envío.</b>
      </p>
      {msg && <div className={`text-sm mb-4 px-3 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"}`}>{msg.text}</div>}

      {/* Cola de revisión */}
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-base font-semibold text-ms-gray-160">Cola de revisión {openCount > 0 && <span className="ml-1 text-xs bg-red-100 text-red-700 rounded-full px-2 py-0.5">{openCount} pendientes</span>}</h2>
        <select className="px-2 py-1 border border-ms-gray-30 rounded text-xs" value={filter} onChange={(e) => { setFilter(e.target.value); loadFlags(e.target.value); }}>
          <option value="open">Pendientes</option><option value="all">Todas</option>
        </select>
      </div>
      <div className="bg-white border border-ms-gray-30 rounded-lg overflow-hidden mb-6">
        {flags.length === 0 ? <div className="p-4 text-sm text-ms-gray-110">Nada para revisar. 🎉</div> :
          flags.map((f) => (
            <div key={f.id} className="border-t border-ms-gray-10 first:border-0 p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`text-xs rounded px-2 py-0.5 ${SEV[f.severity] || SEV.baja}`}>{f.severity}</span>
                    <span className="text-sm font-medium text-ms-gray-160">{f.policy_name}</span>
                    <span className="text-xs text-ms-gray-110">· {f.username} → {f.recipients.join(", ")}</span>
                  </div>
                  <div className="text-sm text-ms-gray-130 mt-1"><b>Asunto:</b> {f.subject || "(sin asunto)"}</div>
                  <div className="text-xs text-ms-gray-110 mt-0.5">Coincidió: {f.matched_terms.map((t) => <span key={t} className="bg-amber-50 border border-amber-200 rounded px-1 mx-0.5">{t}</span>)}</div>
                  <div className="text-xs text-ms-gray-110 mt-1 italic truncate">{f.snippet}</div>
                </div>
                {f.status === "open" ? (
                  <div className="flex flex-col gap-1 shrink-0">
                    <button onClick={() => setFlagStatus(f, "reviewed")} className="px-2 py-1 bg-ms-gray-20 text-ms-gray-160 rounded text-xs">Revisado ✓</button>
                    <button onClick={() => setFlagStatus(f, "escalated")} className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs">Escalar</button>
                    <button onClick={() => setFlagStatus(f, "dismissed")} className="px-2 py-1 text-ms-gray-110 text-xs hover:underline">Descartar</button>
                  </div>
                ) : <span className="text-xs text-ms-gray-110 shrink-0">{f.status}</span>}
              </div>
            </div>
          ))}
      </div>

      {/* Políticas */}
      <h2 className="text-base font-semibold text-ms-gray-160 mb-2">Políticas</h2>
      <div className="bg-white border border-ms-gray-30 rounded-lg p-4 mb-4">
        <div className="text-sm font-medium text-ms-gray-130 mb-2">Nueva política</div>
        <div className="grid grid-cols-2 gap-3 mb-2">
          <input className={inputCls} placeholder="Nombre (ej. Lenguaje inapropiado)" value={np.name} onChange={(e) => setNp({ ...np, name: e.target.value })} />
          <input className={inputCls} placeholder="Descripción (opcional)" value={np.description} onChange={(e) => setNp({ ...np, description: e.target.value })} />
        </div>
        <input className={inputCls + " mb-2"} placeholder="Términos separados por coma (ej. insulto, amenaza, soborno)" value={np.termsInput} onChange={(e) => setNp({ ...np, termsInput: e.target.value })} />
        <div className="flex items-center gap-2">
          <select className="px-2 py-2 border border-ms-gray-30 rounded text-sm" value={np.scope} onChange={(e) => setNp({ ...np, scope: e.target.value })}>
            <option value="outbound">Salientes</option><option value="inbound">Entrantes</option><option value="all">Todos</option>
          </select>
          <select className="px-2 py-2 border border-ms-gray-30 rounded text-sm" value={np.severity} onChange={(e) => setNp({ ...np, severity: e.target.value })}>
            <option value="baja">Baja</option><option value="media">Media</option><option value="alta">Alta</option>
          </select>
          <button onClick={createPolicy} className="px-4 py-2 bg-ms-blue text-white rounded text-sm font-medium">Crear y activar</button>
        </div>
      </div>
      <div className="space-y-2">
        {policies.map((p) => (
          <div key={p.id} className="bg-white border border-ms-gray-30 rounded-lg p-3 flex items-center gap-3">
            <input type="checkbox" className="w-4 h-4" checked={p.enabled} onChange={() => toggleEnabled(p)} title="Activar/desactivar" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-ms-gray-160">{p.name} <span className={`ml-1 text-xs rounded px-1.5 py-0.5 ${SEV[p.severity] || SEV.baja}`}>{p.severity}</span> <span className="text-xs text-ms-gray-110">· {SCOPE_LBL[p.scope]}</span></div>
              <div className="text-xs text-ms-gray-110 truncate">{p.terms.join(", ")}</div>
            </div>
            <button onClick={() => removePolicy(p)} className="text-xs text-red-600 hover:underline shrink-0">Eliminar</button>
          </div>
        ))}
      </div>
    </div>
  );
}
