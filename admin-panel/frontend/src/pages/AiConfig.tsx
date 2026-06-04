import { useState, useEffect } from "react";
import { api } from "../api/client";

interface AiCfg {
  provider: string;
  base_url: string;
  model: string;
  enabled: boolean;
  has_key?: boolean;
  api_key?: string;
}

const PROVIDERS = [
  {
    value: "ollama",
    label: "IA propia / Ollama (en tu data center)",
    hint: "URL de tu servidor Ollama o gateway local. Ej: http://127.0.0.1:11434 o http://192.168.1.50:11434",
    needsKey: false,
  },
  {
    value: "custom",
    label: "Gateway propio (cabecera X-API-Key)",
    hint: "URL de tu servicio de IA propio. Se autentica con la cabecera X-API-Key.",
    needsKey: true,
  },
  {
    value: "openai",
    label: "Proveedor por API (OpenAI o compatible)",
    hint: "Deja la URL vacía para OpenAI, o pon la de un compatible (Groq, Together, etc.). Requiere API key.",
    needsKey: true,
  },
];

export function AiConfig() {
  const [cfg, setCfg] = useState<AiCfg>({ provider: "ollama", base_url: "", model: "", enabled: false });
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    api.get<AiCfg>("/ai-config")
      .then((d) => setCfg(d))
      .catch((e) => setMsg({ ok: false, text: e.message }))
      .finally(() => setLoading(false));
  }, []);

  const prov = PROVIDERS.find((p) => p.value === cfg.provider) || PROVIDERS[0];

  async function save() {
    setSaving(true); setMsg(null);
    try {
      await api.put("/ai-config", { ...cfg, api_key: apiKey });
      setApiKey("");
      setCfg((c) => ({ ...c, has_key: c.has_key || !!apiKey }));
      setMsg({ ok: true, text: "Configuración guardada." });
    } catch (e: any) {
      setMsg({ ok: false, text: e.message });
    } finally { setSaving(false); }
  }

  async function test() {
    setTesting(true); setMsg(null);
    try {
      const r: any = await api.post("/ai-config/test", { ...cfg, api_key: apiKey });
      setMsg({ ok: r.ok, text: r.ok ? (r.detail || "Conexión OK") : (r.error || r.detail || "Falló la conexión") });
    } catch (e: any) {
      setMsg({ ok: false, text: e.message });
    } finally { setTesting(false); }
  }

  if (loading) return <div className="p-6 text-ms-gray-60">Cargando…</div>;

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-xl font-semibold text-ms-gray-130 mb-1">Configurar IA</h1>
      <p className="text-sm text-ms-gray-60 mb-5">
        Conecta la IA que usará el webmail (redacción asistida, respuestas, resúmenes).
        Puedes usar una <b>IA propia</b> en tu data center o un <b>proveedor por API</b>.
        Si lo dejas desactivado, el webmail usa la configuración del archivo <code>.env</code>.
      </p>

      <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-4">
        {/* Activar */}
        <label className="flex items-center gap-2 text-sm font-medium text-ms-gray-130">
          <input type="checkbox" checked={cfg.enabled}
            onChange={(e) => setCfg({ ...cfg, enabled: e.target.checked })} />
          Activar la IA configurada aquí (si se desactiva, se usa el <code>.env</code>)
        </label>

        {/* Proveedor */}
        <div>
          <label className="block text-sm font-medium text-ms-gray-130 mb-1">Tipo de conexión</label>
          <select className="w-full px-3 py-2 border border-ms-gray-30 rounded text-sm"
            value={cfg.provider} onChange={(e) => setCfg({ ...cfg, provider: e.target.value })}>
            {PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
          <p className="text-xs text-ms-gray-60 mt-1">{prov.hint}</p>
        </div>

        {/* URL */}
        <div>
          <label className="block text-sm font-medium text-ms-gray-130 mb-1">
            URL del servidor {cfg.provider === "openai" ? "(opcional)" : ""}
          </label>
          <input className="w-full px-3 py-2 border border-ms-gray-30 rounded text-sm"
            placeholder="http://127.0.0.1:11434"
            value={cfg.base_url} onChange={(e) => setCfg({ ...cfg, base_url: e.target.value })} />
        </div>

        {/* API Key */}
        {prov.needsKey && (
          <div>
            <label className="block text-sm font-medium text-ms-gray-130 mb-1">
              API Key {cfg.has_key && <span className="text-xs text-green-600">(hay una guardada — deja vacío para conservarla)</span>}
            </label>
            <input type="password" className="w-full px-3 py-2 border border-ms-gray-30 rounded text-sm"
              placeholder={cfg.has_key ? "•••••••• (sin cambios)" : "Pega tu API key"}
              value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
          </div>
        )}

        {/* Modelo */}
        <div>
          <label className="block text-sm font-medium text-ms-gray-130 mb-1">Modelo</label>
          <input className="w-full px-3 py-2 border border-ms-gray-30 rounded text-sm"
            placeholder="Ej: qwen2.5:7b  ·  llama3  ·  gpt-4o-mini"
            value={cfg.model} onChange={(e) => setCfg({ ...cfg, model: e.target.value })} />
        </div>

        {/* Mensaje */}
        {msg && (
          <div className={`text-sm px-3 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
            {msg.text}
          </div>
        )}

        {/* Botones */}
        <div className="flex gap-3 pt-1">
          <button onClick={save} disabled={saving}
            className="px-4 py-2 bg-ms-blue text-white rounded text-sm font-medium disabled:opacity-50">
            {saving ? "Guardando…" : "Guardar"}
          </button>
          <button onClick={test} disabled={testing}
            className="px-4 py-2 border border-ms-gray-30 rounded text-sm font-medium disabled:opacity-50">
            {testing ? "Probando…" : "Probar conexión"}
          </button>
        </div>
      </div>
    </div>
  );
}
