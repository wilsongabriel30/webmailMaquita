import { useState, useEffect } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface OfficeCfg {
  onlyoffice_url: string;
  enabled: boolean;
  has_secret?: boolean;
  from_env?: boolean;
}

const inputCls = "w-full px-3 py-2 border border-ms-gray-30 rounded text-sm";
const labelCls = "block text-sm font-medium text-ms-gray-130 mb-1";

export function OfficeConfig() {
  const [cfg, setCfg] = useState<OfficeCfg>({
    onlyoffice_url: "", enabled: false,
  });
  const [secret, setSecret] = useState("");
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
        ...cfg, onlyoffice_secret: secret,
      });
      setSecret("");
      setMsg({ ok: true, text: "Configuración guardada" });
    } catch (e: any) {
      setMsg({ ok: false, text: e?.message || "Error al guardar" });
    } finally { setSaving(false); }
  };

  const test = async () => {
    setTesting(true); setMsg(null);
    try {
      const r: any = await api.post("/office-config/test", {
        ...cfg, onlyoffice_secret: secret,
      });
      const oo = r.onlyoffice?.ok ? "OnlyOffice OK" : `OnlyOffice falló (${r.onlyoffice?.status || r.onlyoffice?.error || "?"})`;
      setMsg({ ok: !!r.onlyoffice?.ok, text: oo });
    } catch (e: any) {
      setMsg({ ok: false, text: e?.message || "Error en la prueba" });
    } finally { setTesting(false); }
  };

  if (loading) return <div className="p-6 text-sm text-ms-gray-110">Cargando…</div>;

  return (
    <div className="max-w-2xl">
      <div className="flex justify-end">
        <SectionHelp
          titulo="OnlyOffice"
          items={[
            { titulo: "Qué hace esta sección", desc: "Conecta el webmail con OnlyOffice para previsualizar y editar adjuntos de Word, Excel y PowerPoint. Los archivos viven en el Almacén (Drive)." },
            { titulo: "Habilitar integración", desc: "La casilla superior enciende o apaga la previsualización de documentos para todos los usuarios del webmail." },
            { titulo: "Document Server (OnlyOffice)", desc: "URL del servidor OnlyOffice y su secreto JWT (debe coincidir con el configurado en OnlyOffice). Sin JWT correcto, el visor de documentos no abre los adjuntos." },
            { titulo: "Credenciales guardadas", desc: "El secreto JWT se guarda cifrado; si ya existe y dejas el campo vacío, se conserva el actual." },
            { titulo: "Guardar y probar", desc: "Guardar aplica los cambios de inmediato; Probar conexión verifica OnlyOffice sin guardar nada." },
          ]}
        />
      </div>
      <h1 className="text-xl font-semibold text-ms-gray-160 mb-1">OnlyOffice</h1>
      <p className="text-sm text-ms-gray-110 mb-5">
        Parametriza el visor de documentos Office (OnlyOffice) que usa el webmail para previsualizar
        adjuntos; los archivos se guardan en el Almacén (Drive).
        {cfg.from_env && " (Mostrando lo configurado hoy en el servidor.)"}
      </p>

      <div className="bg-white border border-ms-gray-30 rounded-lg p-5 space-y-5">
        <label className="flex items-center gap-2 text-sm font-medium text-ms-gray-130">
          <input type="checkbox" checked={cfg.enabled}
            title="Activa o desactiva para todos los usuarios la previsualización de documentos Office en el webmail."
            onChange={(e) => setCfg({ ...cfg, enabled: e.target.checked })} />
          Habilitar la previsualización de documentos Office
        </label>

        <div className="border-t border-ms-gray-20 pt-4">
          <h2 className="text-sm font-semibold text-ms-gray-150 mb-3">Document Server (OnlyOffice)</h2>
          <div className="space-y-3">
            <div>
              <label className={labelCls}>URL del Document Server</label>
              <input className={inputCls} placeholder="https://office.example.com"
                title="URL del Document Server de OnlyOffice que renderiza los documentos (ej. https://office.example.com). Debe ser accesible desde los navegadores de los usuarios."
                value={cfg.onlyoffice_url} onChange={(e) => setCfg({ ...cfg, onlyoffice_url: e.target.value })} />
            </div>
            <div>
              <label className={labelCls}>
                Secreto JWT {cfg.has_secret && <span className="text-ms-green font-normal">(configurado — deja vacío para conservarlo)</span>}
              </label>
              <input type="password" className={inputCls} placeholder={cfg.has_secret ? "••••••••" : "Secreto JWT de OnlyOffice"}
                title="Secreto JWT configurado en el Document Server de OnlyOffice; debe coincidir exactamente o el visor no abrirá documentos. Si ya hay uno guardado, deja vacío para conservarlo."
                value={secret} onChange={(e) => setSecret(e.target.value)} />
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
            title="Guarda esta configuración en el servidor y la aplica de inmediato a la previsualización de documentos."
            className="px-4 py-2 bg-ms-blue text-white rounded text-sm font-medium hover:bg-ms-blue-dark disabled:opacity-50">
            {saving ? "Guardando…" : "Guardar"}
          </button>
          <button onClick={test} disabled={testing}
            title="Verifica la conexión con OnlyOffice usando los datos del formulario, sin guardar nada."
            className="px-4 py-2 border border-ms-gray-30 text-ms-gray-150 rounded text-sm font-medium hover:bg-ms-gray-10 disabled:opacity-50">
            {testing ? "Probando…" : "Probar conexión"}
          </button>
        </div>
      </div>
    </div>
  );
}
