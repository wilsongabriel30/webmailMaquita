import { useState, useRef, useEffect, useCallback } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface Folder { name: string; messages: number; unseen: number; recent: number }
interface Msg { mailbox_guid: string; uid: string; from: string; to: string; subject: string; date: string; flags: string; folder: string; mailbox: string }
interface Suggestion { username: string; name: string }

const PAGE_SIZE = 50;

export function MailViewer() {
  const [username, setUsername] = useState("");
  const [folders, setFolders] = useState<Folder[]>([]);
  const [selectedFolder, setSelectedFolder] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [selectedMsg, setSelectedMsg] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [searchQ, setSearchQ] = useState("");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSugg, setShowSugg] = useState(false);
  const [quota, setQuota] = useState<any>(null);
  const [hasMore, setHasMore] = useState(false);
  const [totalMsgs, setTotalMsgs] = useState(0);
  const [currentOffset, setCurrentOffset] = useState(0);
  const timerRef = useRef<any>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const msgListRef = useRef<HTMLDivElement>(null);
  const folderRef = useRef("");
  const userRef = useRef("");

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

  const openMailbox = async (user?: string) => {
    const u = user || username;
    if (!u) return;
    setUsername(u);
    userRef.current = u;
    setShowSugg(false);
    setLoading(true);
    setFolders([]); setMessages([]); setSelectedMsg(null); setSelectedFolder("");
    setHasMore(false); setTotalMsgs(0); setCurrentOffset(0);
    folderRef.current = "";
    try {
      const res: any = await api.get(`/mailviewer/folders/${encodeURIComponent(u)}`);
      setFolders(res.folders || []);
      const q: any = await api.get(`/mailviewer/quota/${encodeURIComponent(u)}`);
      setQuota(q.quota);
    } catch { }
    setLoading(false);
  };

  const openFolder = async (folder: string) => {
    setSelectedFolder(folder);
    folderRef.current = folder;
    setSelectedMsg(null);
    setMessages([]);
    setCurrentOffset(0);
    setHasMore(false);
    setTotalMsgs(0);
    setLoading(true);
    try {
      const res: any = await api.get(
        `/mailviewer/messages/${encodeURIComponent(userRef.current)}?folder=${encodeURIComponent(folder)}&limit=${PAGE_SIZE}&offset=0`
      );
      const msgs = res.messages || [];
      setMessages(msgs);
      setTotalMsgs(res.total || 0);
      setHasMore(res.has_more || false);
      setCurrentOffset(msgs.length);
    } catch { }
    setLoading(false);
  };

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore || !folderRef.current) return;
    setLoadingMore(true);
    try {
      const res: any = await api.get(
        `/mailviewer/messages/${encodeURIComponent(userRef.current)}?folder=${encodeURIComponent(folderRef.current)}&limit=${PAGE_SIZE}&offset=${currentOffset}`
      );
      const newMsgs = res.messages || [];
      if (newMsgs.length > 0) {
        setMessages(prev => [...prev, ...newMsgs]);
        setCurrentOffset(prev => prev + newMsgs.length);
      }
      setHasMore(res.has_more || false);
    } catch { }
    setLoadingMore(false);
  }, [loadingMore, hasMore, currentOffset]);

  // IntersectionObserver for infinite scroll
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          loadMore();
        }
      },
      { root: msgListRef.current, threshold: 0.1 }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [loadMore]);

  const readMessage = async (msg: Msg) => {
    try {
      const res: any = await api.get(`/mailviewer/message/${encodeURIComponent(username)}?mailbox_guid=${msg.mailbox_guid}&uid=${msg.uid}`);
      setSelectedMsg({ ...res, _guid: msg.mailbox_guid, _uid: msg.uid });
    } catch { }
  };

  const searchMail = async () => {
    if (!searchQ || !username) return;
    setLoading(true);
    setHasMore(false);
    const folder = selectedFolder ? `&folder=${encodeURIComponent(selectedFolder)}` : "";
    try {
      const res: any = await api.get(`/mailviewer/search/${encodeURIComponent(username)}?q=${encodeURIComponent(searchQ)}${folder}`);
      setMessages(res.messages || []);
      setTotalMsgs(res.messages?.length || 0);
    } catch { }
    setLoading(false);
  };

  const moveMsg = async (dest: string) => {
    if (!selectedMsg?._guid || !selectedMsg?._uid) return;
    await api.post("/mailviewer/move", { username, mailbox_guid: selectedMsg._guid, uid: selectedMsg._uid, destination: dest });
    openFolder(selectedFolder);
    setSelectedMsg(null);
  };

  const formatBytes = (b: number) => b > 1073741824 ? `${(b / 1073741824).toFixed(1)} GB` : `${(b / 1048576).toFixed(0)} MB`;

  return (
    <div className="p-6 space-y-4">
      <div className="flex justify-end">
        <SectionHelp
          titulo="Visor de buzones"
          items={[
            { titulo: "Qué hace esta sección", desc: "Permite al administrador abrir cualquier buzón del servidor y revisar sus carpetas y correos en modo solo lectura, por ejemplo para soporte o auditoría." },
            { titulo: "Buscar y abrir buzón", desc: "Escribe el nombre o correo del usuario (con autocompletado) y pulsa Abrir buzón para cargar sus carpetas y su cuota de espacio." },
            { titulo: "Barra de cuota", desc: "Muestra el espacio usado del buzón frente a su límite; cambia a amarillo sobre 60% y a rojo sobre 80% de uso." },
            { titulo: "Carpetas y mensajes", desc: "La columna izquierda lista las carpetas (con no leídos y total); al abrir una carpeta se cargan los mensajes de 50 en 50 y al bajar se cargan más automáticamente." },
            { titulo: "Buscar en el correo", desc: "El cuadro Buscar filtra por texto dentro del buzón (en la carpeta seleccionada, o en todo el buzón si no hay carpeta elegida)." },
            { titulo: "Solo lectura", desc: "Abrir un mensaje muestra sus cabeceras y cuerpo sin marcarlo como leído: nada de lo que hagas aquí modifica el buzón del usuario." },
          ]}
        />
      </div>
      <h1 className="text-xl font-semibold text-ms-gray-130">Visor de buzones</h1>

      {/* User search */}
      <div className="flex gap-2 relative">
        <div className="relative flex-1">
          <input value={username} onChange={(e) => searchUsers(e.target.value)}
            onFocus={() => suggestions.length > 0 && setShowSugg(true)}
            onKeyDown={(e) => e.key === "Enter" && (setShowSugg(false), openMailbox())}
            placeholder="Escriba nombre o email del usuario..."
            title="Escribe el nombre o email del usuario cuyo buzón deseas consultar. Autocompletado disponible."
            className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue focus:ring-1 focus:ring-ms-blue" />
          {showSugg && suggestions.length > 0 && (
            <div className="absolute z-10 w-full mt-1 bg-white border border-ms-gray-30 rounded shadow-lg max-h-48 overflow-auto">
              {suggestions.map((s) => (
                <button key={s.username} onClick={() => { openMailbox(s.username); }}
                  title={`Seleccionar ${s.username} y abrir su buzón. Solo lectura, no modifica nada.`}
                  className="w-full text-left px-3 py-2 hover:bg-ms-blue-lighter text-sm flex justify-between">
                  <span className="font-medium">{s.username}</span>
                  {s.name && <span className="text-ms-gray-60 text-xs">{s.name}</span>}
                </button>
              ))}
            </div>
          )}
        </div>
        <button onClick={() => openMailbox()} disabled={loading}
          title="Abre el buzón del usuario para ver sus carpetas y correos. Solo lectura, no modifica nada."
          className="px-5 py-2 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark disabled:opacity-50">
          {loading ? "..." : "Abrir buzón"}
        </button>
      </div>

      {/* Quota bar */}
      {quota && (
        <div className="bg-white rounded border border-ms-gray-30 p-3 flex items-center gap-4" title="Muestra el espacio utilizado del buzón del usuario. Solo informativo.">
          <span className="text-xs text-ms-gray-90">Cuota:</span>
          <div className="flex-1 bg-ms-gray-30 rounded-full h-2.5">
            <div className={`h-2.5 rounded-full ${quota.percent > 80 ? "bg-ms-red" : quota.percent > 60 ? "bg-ms-yellow" : "bg-ms-green"}`} style={{ width: `${Math.min(quota.percent, 100)}%` }} />
          </div>
          <span className="text-xs text-ms-gray-130 font-medium">{formatBytes(quota.used_bytes)}{quota.limit_bytes > 0 ? ` / ${formatBytes(quota.limit_bytes)} (${quota.percent}%)` : ""}</span>
          <span className="text-xs text-ms-gray-60">{quota.messages} msgs</span>
        </div>
      )}

      {folders.length > 0 && (
        <div className="grid grid-cols-12 gap-4" style={{ height: "calc(100vh - 280px)" }}>
          {/* Folder list */}
          <div className="col-span-3 bg-white rounded border border-ms-gray-30 overflow-auto">
            <div className="px-3 py-2.5 bg-ms-gray-20 border-b border-ms-gray-30 sticky top-0">
              <span className="text-xs font-semibold text-ms-gray-130">Carpetas</span>
            </div>
            {folders.map((f) => (
              <button key={f.name} onClick={() => openFolder(f.name)}
                title="Abre esta carpeta para ver los mensajes. Solo lectura."
                className={`w-full text-left px-3 py-2 text-xs border-b border-ms-gray-30 hover:bg-ms-blue-lighter/50 flex items-center justify-between ${selectedFolder === f.name ? "bg-ms-blue-lighter border-l-2 border-l-ms-blue" : ""}`}>
                <span className={`truncate ${f.unseen > 0 ? "font-semibold text-ms-gray-130" : "text-ms-gray-90"}`}>{f.name}</span>
                <div className="flex gap-1 shrink-0 ml-1">
                  {f.unseen > 0 && <span className="text-[9px] px-1 py-0.5 bg-ms-blue text-white rounded-full">{f.unseen}</span>}
                  <span className="text-[9px] text-ms-gray-60">{f.messages}</span>
                </div>
              </button>
            ))}
          </div>

          {/* Messages list */}
          <div ref={msgListRef} className="col-span-4 bg-white rounded border border-ms-gray-30 overflow-auto">
            <div className="px-3 py-2 bg-ms-gray-20 border-b border-ms-gray-30 sticky top-0 z-10 flex gap-1">
              <input value={searchQ} onChange={(e) => setSearchQ(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && searchMail()}
                placeholder="Buscar..."
                title="Busca en los correos del usuario. Solo lectura, no modifica nada."
                className="flex-1 px-2 py-1 border border-ms-gray-40 rounded text-xs focus:outline-none focus:border-ms-blue" />
              <button onClick={searchMail}
                title="Busca en los correos del usuario. Solo lectura, no modifica nada."
                className="px-2 py-1 bg-ms-blue text-white rounded text-xs">Buscar</button>
            </div>
            {/* Message count indicator */}
            {selectedFolder && totalMsgs > 0 && (
              <div className="px-3 py-1.5 bg-ms-gray-10 border-b border-ms-gray-30 sticky top-[37px] z-10">
                <span className="text-[10px] text-ms-gray-60">
                  Mostrando {messages.length} de {totalMsgs} mensajes
                  {hasMore && " — baja para cargar mas"}
                </span>
              </div>
            )}
            {messages.length === 0 && !loading && (
              <div className="p-6 text-center text-ms-gray-60 text-xs">
                {selectedFolder ? "No hay mensajes" : "Selecciona una carpeta"}
              </div>
            )}
            {loading && messages.length === 0 && (
              <div className="p-6 text-center text-ms-gray-60 text-xs">
                <div className="inline-block w-5 h-5 border-2 border-ms-blue border-t-transparent rounded-full animate-spin mb-2" />
                <p>Cargando mensajes...</p>
              </div>
            )}
            {messages.map((m, i) => (
              <button key={`${m.uid}-${i}`} onClick={() => { readMessage(m); }}
                title="Abre el mensaje para leerlo. No marca como leido ni modifica el buzón."
                className={`w-full text-left p-2.5 border-b border-ms-gray-30 hover:bg-ms-blue-lighter/50 ${selectedMsg?._uid === m.uid ? "bg-ms-blue-lighter" : ""}`}>
                <div className="flex justify-between items-start">
                  <span className="text-xs font-medium text-ms-gray-130 truncate flex-1">{m.from || "-"}</span>
                  <span className="text-[9px] text-ms-gray-60 shrink-0 ml-1">{m.date?.slice(0, 16) || ""}</span>
                </div>
                <p className="text-xs text-ms-gray-130 truncate mt-0.5">{m.subject || "(Sin asunto)"}</p>
              </button>
            ))}
            {/* Sentinel for infinite scroll */}
            <div ref={sentinelRef} className="h-1" />
            {loadingMore && (
              <div className="p-4 text-center">
                <div className="inline-block w-5 h-5 border-2 border-ms-blue border-t-transparent rounded-full animate-spin mb-1" />
                <p className="text-[10px] text-ms-gray-60">Cargando mas mensajes...</p>
              </div>
            )}
            {!hasMore && messages.length > 0 && !loadingMore && (
              <div className="p-3 text-center text-[10px] text-ms-gray-50">
                — Fin de los mensajes ({messages.length} de {totalMsgs}) —
              </div>
            )}
          </div>

          {/* Message viewer */}
          <div className="col-span-5 bg-white rounded border border-ms-gray-30 overflow-auto">
            {selectedMsg?.headers ? (
              <div>
                <div className="p-4 border-b border-ms-gray-30 bg-ms-gray-10">
                  <h3 className="text-sm font-semibold text-ms-gray-130 mb-2">{selectedMsg.headers.subject || "(Sin asunto)"}</h3>
                  <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                    <span className="text-ms-gray-60">De:</span><span className="text-ms-gray-130">{selectedMsg.headers.from || "-"}</span>
                    <span className="text-ms-gray-60">Para:</span><span className="text-ms-gray-130">{selectedMsg.headers.to || "-"}</span>
                    {selectedMsg.headers.cc && <><span className="text-ms-gray-60">CC:</span><span className="text-ms-gray-130">{selectedMsg.headers.cc}</span></>}
                    <span className="text-ms-gray-60">Fecha:</span><span className="text-ms-gray-130">{selectedMsg.headers.date || "-"}</span>
                  </div>
                </div>
                <div className="p-4">
                  <pre className="text-xs text-ms-gray-130 whitespace-pre-wrap font-sans leading-relaxed">{selectedMsg.body || "(Sin contenido)"}</pre>
                </div>
              </div>
            ) : (
              <div className="p-8 text-center text-ms-gray-60 text-xs">Selecciona un mensaje para leerlo</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
