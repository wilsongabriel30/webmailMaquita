import { useEffect, useState } from "react";
import { api } from "../../api/client";

// Entrada al panel con OpenID Connect (solo superadmin). El secreto del cliente nunca vuelve del
// servidor: se guarda cifrado y aquí solo se sabe si hay uno guardado.
interface Config {
  activado: boolean; emisor: string; client_id: string; secreto_guardado: boolean;
  claim_usuario: string; claim_grupos: string; grupo_requerido: string;
  crear_si_no_existe: boolean; rol_nuevo: string; texto_boton: string;
  actualizado_por: string; actualizado_en: string | null; url_vuelta: string;
}
interface Prueba { issuer: string; authorization_endpoint: string; token_endpoint: string; claves: number; pkce_s256: boolean }

const campo = "w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue";

export function EntradaOidcConfig() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [secreto, setSecreto] = useState("");
  const [mensaje, setMensaje] = useState<{ ok: boolean; texto: string } | null>(null);
  const [prueba, setPrueba] = useState<Prueba | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => { api.get<Config>("/auth/oidc/config").then(setCfg).catch((e) => setMensaje({ ok: false, texto: e.message })); }, []);
  if (!cfg) return mensaje ? <div className="text-sm text-ms-red">{mensaje.texto}</div> : null;

  const poner = <K extends keyof Config>(k: K, v: Config[K]) => setCfg({ ...cfg, [k]: v });
  const guardar = async () => {
    setOcupado(true); setMensaje(null);
    try {
      const r = await api.put<Config>("/auth/oidc/config", { ...cfg, client_secret: secreto });
      setCfg({ ...cfg, ...r }); setSecreto("");
      setMensaje({ ok: true, texto: "Guardado." });
    } catch (e) { setMensaje({ ok: false, texto: e instanceof Error ? e.message : "No se pudo guardar" }); }
    setOcupado(false);
  };
  const probar = async () => {
    setOcupado(true); setMensaje(null); setPrueba(null);
    try { setPrueba(await api.post<Prueba>("/auth/oidc/probar", { emisor: cfg.emisor })); }
    catch (e) { setMensaje({ ok: false, texto: e instanceof Error ? e.message : "No se pudo probar" }); }
    setOcupado(false);
  };

  return (
    <div className="bg-white border border-ms-gray-30 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <h2 className="text-sm font-semibold text-ms-gray-160">Entrada al panel con OpenID Connect</h2>
        <label className="text-sm flex items-center gap-2" title="Muestra el botón en la pantalla de entrada del panel. La entrada con usuario y contraseña sigue disponible.">
          <input type="checkbox" checked={cfg.activado} onChange={(e) => poner("activado", e.target.checked)} /> Activada
        </label>
      </div>
      <p className="text-xs text-ms-gray-110">Solo para entrar a este panel (8443): no cambia el SSO del correo. Registre en el proveedor esta dirección de vuelta:</p>
      <div className="text-xs font-mono bg-ms-gray-20 rounded px-2 py-1 break-all">{cfg.url_vuelta}</div>
      <div className="grid gap-3 md:grid-cols-2">
        <label className="text-xs text-ms-gray-110">Emisor (issuer)
          <input className={campo} value={cfg.emisor} onChange={(e) => poner("emisor", e.target.value)} placeholder="https://auth.example.org" /></label>
        <label className="text-xs text-ms-gray-110">client_id
          <input className={campo} value={cfg.client_id} onChange={(e) => poner("client_id", e.target.value)} placeholder="panel-correo" /></label>
        <label className="text-xs text-ms-gray-110">client_secret {cfg.secreto_guardado && <span className="text-ms-green">(guardado; vacío = no cambiar)</span>}
          <input className={campo} type="password" autoComplete="new-password" value={secreto} onChange={(e) => setSecreto(e.target.value)} /></label>
        <label className="text-xs text-ms-gray-110">Claim de usuario
          <input className={campo} value={cfg.claim_usuario} onChange={(e) => poner("claim_usuario", e.target.value)} placeholder="preferred_username o email" /></label>
        <label className="text-xs text-ms-gray-110">Claim de grupos (opcional)
          <input className={campo} value={cfg.claim_grupos} onChange={(e) => poner("claim_grupos", e.target.value)} placeholder="groups" /></label>
        <label className="text-xs text-ms-gray-110">Grupo requerido (opcional)
          <input className={campo} value={cfg.grupo_requerido} onChange={(e) => poner("grupo_requerido", e.target.value)} placeholder="admins-correo" /></label>
        <label className="text-xs text-ms-gray-110">Texto del botón
          <input className={campo} maxLength={60} value={cfg.texto_boton} onChange={(e) => poner("texto_boton", e.target.value)} /></label>
        <div className="text-xs text-ms-gray-110 space-y-1">
          <label className="flex items-center gap-2" title="Apagado: solo entran las cuentas que ya existen en el panel con ese nombre de usuario.">
            <input type="checkbox" checked={cfg.crear_si_no_existe} onChange={(e) => poner("crear_si_no_existe", e.target.checked)} />
            Crear la cuenta si no existe</label>
          {cfg.crear_si_no_existe && (
            <label className="block">Rol de las cuentas nuevas
              <select className={campo} value={cfg.rol_nuevo} onChange={(e) => poner("rol_nuevo", e.target.value)}>
                <option value="viewer">viewer (solo lectura)</option><option value="admin">admin</option><option value="superadmin">superadmin</option>
              </select></label>
          )}
        </div>
      </div>
      <p className="text-xs text-ms-gray-110">La cuenta se busca en los administradores del panel por el claim de usuario. Si tiene segundo factor, se le pide al volver del proveedor.</p>
      {mensaje && <div className={`text-xs ${mensaje.ok ? "text-ms-green" : "text-ms-red"}`}>{mensaje.texto}</div>}
      {prueba && (
        <div className="text-xs text-ms-gray-110 bg-ms-gray-20 rounded p-2 space-y-0.5">
          <div>Proveedor correcto: <span className="font-mono">{prueba.issuer}</span></div>
          <div>{prueba.claves} clave(s) publicadas · PKCE S256 {prueba.pkce_s256 ? "admitido" : "NO anunciado"}</div>
        </div>
      )}
      <div className="flex gap-2">
        <button onClick={probar} disabled={ocupado || !cfg.emisor} title="Descarga /.well-known/openid-configuration y las claves del emisor, sin guardar nada."
          className="px-3 py-1.5 border border-ms-blue text-ms-blue rounded text-sm disabled:opacity-50">Probar el emisor</button>
        <button onClick={guardar} disabled={ocupado} title="Guarda la configuración. Queda en la auditoría (sin el secreto)."
          className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Guardar</button>
      </div>
      {cfg.actualizado_por && <div className="text-[11px] text-ms-gray-60">Último cambio: {cfg.actualizado_por}{cfg.actualizado_en ? `, ${new Date(cfg.actualizado_en).toLocaleString()}` : ""}</div>}
    </div>
  );
}
