import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface Status {
  realm: string; idp_url: string; keycloak_ok: boolean; oidc_enabled: boolean;
  mailbox_active: number; ldap_users: number; ldap_synced_pct: number; webmail_client: string;
}

function Badge({ ok, okText, noText }: { ok: boolean; okText: string; noText: string }) {
  return (
    <span className="px-2 py-0.5 rounded text-xs font-medium"
      style={{ background: ok ? "#dff6dd" : "#fde7e9", color: ok ? "#107c10" : "#a4262c" }}>
      {ok ? okText : noText}
    </span>
  );
}

export function Sso() {
  const [st, setSt] = useState<Status | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [out, setOut] = useState("");
  const load = () => api.get<Status>("/sso/status").then(setSt).catch(() => {});
  useEffect(load, []);
  const sync = async () => {
    setSyncing(true); setOut("");
    try { const r = await api.post<{ output: string }>("/sso/sync", {}); setOut(r?.output || ""); load(); }
    catch { setOut("Error en la sincronización."); }
    setSyncing(false);
  };
  return (
    <div className="p-6 max-w-4xl space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-semibold text-ms-gray-160">SSO / Identidad unificada</h1>
          <p className="text-sm text-ms-gray-110">Inicio de sesión único del ecosistema vía Keycloak (OIDC) y federación LDAP.</p>
        </div>
        <div className="flex items-center gap-2">
          <SectionHelp titulo="SSO / Identidad unificada" items={[
            { titulo: "Qué es esta sección", desc: "Muestra el estado del inicio de sesión único (SSO): los usuarios entran al webmail con la misma cuenta del ecosistema, gestionada por Keycloak vía OIDC y federación LDAP." },
            { titulo: "Proveedor de identidad (Keycloak)", desc: "Servidor central de identidades. La tarjeta indica si está en línea, el realm usado y su URL. Si está caído, el SSO no funciona (queda el login local de respaldo)." },
            { titulo: "SSO del Webmail (OIDC)", desc: "Indica si el webmail tiene habilitado el inicio de sesión vía Keycloak y qué client OIDC usa. El login local break-glass sigue disponible como respaldo." },
            { titulo: "Federación LDAP", desc: "Muestra cuántos buzones activos están sincronizados en LDAP. Las contraseñas no se copian: LDAP valida los hashes Dovecot existentes." },
            { titulo: "Sincronizar usuarios", desc: "El botón vuelca los buzones de correo hacia LDAP para que Keycloak los reconozca. Ejecútelo tras crear o eliminar buzones. La salida del proceso se muestra abajo." },
          ]} />
          <button onClick={sync} disabled={syncing}
            title="Ejecuta la sincronización de los buzones de correo hacia LDAP para que Keycloak los reconozca en el SSO. No borra usuarios ni cambia contraseñas; la salida del proceso se muestra abajo."
            className="text-white text-sm px-4 py-2 rounded disabled:opacity-50" style={{ backgroundColor: "#0078d4" }}>
            {syncing ? "Sincronizando…" : "Sincronizar usuarios → LDAP"}
          </button>
        </div>
      </div>
      {!st ? <div className="text-sm text-ms-gray-110">Cargando…</div> : (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="bg-white border border-ms-gray-30 rounded-lg p-4 space-y-2">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-ms-gray-160">Proveedor de identidad (Keycloak)</h2>
              <Badge ok={st.keycloak_ok} okText="En línea" noText="Caído" />
            </div>
            <div className="text-xs text-ms-gray-110">Realm: <span className="font-mono">{st.realm}</span></div>
            <div className="text-xs text-ms-gray-110">URL: <span className="font-mono">{st.idp_url}</span></div>
          </div>
          <div className="bg-white border border-ms-gray-30 rounded-lg p-4 space-y-2">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-ms-gray-160">SSO del Webmail (OIDC)</h2>
              <Badge ok={st.oidc_enabled} okText="Habilitado" noText="Deshabilitado" />
            </div>
            <div className="text-xs text-ms-gray-110">Client: <span className="font-mono">{st.webmail_client}</span></div>
            <div className="text-xs text-ms-gray-110">Login local de respaldo (break-glass) intacto.</div>
          </div>
          <div className="bg-white border border-ms-gray-30 rounded-lg p-4 space-y-2 md:col-span-2">
            <h2 className="text-sm font-semibold text-ms-gray-160">Federación LDAP</h2>
            <div className="text-sm text-ms-gray-160">{st.ldap_users} de {st.mailbox_active} buzones sincronizados
              <span className="text-ms-gray-110"> ({st.ldap_synced_pct}%)</span></div>
            <div className="h-2 rounded overflow-hidden" style={{ backgroundColor: "#edebe9" }}>
              <div className="h-full" style={{ width: `${st.ldap_synced_pct}%`, backgroundColor: st.ldap_synced_pct >= 100 ? "#107c10" : "#0078d4" }} />
            </div>
            <div className="text-xs text-ms-gray-110">Las contraseñas no se migran: LDAP valida los hashes Dovecot existentes; Keycloak federa LDAP.</div>
          </div>
        </div>
      )}
      {out && <pre className="text-xs p-3 rounded whitespace-pre-wrap max-h-48 overflow-auto" style={{ background: "#1e1e1e", color: "#e0e0e0" }}>{out}</pre>}
    </div>
  );
}
