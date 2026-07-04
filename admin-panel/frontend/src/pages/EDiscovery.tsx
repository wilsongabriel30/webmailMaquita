import { useState, useEffect } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface Mailbox {
  email: string;
  name: string;
  active: boolean;
}

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

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(d: string) {
  if (!d) return "";
  try {
    const date = new Date(d);
    return date.toLocaleString("es-EC", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return d;
  }
}

export function EDiscovery() {
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const [query, setQuery] = useState("");
  const [field, setField] = useState("TEXT");
  const [folder, setFolder] = useState("INBOX");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [limit, setLimit] = useState(50);

  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState<string | null>(null);

  useEffect(() => {
    api.get<Mailbox[]>("/ediscovery/mailboxes").then(setMailboxes).catch(() => {});
  }, []);

  const toggleAll = (on: boolean) => {
    setSelected(on ? new Set(mailboxes.map((m) => m.email)) : new Set());
  };

  const toggle = (email: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(email) ? next.delete(email) : next.add(email);
      return next;
    });
  };

  const search = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    setResults(null);
    try {
      const params = new URLSearchParams({ q: query, field, folder, limit: String(limit) });
      if (selected.size > 0 && selected.size < mailboxes.length) {
        params.set("mailboxes", Array.from(selected).join(","));
      }
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      const data = await api.get<SearchResponse>(`/ediscovery/search?${params}`);
      setResults(data);
    } catch (e: any) {
      setError(e.message || "Error en la búsqueda");
    } finally {
      setLoading(false);
    }
  };

  const exportMsg = async (r: SearchResult) => {
    const key = `${r.mailbox}:${r.uid}`;
    setExporting(key);
    try {
      const token = localStorage.getItem("admin_token");
      const res = await fetch(
        `/api/ediscovery/export/${encodeURIComponent(r.mailbox)}?uid=${r.uid}&folder=${r.folder}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error("Error exportando");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${r.mailbox}_${r.uid}.eml`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert("Error al exportar el mensaje");
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex justify-end">
        <SectionHelp
          titulo="eDiscovery — Búsqueda Forense"
          items={[
            { titulo: "¿Qué es?", desc: "Buscador forense que rastrea correos en todos los buzones del servidor a la vez, usando autenticación administrativa (no necesita las contraseñas de los usuarios)." },
            { titulo: "Formulario de búsqueda", desc: "Escribe el término, elige dónde buscar (todo el mensaje, asunto, remitente, destinatario o cuerpo), la carpeta (entrada, enviados, papelera…) y el límite de resultados por buzón." },
            { titulo: "Filtros de fecha", desc: "«Desde» y «Hasta» acotan la búsqueda a un rango de fechas del correo; déjalos vacíos para buscar sin límite temporal." },
            { titulo: "Selección de buzones", desc: "Por defecto se buscan todos los buzones. Despliega «Seleccionar buzones» para limitar la búsqueda solo a algunos." },
            { titulo: "Exportar evidencia", desc: "El icono de descarga en cada resultado exporta el mensaje como archivo .eml con cadena de custodia (hash SHA256, marcas de tiempo y origen), válido como evidencia." },
            { titulo: "Auditoría", desc: "Cada búsqueda y exportación queda registrada en el log de auditoría con el administrador que la hizo. Úsalo solo para investigaciones legítimas." },
          ]}
        />
      </div>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-800 flex items-center gap-2">
          <svg className="w-6 h-6 text-ms-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          eDiscovery — Búsqueda Forense
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Busque correos electrónicos en todos los buzones del servidor simultáneamente. Cada búsqueda y exportación queda registrada en auditoría.
        </p>
      </div>

      {/* Search Form */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
          {/* Query */}
          <div className="md:col-span-5">
            <label className="block text-xs font-medium text-gray-600 mb-1">Término de búsqueda</label>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && search()}
              placeholder="Buscar en correos..."
              title="Texto a buscar dentro de los correos según el campo elegido en «Buscar en». Pulsa Enter o el botón «Buscar» para lanzar la búsqueda; quedará registrada en auditoría."
              className="w-full px-3 py-2 border rounded-md text-sm focus:ring-2 focus:ring-ms-blue focus:border-ms-blue"
            />
          </div>

          {/* Field */}
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-gray-600 mb-1">Buscar en</label>
            <select value={field} onChange={(e) => setField(e.target.value)} title="Campo del correo donde buscar el término: todo el mensaje (más lento pero completo), solo el asunto, el remitente, el destinatario o solo el cuerpo." className="w-full px-3 py-2 border rounded-md text-sm">
              <option value="TEXT">Todo el mensaje</option>
              <option value="SUBJECT">Asunto</option>
              <option value="FROM">Remitente</option>
              <option value="TO">Destinatario</option>
              <option value="BODY">Cuerpo</option>
            </select>
          </div>

          {/* Folder */}
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-gray-600 mb-1">Carpeta</label>
            <select value={folder} onChange={(e) => setFolder(e.target.value)} title="Carpeta IMAP donde buscar en cada buzón: bandeja de entrada, enviados, borradores, papelera, spam o archivo. Se busca solo en la carpeta elegida." className="w-full px-3 py-2 border rounded-md text-sm">
              <option value="INBOX">Bandeja de entrada</option>
              <option value="Sent">Enviados</option>
              <option value="Drafts">Borradores</option>
              <option value="Trash">Papelera</option>
              <option value="Junk">Spam</option>
              <option value="Archive">Archivo</option>
            </select>
          </div>

          {/* Limit */}
          <div className="md:col-span-1">
            <label className="block text-xs font-medium text-gray-600 mb-1">Límite</label>
            <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} title="Número máximo de resultados a devolver. Un límite bajo hace la búsqueda más rápida; súbelo si sospechas que hay más coincidencias de las mostradas." className="w-full px-3 py-2 border rounded-md text-sm">
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
              <option value={500}>500</option>
            </select>
          </div>

          {/* Search button */}
          <div className="md:col-span-2 flex items-end">
            <button
              onClick={search}
              disabled={loading || !query.trim()}
              title="Lanza la búsqueda en los buzones seleccionados (o en todos si no elegiste ninguno) con los filtros indicados. Puede tardar según la cantidad de buzones; la búsqueda queda registrada en el log de auditoría."
              className="w-full px-4 py-2 bg-ms-blue text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
              )}
              Buscar
            </button>
          </div>
        </div>

        {/* Date range */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4 mt-3">
          <div className="md:col-span-3">
            <label className="block text-xs font-medium text-gray-600 mb-1">Desde</label>
            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} title="Fecha inicial del rango: solo se incluirán correos con fecha igual o posterior a esta. Déjala vacía para no limitar el inicio." className="w-full px-3 py-2 border rounded-md text-sm" />
          </div>
          <div className="md:col-span-3">
            <label className="block text-xs font-medium text-gray-600 mb-1">Hasta</label>
            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} title="Fecha final del rango: solo se incluirán correos con fecha igual o anterior a esta. Déjala vacía para no limitar el final." className="w-full px-3 py-2 border rounded-md text-sm" />
          </div>
        </div>

        {/* Mailbox picker */}
        <details className="mt-4">
          <summary className="text-sm text-ms-blue cursor-pointer hover:underline font-medium">
            Seleccionar buzones ({selected.size === 0 ? "todos" : `${selected.size} de ${mailboxes.length}`})
          </summary>
          <div className="mt-2 border rounded-md p-3 bg-gray-50 max-h-48 overflow-y-auto">
            <div className="flex gap-3 mb-2 pb-2 border-b">
              <button onClick={() => toggleAll(true)} title="Marca todos los buzones del servidor para incluirlos en la búsqueda." className="text-xs text-ms-blue hover:underline">Seleccionar todos</button>
              <button onClick={() => toggleAll(false)} title="Desmarca todos los buzones; sin ninguno marcado la búsqueda se hace igualmente en todos los buzones del servidor." className="text-xs text-red-500 hover:underline">Ninguno</button>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-1">
              {mailboxes.map((m) => (
                <label key={m.email} className="flex items-center gap-2 text-sm py-0.5 cursor-pointer hover:bg-gray-100 px-1 rounded">
                  <input type="checkbox" checked={selected.has(m.email)} onChange={() => toggle(m.email)} title="Incluye o excluye este buzón de la búsqueda. Si ningún buzón queda marcado, se buscará en todos." className="rounded text-ms-blue" />
                  <span className={m.active ? "" : "text-gray-400 line-through"}>{m.email.split("@")[0]}</span>
                </label>
              ))}
            </div>
          </div>
        </details>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">{error}</div>
      )}

      {/* Results */}
      {results && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          {/* Stats bar */}
          <div className="px-5 py-3 border-b bg-gray-50 flex items-center justify-between flex-wrap gap-2">
            <div className="text-sm text-gray-600">
              <strong className="text-gray-800">{results.total_results}</strong> resultados en{" "}
              <strong>{results.mailboxes_searched}</strong> buzones
              {results.mailboxes_with_errors > 0 && (
                <span className="text-amber-600 ml-2">
                  ({results.mailboxes_with_errors} con errores)
                </span>
              )}
            </div>
            <div className="text-xs text-gray-400">
              Campo: {results.field} | Carpeta: {results.folder}
            </div>
          </div>

          {/* Errors detail */}
          {results.errors && results.errors.length > 0 && (
            <div className="px-5 py-2 bg-amber-50 border-b text-xs text-amber-700">
              Errores: {results.errors.map((e) => `${e.mailbox.split("@")[0]}: ${e.error}`).join(" | ")}
            </div>
          )}

          {/* Table */}
          {results.results.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50/50 text-left text-xs text-gray-500 uppercase tracking-wider">
                    <th className="px-4 py-2.5">Buzón</th>
                    <th className="px-4 py-2.5">Asunto</th>
                    <th className="px-4 py-2.5">De</th>
                    <th className="px-4 py-2.5">Para</th>
                    <th className="px-4 py-2.5">Fecha</th>
                    <th className="px-4 py-2.5 text-right">Tamaño</th>
                    <th className="px-4 py-2.5 w-20"></th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {results.results.map((r, i) => (
                    <tr key={`${r.mailbox}-${r.uid}-${i}`} className="hover:bg-blue-50/30 transition-colors">
                      <td className="px-4 py-2.5">
                        <span className="inline-block px-2 py-0.5 bg-ms-blue/10 text-ms-blue text-xs rounded-full font-medium">
                          {r.mailbox.split("@")[0]}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 font-medium text-gray-800 max-w-xs truncate" title={r.subject}>
                        {r.subject || "(sin asunto)"}
                      </td>
                      <td className="px-4 py-2.5 text-gray-600 max-w-[180px] truncate" title={r.from}>{r.from}</td>
                      <td className="px-4 py-2.5 text-gray-600 max-w-[180px] truncate" title={r.to}>{r.to}</td>
                      <td className="px-4 py-2.5 text-gray-500 text-xs whitespace-nowrap">{formatDate(r.date)}</td>
                      <td className="px-4 py-2.5 text-gray-500 text-xs text-right">{formatSize(r.size)}</td>
                      <td className="px-4 py-2.5">
                        <button
                          onClick={() => exportMsg(r)}
                          disabled={exporting === `${r.mailbox}:${r.uid}`}
                          className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-ms-blue transition-colors"
                          title="Exportar como .eml (con cadena de custodia)"
                        >
                          {exporting === `${r.mailbox}:${r.uid}` ? (
                            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                          ) : (
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                          )}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="px-5 py-12 text-center text-gray-400">
              <svg className="w-12 h-12 mx-auto mb-3 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
              No se encontraron resultados para "{results.query}"
            </div>
          )}
        </div>
      )}

      {/* Info box */}
      {!results && !loading && (
        <div className="bg-blue-50 rounded-lg border border-blue-200 p-5 text-sm text-blue-800">
          <h3 className="font-semibold mb-2">¿Qué es eDiscovery?</h3>
          <ul className="space-y-1.5 list-disc list-inside text-blue-700">
            <li>Busque correos electrónicos en <strong>todos los buzones</strong> del servidor simultáneamente</li>
            <li>No necesita la contraseña de cada usuario — usa autenticación administrativa</li>
            <li>Exporte mensajes como archivos <strong>.eml con cadena de custodia</strong> (hash SHA256, timestamps, origen)</li>
            <li>Filtre por remitente, destinatario, asunto, fechas y carpetas</li>
            <li>Cada búsqueda y exportación queda registrada en el <strong>log de auditoría</strong></li>
            <li>Útil para investigaciones internas, cumplimiento normativo y soporte técnico</li>
          </ul>
        </div>
      )}
    </div>
  );
}
