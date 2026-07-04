import { useEffect, useState, useRef } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface SpamRow { time: string; ip: string; action: string; score: number; from: string; rcpt: string; subject: string }
interface Suggestion { username: string; name: string }

export function Quarantine() {
  const [history, setHistory] = useState<SpamRow[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [junkUser, setJunkUser] = useState("");
  const [junkMsgs, setJunkMsgs] = useState<any[]>([]);
  const [tab, setTab] = useState<"history" | "junk">("history");
  const [loading, setLoading] = useState(false);
  const [histLoading, setHistLoading] = useState(true);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSugg, setShowSugg] = useState(false);
  const [error, setError] = useState("");
  const timerRef = useRef<any>(null);

  useEffect(() => {
    api.get<{ rows: SpamRow[] }>("/quarantine/history?limit=100").then((d) => setHistory(d.rows || [])).catch(() => {}).finally(() => setHistLoading(false));
    api.get("/quarantine/stats").then(setStats).catch(() => {});
  }, []);

  const searchUsers = (q: string) => {
    setJunkUser(q);
    setError("");
    if (timerRef.current) clearTimeout(timerRef.current);
    if (q.length < 2) { setSuggestions([]); setShowSugg(false); return; }
    timerRef.current = setTimeout(() => {
      api.get<Suggestion[]>(`/mailboxes/search/autocomplete?q=${encodeURIComponent(q)}&limit=8`)
        .then((d) => { setSuggestions(d); setShowSugg(d.length > 0); })
        .catch(() => {});
    }, 300);
  };

  const selectUser = (u: string) => {
    setJunkUser(u);
    setShowSugg(false);
    setSuggestions([]);
  };

  const loadJunk = () => {
    if (!junkUser) return;
    setLoading(true);
    setError("");
    setJunkMsgs([]);
    api.get(`/quarantine/junk/${encodeURIComponent(junkUser)}`)
      .then((d: any) => {
        setJunkMsgs(d.messages || []);
        if ((d.messages || []).length === 0) setError("No se encontraron mensajes en carpetas de spam para este usuario.");
      })
      .catch((e) => setError(e.message || "Error al buscar"))
      .finally(() => setLoading(false));
  };

  const release = async (msg: any) => {
    if (!confirm(`Liberar este correo a la bandeja de ${junkUser} y marcar al remitente como \"No es spam\" (siempre llegara)?`)) return;
    const r: any = await api.post("/quarantine/release", { username: junkUser, mailbox_guid: msg.mailbox_guid, uid: msg.uid, sender: msg.from, whitelist: true });
    if (r && r.whitelisted) alert(`Liberado. \"${r.whitelisted}\" quedo en lista blanca: sus correos siempre llegaran.`);
    loadJunk();
  };

  const actionColors: Record<string, string> = {
    reject: "bg-red-50 text-ms-red border-ms-red/20",
    "soft reject": "bg-red-50 text-ms-red border-ms-red/20",
    "add header": "bg-yellow-50 text-yellow-700 border-yellow-200",
    greylist: "bg-purple-50 text-ms-purple border-purple-200",
    "no action": "bg-green-50 text-ms-green border-green-200",
  };

  return (
    <div className="p-6 space-y-5">
      <div className="flex justify-end">
        <SectionHelp
          titulo="Cuarentena y Spam"
          items={[
            { titulo: "Para qué sirve", desc: "Gestiona el correo clasificado como spam: revisa qué decidió el filtro Rspamd y recupera correos legítimos que cayeron en la carpeta de spam de un usuario." },
            { titulo: "Tarjetas de estadísticas", desc: "Conteo de correos por acción de Rspamd: reject (rechazado), add header (marcado como spam), greylist (pospuesto), no action (aceptado limpio)." },
            { titulo: "Pestaña Historial Rspamd", desc: "Últimos correos analizados por el filtro, con IP de origen, remitente, asunto, puntaje (score) y acción tomada. A mayor score, más indicios de spam. Solo lectura." },
            { titulo: "Pestaña Carpeta Spam de Usuario", desc: "Busque un usuario (autocompleta con nombre o email) y pulse Ver Spam para listar los correos de sus carpetas de spam/junk." },
            { titulo: "Botón Liberar", desc: "Mueve el correo a la bandeja de entrada del usuario y pone al remitente en lista blanca (sus próximos correos siempre llegarán). Verificar antes que no sea malicioso. Se registra en auditoría." },
          ]}
        />
      </div>
      <h1 className="text-xl font-semibold text-ms-gray-130" title="Gestion de correos en cuarentena y spam. Permite ver historial de Rspamd y gestionar carpetas de spam de usuarios.">Cuarentena y Spam</h1>

      {/* Stats */}
      {stats?.actions && (
        <div className="grid grid-cols-5 gap-2">
          {Object.entries(stats.actions as Record<string, number>).map(([k, v]) => (
            <div key={k} className={`rounded border p-3 text-center ${actionColors[k] || "bg-ms-gray-10 border-ms-gray-30"}`} title={`Estadistica de cuarentena: ${k}. Solo lectura.`}>
              <p className="text-[10px] font-medium uppercase">{k}</p>
              <p className="text-lg font-bold">{v}</p>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-ms-gray-30">
        <button onClick={() => setTab("history")}
          title="Muestra el historial de correos procesados por Rspamd. Solo lectura, no modifica nada."
          className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === "history" ? "border-ms-blue text-ms-blue" : "border-transparent text-ms-gray-90 hover:text-ms-gray-130"}`}>
          Historial Rspamd
        </button>
        <button onClick={() => setTab("junk")}
          title="Permite buscar y gestionar correos en la carpeta de spam de un usuario especifico."
          className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === "junk" ? "border-ms-blue text-ms-blue" : "border-transparent text-ms-gray-90 hover:text-ms-gray-130"}`}>
          Carpeta Spam de Usuario
        </button>
      </div>

      {tab === "junk" && (
        <div className="relative">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                value={junkUser}
                onChange={(e) => searchUsers(e.target.value)}
                onFocus={() => suggestions.length > 0 && setShowSugg(true)}
                onKeyDown={(e) => e.key === "Enter" && (setShowSugg(false), loadJunk())}
                placeholder="Escriba nombre o email del usuario..."
                title="Escriba el nombre o email del usuario para buscar sus correos en spam."
                className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-130 focus:outline-none focus:border-ms-blue focus:ring-1 focus:ring-ms-blue"
              />
              {showSugg && suggestions.length > 0 && (
                <div className="absolute z-10 w-full mt-1 bg-white border border-ms-gray-30 rounded shadow-lg max-h-48 overflow-auto">
                  {suggestions.map((s) => (
                    <button
                      key={s.username}
                      onClick={() => selectUser(s.username)}
                      title={`Seleccionar usuario: ${s.username}`}
                      className="w-full text-left px-3 py-2 hover:bg-ms-blue-lighter text-sm flex items-center justify-between"
                    >
                      <span className="font-medium text-ms-gray-130">{s.username}</span>
                      {s.name && <span className="text-ms-gray-60 text-xs">{s.name}</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button onClick={loadJunk} disabled={loading || !junkUser}
              title="Muestra los correos en cuarentena/spam del usuario. Solo lectura."
              className="px-5 py-2 bg-ms-blue text-white rounded text-sm font-medium hover:bg-ms-blue-dark disabled:opacity-50">
              {loading ? "Buscando..." : "Ver Spam"}
            </button>
          </div>
          {error && <p className="mt-2 text-sm text-ms-red">{error}</p>}
        </div>
      )}

      {tab === "junk" && junkMsgs.length > 0 && (
        <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
          <div className="px-4 py-2.5 bg-ms-gray-10 border-b border-ms-gray-30 flex items-center justify-between">
            <span className="text-sm font-medium text-ms-gray-130">{junkMsgs.length} mensajes en spam</span>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-ms-gray-20 border-b border-ms-gray-30">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-ms-gray-90 text-xs">De</th>
                <th className="text-left px-4 py-2 font-medium text-ms-gray-90 text-xs">Asunto</th>
                <th className="text-left px-4 py-2 font-medium text-ms-gray-90 text-xs">Fecha</th>
                <th className="text-left px-4 py-2 font-medium text-ms-gray-90 text-xs">Carpeta</th>
                <th className="text-right px-4 py-2 font-medium text-ms-gray-90 text-xs">Accion</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ms-gray-30">
              {junkMsgs.map((m, i) => (
                <tr key={i} className="hover:bg-ms-blue-lighter/50">
                  <td className="px-4 py-2 text-xs text-ms-gray-130">{m.from || "-"}</td>
                  <td className="px-4 py-2 text-xs truncate max-w-[250px] text-ms-gray-130">{m.subject || "-"}</td>
                  <td className="px-4 py-2 text-xs text-ms-gray-60">{m.date || "-"}</td>
                  <td className="px-4 py-2 text-xs"><span className="px-1.5 py-0.5 bg-ms-gray-20 rounded text-ms-gray-90">{m.spam_folder}</span></td>
                  <td className="px-4 py-2 text-right">
                    <button onClick={() => release(m)} title="Mover a bandeja de entrada del usuario. Verificar que no sea malicioso. Se registra en auditoria." className="px-3 py-1 bg-ms-green text-white rounded text-xs hover:bg-green-700">Liberar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "history" && (
        <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
          {histLoading ? (
            <div className="p-8 text-center text-ms-gray-60 text-sm">
              <div className="animate-spin w-6 h-6 border-2 border-ms-blue border-t-transparent rounded-full mx-auto mb-2" />
              Cargando historial...
            </div>
          ) : history.length === 0 ? (
            <div className="p-8 text-center text-ms-gray-60 text-sm">
              No hay registros de Rspamd disponibles.
            </div>
          ) : (
          <table className="w-full text-sm">
            <thead className="bg-ms-gray-20 border-b border-ms-gray-30">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-ms-gray-90 text-xs">Fecha</th>
                <th className="text-left px-4 py-2 font-medium text-ms-gray-90 text-xs">IP Origen</th>
                <th className="text-left px-4 py-2 font-medium text-ms-gray-90 text-xs">De</th>
                <th className="text-left px-4 py-2 font-medium text-ms-gray-90 text-xs">Para</th>
                <th className="text-left px-4 py-2 font-medium text-ms-gray-90 text-xs">Asunto</th>
                <th className="text-center px-4 py-2 font-medium text-ms-gray-90 text-xs">Score</th>
                <th className="text-center px-4 py-2 font-medium text-ms-gray-90 text-xs">Acción</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ms-gray-30">
              {history.map((r, i) => (
                <tr key={i} className="hover:bg-ms-blue-lighter/50">
                  <td className="px-4 py-2 text-xs text-ms-gray-60 whitespace-nowrap">{r.time}</td>
                  <td className="px-4 py-2 text-xs text-ms-gray-60 font-mono">{r.ip || "-"}</td>
                  <td className="px-4 py-2 text-xs truncate max-w-[130px] text-ms-gray-130" title={r.from || "Rspamd no registra remitente a nivel SMTP"}>{r.from || <span className="text-ms-gray-60 italic" title="Rspamd no registra este dato a nivel de cabecera SMTP">—</span>}</td>
                  <td className="px-4 py-2 text-xs truncate max-w-[130px] text-ms-gray-130" title={r.rcpt || "Rspamd no registra destinatario a nivel SMTP"}>{r.rcpt || <span className="text-ms-gray-60 italic" title="Rspamd no registra este dato a nivel de cabecera SMTP">—</span>}</td>
                  <td className="px-4 py-2 text-xs truncate max-w-[200px] text-ms-gray-130">{r.subject || "-"}</td>
                  <td className="px-4 py-2 text-center text-xs font-mono">{r.score?.toFixed(1)}</td>
                  <td className="px-4 py-2 text-center">
                    <span className={`px-2 py-0.5 rounded border text-[10px] font-medium ${actionColors[r.action] || "bg-ms-gray-10 border-ms-gray-30"}`}>{r.action}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          )}
        </div>
      )}
    </div>
  );
}
