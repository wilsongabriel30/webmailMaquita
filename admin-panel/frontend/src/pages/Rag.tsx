import { useEffect, useState } from "react";
import { api } from "../api/client";

interface Dom { domain: string; enabled: boolean; }

export function Rag() {
  const [doms, setDoms] = useState<Dom[]>([]);
  const [stats, setStats] = useState<{ indexed_total: number; users_indexed: number }>({ indexed_total: 0, users_indexed: 0 });
  const [newDom, setNewDom] = useState("");
  const [user, setUser] = useState("");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState("");
  const [result, setResult] = useState<any>(null);
  const [ingestMsg, setIngestMsg] = useState("");

  const load = () => api.get<any>("/rag/domains").then((r) => { setDoms(r?.domains || []); setStats({ indexed_total: r?.indexed_total || 0, users_indexed: r?.users_indexed || 0 }); }).catch(() => {});
  useEffect(load, []);

  const toggle = async (d: Dom) => { await api.post("/rag/domains/toggle", { domain: d.domain, enabled: !d.enabled }); load(); };
  const addDom = async () => { if (!newDom.trim()) return; await api.post("/rag/domains", { domain: newDom }); setNewDom(""); load(); };
  const ingest = async () => {
    if (!user.trim()) return;
    setBusy("ingest"); setIngestMsg("");
    try { const r = await api.post<any>("/rag/ingest", { user }); setIngestMsg(r.error ? `Error: ${r.error}` : (r.skipped ? `Omitido: ${r.skipped}` : `Indexados ${r.indexed} nuevos (total ${r.total}).`)); load(); }
    catch { setIngestMsg("Error al indexar."); }
    setBusy("");
  };
  const ask = async () => {
    if (!user.trim() || !q.trim()) return;
    setBusy("ask"); setResult(null);
    try { setResult(await api.post<any>("/rag/ask", { user, question: q })); }
    catch { setResult({ answer: "Error al preguntar." }); }
    setBusy("");
  };

  return (
    <div className="p-6 max-w-3xl space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-ms-gray-160">RAG — Pregúntale a tu correo</h1>
        <p className="text-sm text-ms-gray-110">Búsqueda semántica sobre el correo con IA local. Solo aplica a los dominios habilitados. {stats.indexed_total} correos indexados · {stats.users_indexed} buzones.</p>
      </div>

      <div className="bg-white border border-ms-gray-30 rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-semibold text-ms-gray-160">Dominios habilitados</h2>
        <div className="space-y-1">
          {doms.map((d) => (
            <div key={d.domain} className="flex items-center justify-between text-sm border-b border-ms-gray-20 py-1.5">
              <span className="font-mono text-ms-gray-160">{d.domain}</span>
              <button onClick={() => toggle(d)} className="text-xs px-2 py-1 rounded" style={{ background: d.enabled ? "#dff6dd" : "#f3f2f1", color: d.enabled ? "#107c10" : "#605e5c" }}>{d.enabled ? "Habilitado" : "Deshabilitado"}</button>
            </div>
          ))}
          {!doms.length && <div className="text-xs text-ms-gray-110">Sin dominios. Agrega uno abajo.</div>}
        </div>
        <div className="flex gap-2">
          <input value={newDom} onChange={(e) => setNewDom(e.target.value)} placeholder="dominio.com" className="px-3 py-2 border border-ms-gray-30 rounded text-sm flex-1" />
          <button onClick={addDom} className="text-white text-sm px-4 py-2 rounded" style={{ backgroundColor: "#0078d4" }}>Agregar</button>
        </div>
      </div>

      <div className="bg-white border border-ms-gray-30 rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-semibold text-ms-gray-160">Probar (indexar + preguntar)</h2>
        <input value={user} onChange={(e) => setUser(e.target.value)} placeholder="buzon@maquita.com.ec" className="px-3 py-2 border border-ms-gray-30 rounded text-sm w-full" />
        <div className="flex gap-2 items-center">
          <button onClick={ingest} disabled={busy === "ingest"} className="text-sm px-3 py-2 rounded border border-ms-gray-30 disabled:opacity-50">{busy === "ingest" ? "Indexando…" : "Indexar bandeja"}</button>
          {ingestMsg && <span className="text-xs text-ms-gray-110">{ingestMsg}</span>}
        </div>
        <div className="flex gap-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="¿Tengo algo pendiente?" className="px-3 py-2 border border-ms-gray-30 rounded text-sm flex-1" />
          <button onClick={ask} disabled={busy === "ask"} className="text-white text-sm px-4 py-2 rounded disabled:opacity-50" style={{ backgroundColor: "#0078d4" }}>{busy === "ask" ? "Pensando…" : "Preguntar"}</button>
        </div>
        {result && (
          <div className="border border-ms-gray-30 rounded p-3 space-y-2">
            <pre className="text-sm whitespace-pre-wrap text-ms-gray-160" style={{ fontFamily: "inherit" }}>{result.answer}</pre>
            {(result.sources || []).length > 0 && (
              <ul className="text-xs text-ms-gray-110 space-y-0.5">
                {result.sources.map((sc: any, i: number) => <li key={i}>· {sc.subject} <span style={{ color: "#a19f9d" }}>({sc.sim})</span></li>)}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
