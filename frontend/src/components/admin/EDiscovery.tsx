import { useState, useCallback } from "react";
import { api } from "../../api/client";

interface SearchResult {
  mailbox: string;
  folder: string;
  uid: string;
  subject: string;
  from: string;
  to: string;
  date: string;
  message_id: string;
  size: number;
}

interface SearchResponse {
  query: string;
  field: string;
  folder: string;
  total_results: number;
  mailboxes_searched: number;
  mailboxes_with_errors: number;
  results: SearchResult[];
  errors: { mailbox: string; error: string }[] | null;
}

interface MailboxInfo {
  email: string;
  name: string;
  active: boolean;
}

export function EDiscovery() {
  const [query, setQuery] = useState("");
  const [field, setField] = useState("TEXT");
  const [folder, setFolder] = useState("INBOX");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [selectedMailboxes, setSelectedMailboxes] = useState<string[]>([]);
  const [allMailboxes, setAllMailboxes] = useState<MailboxInfo[]>([]);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showMailboxPicker, setShowMailboxPicker] = useState(false);

  const loadMailboxes = useCallback(async () => {
    if (allMailboxes.length > 0) { setShowMailboxPicker(true); return; }
    const data = await api.get<MailboxInfo[]>("/admin/ediscovery/mailboxes");
    if (data) { setAllMailboxes(Array.isArray(data) ? data : []); setShowMailboxPicker(true); }
  }, [allMailboxes]);

  function formatImapDate(isoDate: string): string {
    if (!isoDate) return "";
    const d = new Date(isoDate);
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return `${String(d.getDate()).padStart(2,"0")}-${months[d.getMonth()]}-${d.getFullYear()}`;
  }

  async function handleSearch() {
    if (!query.trim() || query.trim().length < 2) { setError("Escribe al menos 2 caracteres"); return; }
    setLoading(true);
    setError("");
    setResults(null);
    try {
      let url = `/admin/ediscovery/search?q=${encodeURIComponent(query)}&field=${field}&folder=${encodeURIComponent(folder)}`;
      if (dateFrom) url += `&date_from=${formatImapDate(dateFrom)}`;
      if (dateTo) url += `&date_to=${formatImapDate(dateTo)}`;
      if (selectedMailboxes.length > 0) url += `&mailboxes=${selectedMailboxes.join(",")}`;
      const data = await api.get<SearchResponse>(url);
      if (data) setResults(data);
      else setError("Error en la busqueda");
    } catch (e) {
      setError("Error de conexion");
    } finally {
      setLoading(false);
    }
  }

  async function exportMessage(mailbox: string, uid: string) {
    window.open(`/api/admin/ediscovery/export/${encodeURIComponent(mailbox)}?uid=${uid}&folder=${encodeURIComponent(folder)}`, "_blank");
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
  }

  return (
    <div className="p-6 max-w-7xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
          <svg className="w-7 h-7 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 21h7a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v11m0 5l4.879-4.879m0 0a3 3 0 104.243-4.242 3 3 0 00-4.243 4.242z" />
          </svg>
          eDiscovery
        </h1>
        <p className="text-sm text-slate-500 mt-1">Busqueda forense en todos los buzones del servidor</p>
      </div>

      {/* Search Form */}
      <div className="bg-slate-50 rounded-xl border border-slate-200 p-5 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
          <div className="lg:col-span-2">
            <label className="block text-xs font-semibold text-slate-600 mb-1">Buscar</label>
            <input type="text" value={query} onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSearch()}
              placeholder="Texto, email, asunto..."
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-orange-300 focus:border-orange-400 outline-none" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Campo</label>
            <select value={field} onChange={e => setField(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white">
              <option value="TEXT">Todo (texto completo)</option>
              <option value="SUBJECT">Asunto</option>
              <option value="FROM">Remitente</option>
              <option value="TO">Destinatario</option>
              <option value="BODY">Cuerpo</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Carpeta</label>
            <select value={folder} onChange={e => setFolder(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white">
              <option value="INBOX">Bandeja de entrada</option>
              <option value="Sent">Enviados</option>
              <option value="Drafts">Borradores</option>
              <option value="Trash">Papelera</option>
              <option value="Junk">Spam</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Desde</label>
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Hasta</label>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Buzones</label>
            <button onClick={loadMailboxes}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white text-left hover:bg-slate-50">
              {selectedMailboxes.length === 0 ? "Todos los buzones" : `${selectedMailboxes.length} seleccionados`}
            </button>
          </div>
        </div>

        {showMailboxPicker && (
          <div className="mb-4 p-3 bg-white rounded-lg border border-slate-200 max-h-40 overflow-y-auto">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-semibold text-slate-600">Seleccionar buzones:</span>
              <div className="flex gap-2">
                <button onClick={() => setSelectedMailboxes(allMailboxes.filter(m => m.active).map(m => m.email))}
                  className="text-xs text-orange-600 hover:underline">Todos</button>
                <button onClick={() => setSelectedMailboxes([])}
                  className="text-xs text-slate-500 hover:underline">Ninguno</button>
                <button onClick={() => setShowMailboxPicker(false)}
                  className="text-xs text-slate-400 hover:underline">Cerrar</button>
              </div>
            </div>
            {allMailboxes.filter(m => m.active).map(m => (
              <label key={m.email} className="flex items-center gap-2 py-1 text-sm cursor-pointer hover:bg-slate-50 px-1 rounded">
                <input type="checkbox" checked={selectedMailboxes.includes(m.email)}
                  onChange={e => {
                    if (e.target.checked) setSelectedMailboxes([...selectedMailboxes, m.email]);
                    else setSelectedMailboxes(selectedMailboxes.filter(s => s !== m.email));
                  }} className="rounded border-slate-300" />
                <span className="font-medium">{m.name || m.email}</span>
                <span className="text-slate-400 text-xs">{m.email}</span>
              </label>
            ))}
          </div>
        )}

        <button onClick={handleSearch} disabled={loading || !query.trim()}
          className="px-6 py-2.5 bg-orange-600 text-white rounded-lg font-semibold text-sm hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2">
          {loading ? (
            <><svg className="animate-spin w-4 h-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg> Buscando en {selectedMailboxes.length || "todos los"} buzones...</>
          ) : (
            <><svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg> Buscar en el servidor</>
          )}
        </button>
      </div>

      {error && <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm border border-red-200">{error}</div>}

      {/* Results */}
      {results && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <div className="text-sm text-slate-600">
              <span className="font-bold text-slate-800 text-lg">{results.total_results}</span> resultados
              en <span className="font-semibold">{results.mailboxes_searched}</span> buzones
              {results.mailboxes_with_errors > 0 && (
                <span className="text-amber-600 ml-2">({results.mailboxes_with_errors} con error)</span>
              )}
            </div>
          </div>

          {results.total_results === 0 ? (
            <div className="text-center py-12 text-slate-400">
              <svg className="w-16 h-16 mx-auto mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p>No se encontraron resultados para "{results.query}"</p>
            </div>
          ) : (
            <div className="border border-slate-200 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200">
                    <th className="text-left px-4 py-3 font-semibold text-slate-600">Buzon</th>
                    <th className="text-left px-4 py-3 font-semibold text-slate-600">Asunto</th>
                    <th className="text-left px-4 py-3 font-semibold text-slate-600">De</th>
                    <th className="text-left px-4 py-3 font-semibold text-slate-600">Para</th>
                    <th className="text-left px-4 py-3 font-semibold text-slate-600">Fecha</th>
                    <th className="text-right px-4 py-3 font-semibold text-slate-600">Tam.</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {results.results.map((r, i) => (
                    <tr key={`${r.mailbox}-${r.uid}-${i}`}
                      className="border-b border-slate-100 hover:bg-orange-50/50 transition-colors">
                      <td className="px-4 py-2.5">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                          {r.mailbox.split("@")[0]}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 font-medium text-slate-800 max-w-xs truncate">{r.subject || "(sin asunto)"}</td>
                      <td className="px-4 py-2.5 text-slate-600 max-w-[160px] truncate">{r.from}</td>
                      <td className="px-4 py-2.5 text-slate-600 max-w-[160px] truncate">{r.to}</td>
                      <td className="px-4 py-2.5 text-slate-500 whitespace-nowrap text-xs">{r.date?.substring(0, 22)}</td>
                      <td className="px-4 py-2.5 text-right text-slate-400 text-xs whitespace-nowrap">{formatSize(r.size)}</td>
                      <td className="px-4 py-2.5">
                        <button onClick={() => exportMessage(r.mailbox, r.uid)}
                          title="Exportar .eml con cadena de custodia"
                          className="p-1.5 rounded-lg hover:bg-orange-100 text-slate-400 hover:text-orange-600 transition-colors">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {results.errors && results.errors.length > 0 && (
            <details className="mt-4">
              <summary className="text-xs text-amber-600 cursor-pointer">Ver errores ({results.errors.length})</summary>
              <div className="mt-2 p-3 bg-amber-50 rounded-lg text-xs">
                {results.errors.map((e, i) => (
                  <div key={i} className="py-1"><span className="font-mono">{e.mailbox}</span>: {e.error}</div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
