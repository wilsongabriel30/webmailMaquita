import { useEffect, useState } from "react";

/* Panel de control del Chat institucional.
   - Activar/desactivar el chat y definir la URL del servidor de chat.
   - AISLAMIENTO POR DOMINIO (multi-empresa): definir que dominios pueden chatear
     entre si (grupos). Los dominios que no esten en ningun grupo quedan aislados
     (solo chatean dentro de su mismo dominio). SOLO afecta al chat; el correo
     (email) entre dominios NO se restringe. */

interface ChatConfig {
  enabled: boolean;
  embed_url: string;
  domain_isolation: boolean;
  domain_groups: string[][];
}

export function ChatSettingsPanel() {
  const [enabled, setEnabled] = useState(true);
  const [embedUrl, setEmbedUrl] = useState("/chat/?embed=1");
  const [isolation, setIsolation] = useState(false);
  const [groups, setGroups] = useState<string[]>([]); // cada string = dominios separados por coma
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null);

  useEffect(() => {
    fetch("/api/admin/chat-config", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d: ChatConfig) => {
        setEnabled(!!d.enabled);
        setEmbedUrl(d.embed_url || "/chat/?embed=1");
        setIsolation(!!d.domain_isolation);
        setGroups((d.domain_groups || []).map((g) => g.join(", ")));
      })
      .catch(() => {})
      .finally(() => setCargando(false));
  }, []);

  const parseGroups = (): string[][] =>
    groups
      .map((line) =>
        line
          .split(",")
          .map((d) => d.trim().toLowerCase().replace(/^@/, ""))
          .filter(Boolean)
      )
      .filter((g) => g.length > 0);

  const guardar = async () => {
    setGuardando(true);
    setMsg(null);
    try {
      const r = await fetch("/api/admin/chat-config", {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled,
          embed_url: embedUrl,
          domain_isolation: isolation,
          domain_groups: parseGroups(),
        }),
      });
      if (!r.ok) throw new Error();
      const d: ChatConfig = await r.json();
      setEnabled(!!d.enabled);
      setEmbedUrl(d.embed_url);
      setIsolation(!!d.domain_isolation);
      setGroups((d.domain_groups || []).map((g) => g.join(", ")));
      setMsg({ ok: true, texto: "Configuracion guardada. Recarga el chat para ver el cambio." });
    } catch {
      setMsg({ ok: false, texto: "No se pudo guardar. Intenta de nuevo." });
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) return <div className="p-8 text-slate-500">Cargando...</div>;

  const Toggle = ({ on, onClick }: { on: boolean; onClick: () => void }) => (
    <button
      type="button"
      onClick={onClick}
      className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors ${on ? "bg-blue-600" : "bg-slate-300"}`}
      aria-pressed={on}
    >
      <span className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform ${on ? "translate-x-6" : "translate-x-1"}`} />
    </button>
  );

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-2xl font-semibold text-slate-800">Chat institucional</h1>
      <p className="text-sm text-slate-500 mt-1">
        Activa el chat en el correo, conecta el servidor de chat y controla el
        aislamiento por dominio (multi-empresa).
      </p>

      {/* Activado */}
      <div className="mt-6 flex items-center justify-between rounded-xl border border-slate-200 p-4">
        <div>
          <div className="font-medium text-slate-800">Chat activado</div>
          <div className="text-xs text-slate-500 mt-0.5">Muestra u oculta el chat en todo el correo.</div>
        </div>
        <Toggle on={enabled} onClick={() => setEnabled((v) => !v)} />
      </div>

      {/* URL */}
      <div className="mt-4 rounded-xl border border-slate-200 p-4">
        <label className="block font-medium text-slate-800">URL del servidor de chat</label>
        <p className="text-xs text-slate-500 mt-0.5">
          Por defecto <code>/chat/?embed=1</code>. Para otra instancia, su URL completa.
        </p>
        <input
          type="text"
          value={embedUrl}
          onChange={(e) => setEmbedUrl(e.target.value)}
          disabled={!enabled}
          className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:bg-slate-50"
          placeholder="/chat/?embed=1"
        />
      </div>

      {/* Aislamiento por dominio */}
      <div className="mt-4 rounded-xl border border-slate-200 p-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-medium text-slate-800">Aislar el chat por dominio (multi-empresa)</div>
            <div className="text-xs text-slate-500 mt-0.5">
              Si esta activo, cada quien solo ve y chatea con gente de su mismo grupo de dominios.
              <b> No afecta al correo</b>: los emails entre dominios siguen funcionando.
            </div>
          </div>
          <Toggle on={isolation} onClick={() => setIsolation((v) => !v)} />
        </div>

        {isolation && (
          <div className="mt-4 border-t border-slate-100 pt-4">
            <div className="text-sm font-medium text-slate-700">Grupos que SI pueden chatear entre si</div>
            <p className="text-xs text-slate-500 mt-0.5 mb-3">
              Un grupo por linea, dominios separados por coma. Ej:
              <code className="ml-1">maquita.com.ec, maquita.org, maquitaturismo.com</code>.
              Los dominios que no pongas en ningun grupo quedan <b>aislados</b> (solo hablan dentro de su propio dominio).
            </p>
            {groups.map((line, i) => (
              <div key={i} className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={line}
                  onChange={(e) => setGroups((g) => g.map((x, j) => (j === i ? e.target.value : x)))}
                  className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                  placeholder="dominio1.com, dominio2.com"
                />
                <button
                  onClick={() => setGroups((g) => g.filter((_, j) => j !== i))}
                  className="rounded-lg border border-slate-300 px-3 text-slate-500 hover:bg-slate-50"
                  title="Quitar grupo"
                >
                  ✕
                </button>
              </div>
            ))}
            <button
              onClick={() => setGroups((g) => [...g, ""])}
              className="mt-1 text-sm text-blue-600 hover:underline"
            >
              + Agregar grupo
            </button>
          </div>
        )}
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
