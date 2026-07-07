import { useEffect, useState } from "react";

/* Panel de control del Chat institucional.
   El administrador activa/desactiva el chat y define la URL del servidor de chat
   a embeber. Pensado tambien para quien adopte el proyecto: aqui conecta su
   propia instancia (docker/servidor) sin tocar codigo. */

interface ChatConfig {
  enabled: boolean;
  embed_url: string;
}

export function ChatSettingsPanel() {
  const [cfg, setCfg] = useState<ChatConfig>({ enabled: true, embed_url: "/chat/?embed=1" });
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null);

  useEffect(() => {
    fetch("/api/admin/chat-config", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => setCfg({ enabled: !!d.enabled, embed_url: d.embed_url || "/chat/?embed=1" }))
      .catch(() => {})
      .finally(() => setCargando(false));
  }, []);

  const guardar = async () => {
    setGuardando(true);
    setMsg(null);
    try {
      const r = await fetch("/api/admin/chat-config", {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: cfg.enabled, embed_url: cfg.embed_url }),
      });
      if (!r.ok) throw new Error();
      const d = await r.json();
      setCfg({ enabled: !!d.enabled, embed_url: d.embed_url });
      setMsg({ ok: true, texto: "Configuracion guardada. Recarga el correo para ver el cambio." });
    } catch {
      setMsg({ ok: false, texto: "No se pudo guardar. Intenta de nuevo." });
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) return <div className="p-8 text-slate-500">Cargando...</div>;

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-2xl font-semibold text-slate-800">Chat institucional</h1>
      <p className="text-sm text-slate-500 mt-1">
        Activa el chat en el correo y conecta el servidor de chat. Al desactivarlo,
        el boton de chat desaparece para todos los usuarios del correo.
      </p>

      {/* Interruptor */}
      <div className="mt-6 flex items-center justify-between rounded-xl border border-slate-200 p-4">
        <div>
          <div className="font-medium text-slate-800">Chat activado</div>
          <div className="text-xs text-slate-500 mt-0.5">
            Muestra u oculta el boton flotante de chat en todo el correo.
          </div>
        </div>
        <button
          type="button"
          onClick={() => setCfg((c) => ({ ...c, enabled: !c.enabled }))}
          className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors ${
            cfg.enabled ? "bg-blue-600" : "bg-slate-300"
          }`}
          aria-pressed={cfg.enabled}
        >
          <span
            className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform ${
              cfg.enabled ? "translate-x-6" : "translate-x-1"
            }`}
          />
        </button>
      </div>

      {/* URL del servidor de chat */}
      <div className="mt-4 rounded-xl border border-slate-200 p-4">
        <label className="block font-medium text-slate-800">URL del servidor de chat</label>
        <p className="text-xs text-slate-500 mt-0.5">
          Pagina a embeber. Por defecto <code>/chat/?embed=1</code> (chat en este mismo
          servidor). Para conectar otra instancia, pon su URL completa
          (ej. <code>https://chat.tu-dominio.org/?embed=1</code>).
        </p>
        <input
          type="text"
          value={cfg.embed_url}
          onChange={(e) => setCfg((c) => ({ ...c, embed_url: e.target.value }))}
          disabled={!cfg.enabled}
          className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:bg-slate-50 disabled:text-slate-400"
          placeholder="/chat/?embed=1"
        />
      </div>

      {msg && (
        <div className={`mt-4 rounded-lg px-4 py-2 text-sm ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
          {msg.texto}
        </div>
      )}

      <div className="mt-6">
        <button
          onClick={guardar}
          disabled={guardando}
          className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
        >
          {guardando ? "Guardando..." : "Guardar cambios"}
        </button>
      </div>
    </div>
  );
}
