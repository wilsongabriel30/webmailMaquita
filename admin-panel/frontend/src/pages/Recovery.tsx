import { useState, useRef } from "react";
import { api } from "../api/client";

interface Suggestion { username: string; name: string }

export function Recovery() {
  const [username, setUsername] = useState("");
  const [messages, setMessages] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSugg, setShowSugg] = useState(false);
  const timerRef = useRef<any>(null);

  const searchUsers = (q: string) => {
    setUsername(q);
    if (timerRef.current) clearTimeout(timerRef.current);
    if (q.length < 2) { setSuggestions([]); setShowSugg(false); return; }
    timerRef.current = setTimeout(() => {
      api.get<Suggestion[]>(`/mailboxes/search/autocomplete?q=${encodeURIComponent(q)}&limit=8`)
        .then((d) => { setSuggestions(d); setShowSugg(d.length > 0); })
        .catch(() => {});
    }, 300);
  };

  const load = () => {
    if (!username) return;
    setLoading(true); setShowSugg(false);
    api.get(`/recovery/trash/${username}`).then((d: any) => { setMessages(d.messages || []); setSelected(new Set()); }).catch(() => {}).finally(() => setLoading(false));
  };

  const toggle = (i: number) => { const s = new Set(selected); s.has(i) ? s.delete(i) : s.add(i); setSelected(s); };
  const selectAll = () => { selected.size === messages.length ? setSelected(new Set()) : setSelected(new Set(messages.map((_, i) => i))); };

  const restoreSelected = async () => {
    const msgs = Array.from(selected).map((i) => messages[i]);
    if (msgs.length === 0) return;
    if (!confirm(`Restaurar ${msgs.length} correo(s) a la bandeja de entrada del usuario? Los correos se moveran de la papelera. Se registra en auditoria.`)) return;
    const res: any = await api.post("/recovery/restore-bulk", { username, messages: msgs, destination: "INBOX" });
    alert(`Restaurados: ${res.restored}, Errores: ${res.errors}`);
    load();
  };

  const restoreOne = async (msg: any) => {
    if (!confirm("Restaurar este correo a la bandeja de entrada del usuario? El correo se movera de la papelera. Se registra en auditoria.")) return;
    await api.post("/recovery/restore", { username, mailbox_guid: msg.mailbox_guid, uid: msg.uid, destination: "INBOX" });
    load();
  };

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-xl font-semibold text-ms-gray-130" title="Permite recuperar correos eliminados (en papelera) de los usuarios. Los correos se restauran a la bandeja de entrada.">Recuperación de correos eliminados</h1>

      <div className="flex gap-2 relative">
        <div className="relative flex-1">
          <input value={username} onChange={(e) => searchUsers(e.target.value)}
            onFocus={() => suggestions.length > 0 && setShowSugg(true)}
            onKeyDown={(e) => e.key === "Enter" && (setShowSugg(false), load())}
            placeholder="Escriba nombre o email del usuario..."
            title="Escriba el nombre o email del usuario para buscar correos en su papelera."
            className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue focus:ring-1 focus:ring-ms-blue" />
          {showSugg && suggestions.length > 0 && (
            <div className="absolute z-10 w-full mt-1 bg-white border border-ms-gray-30 rounded shadow-lg max-h-48 overflow-auto">
              {suggestions.map((s) => (
                <button key={s.username} onClick={() => { setUsername(s.username); setShowSugg(false); }}
                  title={`Seleccionar usuario: ${s.username}`}
                  className="w-full text-left px-3 py-2 hover:bg-ms-blue-lighter text-sm flex justify-between">
                  <span className="font-medium text-ms-gray-130">{s.username}</span>
                  {s.name && <span className="text-ms-gray-60 text-xs">{s.name}</span>}
                </button>
              ))}
            </div>
          )}
        </div>
        <button onClick={load} disabled={loading} title="Busca correos en la papelera del usuario. Solo lectura, no modifica nada." className="px-5 py-2 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark disabled:opacity-50">
          {loading ? "Buscando..." : "Buscar en papelera"}
        </button>
      </div>

      {messages.length > 0 && (
        <>
          <div className="flex items-center justify-between">
            <span className="text-sm text-ms-gray-90">{messages.length} mensajes en papelera</span>
            <div className="flex gap-2">
              <button onClick={selectAll} title="Seleccionar o deseleccionar todos los correos de la lista." className="px-3 py-1.5 border border-ms-gray-40 rounded text-xs text-ms-gray-130 hover:bg-ms-gray-20">
                {selected.size === messages.length ? "Deseleccionar" : "Seleccionar"} todos
              </button>
              {selected.size > 0 && (
                <button onClick={restoreSelected} title={`ATENCION: Restaurara ${selected.size} correo(s) a la bandeja de entrada del usuario. Los correos se moveran de la papelera. Se registra en auditoria.`} className="px-4 py-1.5 bg-ms-green text-white rounded text-xs font-medium hover:bg-green-700">
                  Restaurar {selected.size} seleccionados
                </button>
              )}
            </div>
          </div>
          <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-ms-gray-20 border-b border-ms-gray-30"><tr>
                <th className="p-2.5 w-10"><input type="checkbox" checked={selected.size === messages.length} onChange={selectAll} title="Seleccionar o deseleccionar todos los correos." className="accent-ms-blue" /></th>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">De</th>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Asunto</th>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Fecha</th>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Carpeta</th>
                <th className="text-right px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Accion</th>
              </tr></thead>
              <tbody className="divide-y divide-ms-gray-30">
                {messages.map((m, i) => (
                  <tr key={i} className={`hover:bg-ms-blue-lighter/50 ${selected.has(i) ? "bg-ms-blue-lighter" : ""}`}>
                    <td className="p-2.5"><input type="checkbox" checked={selected.has(i)} onChange={() => toggle(i)} title="Seleccionar este correo para restauracion masiva." className="accent-ms-blue" /></td>
                    <td className="px-4 py-2.5 text-xs text-ms-gray-130">{m.from || "-"}</td>
                    <td className="px-4 py-2.5 text-xs truncate max-w-[250px] text-ms-gray-130">{m.subject || "-"}</td>
                    <td className="px-4 py-2.5 text-xs text-ms-gray-60">{m.date || "-"}</td>
                    <td className="px-4 py-2.5 text-xs"><span className="px-1.5 py-0.5 bg-ms-gray-20 rounded">{m.trash_folder}</span></td>
                    <td className="px-4 py-2.5 text-right"><button onClick={() => restoreOne(m)} title="Restaura este correo a la bandeja de entrada del usuario. Se movera de la papelera. Se registra en auditoria." className="px-3 py-1 bg-ms-green text-white rounded text-xs hover:bg-green-700">Restaurar</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {!loading && messages.length === 0 && username && (
        <div className="bg-white rounded border border-ms-gray-30 p-12 text-center text-ms-gray-60">Sin mensajes en papelera para {username}</div>
      )}
    </div>
  );
}
