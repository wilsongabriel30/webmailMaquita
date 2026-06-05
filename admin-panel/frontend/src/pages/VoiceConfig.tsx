import { useState, useEffect } from "react";
import { api } from "../api/client";

interface VoiceCfg {
  whisper_url: string;
  language: string;
  mode: string;
  enabled: boolean;
  has_key?: boolean;
}

const inputCls = "w-full px-3 py-2 border border-ms-gray-30 rounded text-sm";
const labelCls = "block text-sm font-medium text-ms-gray-130 mb-1";

export function VoiceConfig() {
  const [cfg, setCfg] = useState<VoiceCfg>({ whisper_url: "", language: "es", mode: "whisper", enabled: false });
  const [key, setKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    api.get<VoiceCfg>("/voice-config").then(setCfg).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true); setMsg(null);
    try {
      await api.put("/voice-config", { ...cfg, whisper_key: key });
      setKey("");
      setMsg({ ok: true, text: "Configuración guardada" });
    } catch (e: any) {
      setMsg({ ok: false, text: e?.message || "Error al guardar" });
    } finally { setSaving(false); }
  };

  const test = async () => {
    setTesting(true); setMsg(null);
    try {
      const r: any = await api.post("/voice-config/test", { ...cfg, whisper_key: key });
      setMsg({ ok: !!r.ok, text: r.ok ? "Servidor de transcripción disponible ✓" : (r.detail || r.error || "No disponible") });
    } catch (e: any) {
      setMsg({ ok: false, text: e?.message || "Error en la prueba" });
    } finally { setTesting(false); }
  };

  if (loading) return <div className="p-6 text-sm text-ms-gray-110">Cargando…</div>;

  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-semibold text-ms-gray-160 mb-1">Dictado por voz</h1>
      <p className="text-sm text-ms-gray-110 mb-5">
        Permite a los usuarios dictar el texto de sus correos con la voz. La transcripción
        se hace en un servidor <b>Whisper</b> que tú indicas aquí — así el audio queda en tu
        propia infraestructura (no se envía a terceros).
      </p>

      <div className="bg-white border border-ms-gray-30 rounded-lg p-5 space-y-4">
        <label className="flex items-center gap-2 text-sm font-medium text-ms-gray-130">
          <input type="checkbox" checked={cfg.enabled}
            onChange={(e) => setCfg({ ...cfg, enabled: e.target.checked })} />
          Habilitar el dictado por voz
        </label>

        <div>
          <label className={labelCls}>Motor de transcripción</label>
          <select className={inputCls} value={cfg.mode}
            onChange={(e) => setCfg({ ...cfg, mode: e.target.value })}>
            <option value="whisper">Whisper — privado, en tu servidor (recomendado)</option>
            <option value="browser">Navegador — streaming en vivo (usa Google · solo Chrome/Edge)</option>
          </select>
          <p className="text-xs text-ms-gray-110 mt-1">
            {cfg.mode === "browser"
              ? "El texto aparece mientras hablas; el audio pasa por servidores de Google."
              : "Pulsas, hablas y al callar se escribe solo. Todo queda en tu infraestructura (no usa terceros)."}
          </p>
        </div>

        <div>
          <label className={labelCls}>URL del servidor Whisper</label>
          <input className={inputCls} placeholder="http://192.168.1.50:8765"
            value={cfg.whisper_url} onChange={(e) => setCfg({ ...cfg, whisper_url: e.target.value })} />
          <p className="text-xs text-ms-gray-110 mt-1">Debe responder a <code>/health</code> y <code>POST /api/transcribe</code>.</p>
        </div>

        <div>
          <label className={labelCls}>
            API key {cfg.has_key && <span className="text-ms-green font-normal">(configurada — deja vacío para conservarla)</span>}
          </label>
          <input type="password" className={inputCls} placeholder={cfg.has_key ? "••••••••" : "Clave del servidor Whisper"}
            value={key} onChange={(e) => setKey(e.target.value)} />
        </div>

        <div>
          <label className={labelCls}>Idioma por defecto</label>
          <input className={inputCls + " max-w-[120px]"} placeholder="es"
            value={cfg.language} onChange={(e) => setCfg({ ...cfg, language: e.target.value })} />
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

      <div className="bg-ms-gray-10 border border-ms-gray-30 rounded-lg p-5 mt-5 text-sm text-ms-gray-150">
        <h2 className="font-semibold mb-2">¿Cómo monto el servidor de transcripción?</h2>
        <p className="mb-2">El dictado necesita un servicio <b>Whisper</b> (OpenAI) accesible por HTTP. Opciones:</p>
        <ul className="list-disc pl-5 space-y-1.5">
          <li><b>PC o servidor con GPU (recomendado):</b> instala <code>faster-whisper</code> en un equipo con tarjeta NVIDIA; transcribe rápido. Exponlo en la red local con un pequeño servicio HTTP (<code>/health</code> y <code>POST /api/transcribe</code> con el campo <code>audio</code>).</li>
          <li><b>Servidor sin GPU:</b> funciona en CPU con el modelo <code>small</code> o <code>base</code> (más lento, unos segundos por frase). Útil para bajo volumen.</li>
          <li><b>Servidor de IA existente:</b> si ya tienes un equipo de IA en la institución, levanta ahí el endpoint de Whisper y apunta esta URL.</li>
          <li><b>Apuntar a un PC concreto:</b> pon la IP del equipo (p. ej. <code>http://192.168.1.50:8765</code>) y la API key que ese servicio exija.</li>
        </ul>
        <p className="mt-3 text-xs text-ms-gray-110">
          El servidor Whisper debe aceptar <code>multipart/form-data</code> con el archivo en el campo
          <code> audio</code> y devolver JSON con <code>full_text</code> (o <code>text</code>). La autenticación
          se envía en la cabecera <code>X-API-Key</code>. Si dejas esto deshabilitado, el botón de dictado
          simplemente no transcribe.
        </p>
      </div>
    </div>
  );
}
