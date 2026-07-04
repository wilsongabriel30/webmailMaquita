import { useState, useEffect } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

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
      <div className="flex justify-end">
        <SectionHelp
          titulo="Dictado por voz"
          items={[
            { titulo: "Qué hace esta sección", desc: "Configura el dictado por voz del webmail: los usuarios hablan y el texto se escribe en el correo. La transcripción la hace un servidor Whisper que tú indicas." },
            { titulo: "Motor de transcripción", desc: "Whisper (privado, por frases) y Whisper en vivo (privado, palabra por palabra con GPU) procesan el audio en tu infraestructura; Navegador usa el reconocimiento de Google (solo Chrome/Edge) y el audio sale a terceros." },
            { titulo: "URL y API key", desc: "La URL del servidor Whisper debe responder a /health y POST /api/transcribe; la API key se envía en la cabecera X-API-Key y queda guardada cifrada." },
            { titulo: "Idioma por defecto", desc: "Código de idioma (ej. es) con el que Whisper transcribe si el usuario no elige otro." },
            { titulo: "Guardar y probar", desc: "Guardar aplica la configuración al webmail; Probar conexión verifica que el servidor Whisper esté disponible sin guardar cambios." },
            { titulo: "Guía de instalación", desc: "La caja gris de abajo explica cómo montar el servidor de transcripción (con GPU, en CPU o reutilizando un servidor de IA existente)." },
          ]}
        />
      </div>
      <h1 className="text-xl font-semibold text-ms-gray-160 mb-1">Dictado por voz</h1>
      <p className="text-sm text-ms-gray-110 mb-5">
        Permite a los usuarios dictar el texto de sus correos con la voz. La transcripción
        se hace en un servidor <b>Whisper</b> que tú indicas aquí — así el audio queda en tu
        propia infraestructura (no se envía a terceros).
      </p>

      <div className="bg-white border border-ms-gray-30 rounded-lg p-5 space-y-4">
        <label className="flex items-center gap-2 text-sm font-medium text-ms-gray-130">
          <input type="checkbox" checked={cfg.enabled}
            title="Activa o desactiva el botón de dictado por voz en el webmail para todos los usuarios. Si está desactivado, el botón de micrófono no transcribe."
            onChange={(e) => setCfg({ ...cfg, enabled: e.target.checked })} />
          Habilitar el dictado por voz
        </label>

        <div>
          <label className={labelCls}>Motor de transcripción</label>
          <select className={inputCls} value={cfg.mode}
            title="Elige el motor de transcripción: Whisper y Whisper en vivo procesan el audio en tu propio servidor (privado); Navegador usa los servidores de Google y solo funciona en Chrome/Edge."
            onChange={(e) => setCfg({ ...cfg, mode: e.target.value })}>
            <option value="whisper">Whisper — privado, en tu servidor (recomendado)</option>
            <option value="whisperlive">Whisper en vivo (privado) — streaming en TU GPU (recomendado para fluidez)</option>
            <option value="browser">Navegador — streaming en vivo (usa Google · solo Chrome/Edge)</option>
          </select>
          <p className="text-xs text-ms-gray-110 mt-1">
            {cfg.mode === "whisperlive"
              ? "Streaming en vivo (palabra por palabra) procesado en tu servidor con GPU. Privado y fluido. Requiere el servicio WhisperLive y la ruta /whisperlive/ en nginx."
              : cfg.mode === "browser"
              ? "El texto aparece mientras hablas; el audio pasa por servidores de Google."
              : "Pulsas, hablas y al callar se escribe solo. Todo queda en tu infraestructura (no usa terceros)."}
          </p>
        </div>

        <div>
          <label className={labelCls}>URL del servidor Whisper</label>
          <input className={inputCls} placeholder="http://192.168.1.50:8765"
            title="Dirección HTTP del servidor Whisper que transcribirá el audio (ej. http://192.168.1.50:8765). Debe responder a /health y aceptar POST /api/transcribe."
            value={cfg.whisper_url} onChange={(e) => setCfg({ ...cfg, whisper_url: e.target.value })} />
          <p className="text-xs text-ms-gray-110 mt-1">Debe responder a <code>/health</code> y <code>POST /api/transcribe</code>.</p>
        </div>

        <div>
          <label className={labelCls}>
            API key {cfg.has_key && <span className="text-ms-green font-normal">(configurada — deja vacío para conservarla)</span>}
          </label>
          <input type="password" className={inputCls} placeholder={cfg.has_key ? "••••••••" : "Clave del servidor Whisper"}
            title="Clave que exige el servidor Whisper; se envía en la cabecera X-API-Key. Si ya hay una guardada y dejas el campo vacío, se conserva la actual."
            value={key} onChange={(e) => setKey(e.target.value)} />
        </div>

        <div>
          <label className={labelCls}>Idioma por defecto</label>
          <input className={inputCls + " max-w-[120px]"} placeholder="es"
            title="Código de idioma con el que se transcribe por defecto (ej. es para español, en para inglés)."
            value={cfg.language} onChange={(e) => setCfg({ ...cfg, language: e.target.value })} />
        </div>

        {msg && (
          <div className={`text-sm px-3 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
            {msg.text}
          </div>
        )}

        <div className="flex gap-3 pt-1">
          <button onClick={save} disabled={saving}
            title="Guarda esta configuración en el servidor y la aplica de inmediato al dictado por voz de todos los usuarios del webmail."
            className="px-4 py-2 bg-ms-blue text-white rounded text-sm font-medium hover:bg-ms-blue-dark disabled:opacity-50">
            {saving ? "Guardando…" : "Guardar"}
          </button>
          <button onClick={test} disabled={testing}
            title="Comprueba que el servidor Whisper indicado esté disponible usando los datos del formulario, sin guardar nada. Úsalo antes de guardar."
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
