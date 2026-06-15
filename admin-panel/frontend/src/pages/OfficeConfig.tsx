import { useState, useEffect } from "react";
import { api } from "../api/client";

interface OfficeCfg {
  onlyoffice_url: string;
  nc_base_url: string;
  nc_public_url: string;
  nc_admin_user: string;
  enabled: boolean;
  has_secret?: boolean;
  has_nc_pass?: boolean;
  from_env?: boolean;
}

const inputCls = "w-full px-3 py-2 border border-ms-gray-30 rounded text-sm";
const labelCls = "block text-sm font-medium text-ms-gray-130 mb-1";

export function OfficeConfig() {
  const [cfg, setCfg] = useState<OfficeCfg>({
    onlyoffice_url: "", nc_base_url: "", nc_public_url: "", nc_admin_user: "", enabled: false,
  });
  const [secret, setSecret] = useState("");
  const [ncPass, setNcPass] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    api.get<OfficeCfg>("/office-config")
      .then((d) => setCfg(d))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true); setMsg(null);
    try {
      await api.put("/office-config", {
        ...cfg, onlyoffice_secret: secret, nc_admin_pass: ncPass,
      });
      setSecret(""); setNcPass("");
      setMsg({ ok: true, text: "Configuración guardada" });
    } catch (e: any) {
      setMsg({ ok: false, text: e?.message || "Error al guardar" });
    } finally { setSaving(false); }
  };

  const test = async () => {
    setTesting(true); setMsg(null);
    try {
      const r: any = await api.post("/office-config/test", {
        ...cfg, onlyoffice_secret: secret, nc_admin_pass: ncPass,
      });
      const oo = r.onlyoffice?.ok ? "OnlyOffice OK" : `OnlyOffice falló (${r.onlyoffice?.status || r.onlyoffice?.error || "?"})`;
      const nc = r.nextcloud?.ok ? "Nextcloud OK" : `Nextcloud falló (${r.nextcloud?.status || r.nextcloud?.error || "?"})`;
      setMsg({ ok: !!(r.onlyoffice?.ok && r.nextcloud?.ok), text: `${oo} · ${nc}` });
    } catch (e: any) {
      setMsg({ ok: false, text: e?.message || "Error en la prueba" });
    } finally { setTesting(false); }
  };

  if (loading) return <div className="p-6 text-sm text-ms-gray-110">Cargando…</div>;

  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-semibold text-ms-gray-160 mb-1">OnlyOffice / Nextcloud</h1>
      <p className="text-sm text-ms-gray-110 mb-5">
        Parametriza el visor de documentos Office (OnlyOffice) y la cuenta de la Nube
        (Nextcloud) que usa el webmail para previsualizar adjuntos y para "Guardar en Nube".
        {cfg.from_env && " (Mostrando lo configurado hoy en el servidor.)"}
      </p>

      <div className="bg-white border border-ms-gray-30 rounded-lg p-5 space-y-5">
        <label className="flex items-center gap-2 text-sm font-medium text-ms-gray-130">
          <input type="checkbox" checked={cfg.enabled}
            onChange={(e) => setCfg({ ...cfg, enabled: e.target.checked })} />
          Habilitar integración de documentos en la nube
        </label>

        <div className="border-t border-ms-gray-20 pt-4">
          <h2 className="text-sm font-semibold text-ms-gray-150 mb-3">Document Server (OnlyOffice)</h2>
          <div className="space-y-3">
            <div>
              <label className={labelCls}>URL del Document Server</label>
              <input className={inputCls} placeholder="https://office.example.com"
                value={cfg.onlyoffice_url} onChange={(e) => setCfg({ ...cfg, onlyoffice_url: e.target.value })} />
            </div>
            <div>
              <label className={labelCls}>
                Secreto JWT {cfg.has_secret && <span className="text-ms-green font-normal">(configurado — deja vacío para conservarlo)</span>}
              </label>
              <input type="password" className={inputCls} placeholder={cfg.has_secret ? "••••••••" : "Secreto JWT de OnlyOffice"}
                value={secret} onChange={(e) => setSecret(e.target.value)} />
            </div>
          </div>
        </div>

        <div className="border-t border-ms-gray-20 pt-4">
          <h2 className="text-sm font-semibold text-ms-gray-150 mb-3">Nube (Nextcloud)</h2>
          <div className="space-y-3">
            <div>
              <label className={labelCls}>URL interna (servidor a servidor)</label>
              <input className={inputCls} placeholder="http://10.0.0.10"
                value={cfg.nc_base_url} onChange={(e) => setCfg({ ...cfg, nc_base_url: e.target.value })} />
            </div>
            <div>
              <label className={labelCls}>URL pública (la que ven los usuarios)</label>
              <input className={inputCls} placeholder="https://nube.example.com"
                value={cfg.nc_public_url} onChange={(e) => setCfg({ ...cfg, nc_public_url: e.target.value })} />
            </div>
            <div>
              <label className={labelCls}>Usuario administrador de Nextcloud</label>
              <input className={inputCls} placeholder="gestiontecnologia@maquita.com.ec"
                value={cfg.nc_admin_user} onChange={(e) => setCfg({ ...cfg, nc_admin_user: e.target.value })} />
            </div>
            <div>
              <label className={labelCls}>
                Contraseña del administrador {cfg.has_nc_pass && <span className="text-ms-green font-normal">(configurada — deja vacío para conservarla)</span>}
              </label>
              <input type="password" className={inputCls} placeholder={cfg.has_nc_pass ? "••••••••" : "Contraseña"}
                value={ncPass} onChange={(e) => setNcPass(e.target.value)} />
            </div>
          </div>
        </div>

        {msg && (
          <div className={`text-sm px-3 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
            {msg.text}
          </div>
        )}

        <div className="flex gap-3 pt-1">
          <button onClick={save} disabled={saving}
            className="px-4 py-2 bg-ms-blue text-white rounded text-sm font-medium hover:bg-ms-blue-dark disabled:opacity-50">
            {saving ? "Guardando…" : "Guardar"}
          </button>
          <button onClick={test} disabled={testing}
            className="px-4 py-2 border border-ms-gray-30 text-ms-gray-150 rounded text-sm font-medium hover:bg-ms-gray-10 disabled:opacity-50">
            {testing ? "Probando…" : "Probar conexión"}
          </button>
        </div>
      </div>
    </div>
  );
}
