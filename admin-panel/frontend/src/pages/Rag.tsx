import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

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
      <div className="flex justify-end">
        <SectionHelp
          titulo="RAG — Pregúntale a tu correo"
          items={[
            { titulo: "Qué hace esta sección", desc: "Permite hacer preguntas en lenguaje natural sobre el contenido de un buzón: la IA local busca los correos más relevantes (búsqueda semántica) y responde con base en ellos." },
            { titulo: "Dominios habilitados", desc: "El RAG solo funciona para buzones de los dominios que aparezcan como Habilitado. Un clic en la etiqueta alterna entre habilitado y deshabilitado al instante." },
            { titulo: "Indexar bandeja", desc: "Antes de preguntar hay que indexar el buzón: se leen los correos y se convierten en vectores para la búsqueda. Solo se indexan los correos nuevos en cada ejecución." },
            { titulo: "Preguntar", desc: "Escribe el buzón y la pregunta; la IA responde y lista las fuentes (asuntos de correos usados) con su puntuación de similitud." },
            { titulo: "Privacidad", desc: "Todo se procesa con la IA local del servidor: ni los correos ni las preguntas salen a servicios de terceros." },
          ]}
        />
      </div>
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
              <button onClick={() => toggle(d)} title="Habilita o deshabilita el RAG para este dominio. Si está deshabilitado, los buzones de ese dominio no se pueden indexar ni consultar. El cambio se aplica al instante." className="text-xs px-2 py-1 rounded" style={{ background: d.enabled ? "#dff6dd" : "#f3f2f1", color: d.enabled ? "#107c10" : "#605e5c" }}>{d.enabled ? "Habilitado" : "Deshabilitado"}</button>
            </div>
          ))}
          {!doms.length && <div className="text-xs text-ms-gray-110">Sin dominios. Agrega uno abajo.</div>}
        </div>
        <div className="flex gap-2">
          <input value={newDom} onChange={(e) => setNewDom(e.target.value)} placeholder="dominio.com" title="Escribe el dominio de correo (ej. maquita.com.ec) que quieres agregar a la lista del RAG." className="px-3 py-2 border border-ms-gray-30 rounded text-sm flex-1" />
          <button onClick={addDom} title="Agrega el dominio escrito a la lista y lo deja disponible para habilitar el RAG en sus buzones." className="text-white text-sm px-4 py-2 rounded" style={{ backgroundColor: "#0078d4" }}>Agregar</button>
        </div>
      </div>

      <div className="bg-white border border-ms-gray-30 rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-semibold text-ms-gray-160">Probar (indexar + preguntar)</h2>
        <input value={user} onChange={(e) => setUser(e.target.value)} placeholder="buzon@maquita.com.ec" title="Correo del buzón sobre el que quieres indexar y preguntar. Debe pertenecer a un dominio habilitado arriba." className="px-3 py-2 border border-ms-gray-30 rounded text-sm w-full" />
        <div className="flex gap-2 items-center">
          <button onClick={ingest} disabled={busy === "ingest"} title="Lee la bandeja del buzón indicado y la indexa para búsqueda semántica. Solo agrega correos nuevos al índice; no modifica ni borra correos. Puede tardar según el tamaño del buzón." className="text-sm px-3 py-2 rounded border border-ms-gray-30 disabled:opacity-50">{busy === "ingest" ? "Indexando…" : "Indexar bandeja"}</button>
          {ingestMsg && <span className="text-xs text-ms-gray-110">{ingestMsg}</span>}
        </div>
        <div className="flex gap-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="¿Tengo algo pendiente?" title="Pregunta en lenguaje natural sobre el contenido del buzón (ej. ¿tengo facturas pendientes?). Requiere haber indexado antes." className="px-3 py-2 border border-ms-gray-30 rounded text-sm flex-1" />
          <button onClick={ask} disabled={busy === "ask"} title="Envía la pregunta a la IA local: busca los correos más parecidos en el índice y redacta una respuesta citando las fuentes. No modifica el buzón." className="text-white text-sm px-4 py-2 rounded disabled:opacity-50" style={{ backgroundColor: "#0078d4" }}>{busy === "ask" ? "Pensando…" : "Preguntar"}</button>
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
