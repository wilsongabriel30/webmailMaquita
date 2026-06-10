import { useState, useEffect } from "react";
import { api } from "../api/client";

interface Cfg { enabled: boolean; expire_days: number; max_views: number; intro_text: string; }
interface Msg {
  token: string; sender: string; subject: string; recipients: string[];
  status: string; view_count: number; created_at: string | null; expires_at: string | null;
}

const STATUS: Record<string, { label: string; cls: string }> = {
  abierto: { label: "Abierto ✓", cls: "bg-green-100 text-green-700" },
  no_abierto: { label: "Sin abrir", cls: "bg-amber-100 text-amber-700" },
  caducado: { label: "Caducado", cls: "bg-ms-gray-20 text-ms-gray-130" },
  revocado: { label: "Revocado", cls: "bg-red-100 text-red-700" },
};
const inputCls = "w-full px-3 py-2 border border-ms-gray-30 rounded text-sm";

export function SecureConfig() {
  const [cfg, setCfg] = useState<Cfg>({ enabled: true, expire_days: 7, max_views: 0, intro_text: "" });
  const [messages, setMessages] = useState<Msg[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const loadMsgs = () =>
    api.get<{ messages: Msg[] }>("/secure-config/messages").then((r) => setMessages(r.messages || [])).catch(() => {});

  useEffect(() => {
    Promise.all([
      api.get<Cfg>("/secure-config").then(setCfg).catch(() => {}),
      loadMsgs(),
    ]).finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true); setMsg(null);
    try {
      await api.put("/secure-config", cfg);
      setMsg({ ok: true, text: "Cambios guardados." });
    } catch (e: any) {
      setMsg({ ok: false, text: e?.message || "Error al guardar" });
    } finally { setSaving(false); }
  };

  const revoke = async (token: string) => {
    if (!window.confirm("¿Revocar este mensaje? El destinatario ya no podrá abrirlo.")) return;
    try { await api.post(`/secure-config/messages/${token}/revoke`, {}); await loadMsgs(); }
    catch (e: any) { setMsg({ ok: false, text: e?.message || "Error al revocar" }); }
  };

  if (loading) return <div className="p-6 text-sm text-ms-gray-110">Cargando…</div>;

  return (
    <div className="max-w-3xl">
      <h1 className="text-xl font-semibold text-ms-gray-160 mb-1">Correo cifrado (mensaje seguro)</h1>
      <p className="text-sm text-ms-gray-110 mb-4">
        Permite enviar correos que <b>solo el destinatario puede abrir</b>, confirmando su identidad con un
        código. Ideal para documentos confidenciales. Funciona con cualquier destinatario (Gmail, Outlook…)
        sin que necesite instalar nada.
      </p>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-5 text-sm text-ms-gray-130">
        <b>¿Cómo lo vive el destinatario?</b>
        <ol className="list-decimal ml-5 mt-2 space-y-1">
          <li>Recibe un correo normal: «Tienes un mensaje seguro» con un botón.</li>
          <li>Hace clic y se abre una página de Maquita.</li>
          <li>Pone su correo y recibe un <b>código de un solo uso</b> en su email.</li>
          <li>Escribe el código y <b>lee el mensaje</b> (y descarga adjuntos).</li>
        </ol>
        <p className="mt-2">El contenido viaja <b>cifrado</b> y vive en tus servidores; en el correo solo va un enlace.</p>
      </div>

      <div className="bg-white border border-ms-gray-30 rounded-lg p-5 space-y-4">
        <label className="flex items-center gap-3 text-sm font-medium text-ms-gray-160">
          <input type="checkbox" className="w-4 h-4" checked={cfg.enabled}
            onChange={(e) => setCfg({ ...cfg, enabled: e.target.checked })} />
          <span>Correo cifrado <b>{cfg.enabled ? "ACTIVADO" : "desactivado"}</b>
            <span className="text-ms-gray-110 font-normal"> — {cfg.enabled ? "el botón «Cifrar» aparece en el correo" : "el botón no aparece"}</span></span>
        </label>

        <div className={cfg.enabled ? "grid grid-cols-2 gap-4" : "grid grid-cols-2 gap-4 opacity-50 pointer-events-none"}>
          <div>
            <label className="block text-sm font-medium text-ms-gray-130 mb-1">Caduca a los (días)</label>
            <input type="number" min={0} max={365} className={inputCls} value={cfg.expire_days}
              onChange={(e) => setCfg({ ...cfg, expire_days: parseInt(e.target.value || "0") })} />
            <p className="text-xs text-ms-gray-110 mt-1">0 = no caduca nunca.</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-ms-gray-130 mb-1">Máximo de aperturas</label>
            <input type="number" min={0} max={1000} className={inputCls} value={cfg.max_views}
              onChange={(e) => setCfg({ ...cfg, max_views: parseInt(e.target.value || "0") })} />
            <p className="text-xs text-ms-gray-110 mt-1">0 = sin límite.</p>
          </div>
        </div>

        <div className={cfg.enabled ? "" : "opacity-50 pointer-events-none"}>
          <label className="block text-sm font-medium text-ms-gray-130 mb-1">Mensaje en el correo de aviso (opcional)</label>
          <input className={inputCls} placeholder="Ej.: Este documento es confidencial de Fundación Maquita."
            value={cfg.intro_text} onChange={(e) => setCfg({ ...cfg, intro_text: e.target.value })} />
        </div>

        <div className="flex items-center gap-3 pt-1">
          <button onClick={save} disabled={saving}
            className="px-4 py-2 bg-ms-blue text-white rounded text-sm font-medium disabled:opacity-60">
            {saving ? "Guardando…" : "Guardar cambios"}
          </button>
          {msg && <span className={`text-sm ${msg.ok ? "text-green-700" : "text-red-600"}`}>{msg.text}</span>}
        </div>
      </div>

      <h2 className="text-base font-semibold text-ms-gray-160 mt-7 mb-1">Mensajes seguros enviados</h2>
      <p className="text-sm text-ms-gray-110 mb-3">Puedes <b>revocar</b> cualquiera para que deje de poder abrirse.</p>
      <div className="bg-white border border-ms-gray-30 rounded-lg overflow-hidden">
        {messages.length === 0 ? (
          <div className="p-4 text-sm text-ms-gray-110">Aún no se han enviado mensajes seguros.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-ms-gray-10 text-ms-gray-110 text-xs">
              <tr>
                <th className="text-left px-3 py-2 font-medium">Cuándo</th>
                <th className="text-left px-3 py-2 font-medium">De</th>
                <th className="text-left px-3 py-2 font-medium">Asunto</th>
                <th className="text-left px-3 py-2 font-medium">Para</th>
                <th className="text-left px-3 py-2 font-medium">Estado</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {messages.map((m) => {
                const st = STATUS[m.status] || { label: m.status, cls: "bg-ms-gray-20 text-ms-gray-130" };
                const canRevoke = m.status === "abierto" || m.status === "no_abierto";
                return (
                  <tr key={m.token} className="border-t border-ms-gray-20">
                    <td className="px-3 py-2 text-ms-gray-110 whitespace-nowrap">
                      {m.created_at ? new Date(m.created_at).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "short" }) : "—"}
                    </td>
                    <td className="px-3 py-2 text-ms-gray-160">{m.sender}</td>
                    <td className="px-3 py-2 text-ms-gray-130 max-w-[160px] truncate">{m.subject || "(sin asunto)"}</td>
                    <td className="px-3 py-2 text-ms-gray-110 max-w-[160px] truncate">{m.recipients.join(", ")}</td>
                    <td className="px-3 py-2"><span className={`text-xs rounded px-2 py-0.5 ${st.cls}`}>{st.label}</span></td>
                    <td className="px-3 py-2 text-right">
                      {canRevoke && (
                        <button onClick={() => revoke(m.token)}
                          className="text-xs text-red-600 hover:underline">Revocar</button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
