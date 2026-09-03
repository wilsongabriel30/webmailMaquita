import { useState, useEffect } from "react";
import { api } from "../api/client";

interface Limits {
  burst: number | null;
  rate_per_min: number | null;
  whitelist: string[];
  dlp_exempt?: string[];
}
interface ActivityRow { user: string; count: number; }
interface Activity { hours: number; note?: string; top: ActivityRow[]; }

export function OutboundProtection() {
  const [burst, setBurst] = useState<number>(200);
  const [rate, setRate] = useState<number>(3);
  const [wlText, setWlText] = useState("");
  const [dlpText, setDlpText] = useState("");
  const [act, setAct] = useState<ActivityRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [manualEmail, setManualEmail] = useState("");
  const [anom, setAnom] = useState<any>(null);
  const [anomEvents, setAnomEvents] = useState<any[]>([]);

  const wl = (txt: string) =>
    txt.split(/[,\s]+/).map((s) => s.trim().toLowerCase()).filter(Boolean);

  async function loadLimits() {
    const l = await api.get<Limits>("/admin/outbound/limits");
    if (l.burst != null) setBurst(l.burst);
    if (l.rate_per_min != null) setRate(l.rate_per_min);
    setWlText((l.whitelist || []).join(", "));
    setDlpText((l.dlp_exempt || []).join(", "));
  }
  async function loadActivity() {
    const a = await api.get<Activity>("/admin/outbound/activity?hours=1");
    setAct(a.top || []);
  }

  useEffect(() => {
    Promise.all([loadLimits(), loadActivity(), loadAnomaly()])
      .catch((e) => setMsg({ ok: false, text: e.message }))
      .finally(() => setLoading(false));
  }, []);

  async function loadAnomaly() {
    const c = await api.get<any>("/outbound-anomaly/config").catch(() => null);
    if (c) setAnom(c);
    const e = await api.get<{ events: any[] }>("/outbound-anomaly/events?limit=20").catch(() => null);
    if (e) setAnomEvents(e.events || []);
  }
  async function saveAnomaly() {
    setSaving(true); setMsg(null);
    try {
      await api.put("/outbound-anomaly/config", anom);
      setMsg({ ok: true, text: "Deteccion de envio masivo guardada." });
      await loadAnomaly();
    } catch (e: any) { setMsg({ ok: false, text: e.message }); }
    finally { setSaving(false); }
  }

  async function save() {
    setSaving(true); setMsg(null);
    try {
      await api.put("/admin/outbound/limits", { burst, rate_per_min: rate, whitelist: wl(wlText), dlp_exempt: wl(dlpText) });
      await loadLimits();
      setMsg({ ok: true, text: "Límite aplicado y rspamd recargado." });
    } catch (e: any) {
      setMsg({ ok: false, text: e.message });
    } finally { setSaving(false); }
  }

  async function lock(email: string) {
    if (!email || !email.includes("@")) { setMsg({ ok: false, text: "Email inválido" }); return; }
    if (!confirm(`¿Contener (bloquear envío + cerrar sesión + vaciar cola) de ${email}?`)) return;
    setMsg(null);
    try {
      const r = await api.post<{ output: string }>("/admin/outbound/lock", { email });
      setMsg({ ok: true, text: `Bloqueado ${email}. ${r.output || ""}` });
      loadActivity();
    } catch (e: any) { setMsg({ ok: false, text: e.message }); }
  }
  async function unlock(email: string) {
    if (!email || !email.includes("@")) { setMsg({ ok: false, text: "Email inválido" }); return; }
    setMsg(null);
    try {
      const r = await api.post<{ output: string }>("/admin/outbound/unlock", { email });
      setMsg({ ok: true, text: `Reactivado ${email}. ${r.output || ""}` });
    } catch (e: any) { setMsg({ ok: false, text: e.message }); }
  }

  if (loading) return <div className="p-6">Cargando…</div>;

  return (
    <div className="p-6 max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Protección de salida</h1>
        <p className="text-gray-500 text-sm mt-1">
          Límite de envío por usuario autenticado: frena una cuenta comprometida antes de que mande spam masivo
          (lección del incidente Zimbra). Al exceder el límite, el correo se difiere (DEFER); el usuario legítimo reintenta.
        </p>
      </div>

      {msg && (
        <div className={`p-3 rounded text-sm ${msg.ok ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}>
          {msg.text}
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-5 space-y-4">
        <h2 className="font-semibold">Límite por usuario</h2>
        <div className="flex flex-wrap gap-4">
          <label className="flex flex-col text-sm">
            <span className="text-gray-600 mb-1">Ráfaga inicial (burst)</span>
            <input type="number" min={1} value={burst} onChange={(e) => setBurst(+e.target.value)}
              className="border rounded px-3 py-2 w-40" />
          </label>
          <label className="flex flex-col text-sm">
            <span className="text-gray-600 mb-1">Sostenido (correos / minuto)</span>
            <input type="number" min={1} value={rate} onChange={(e) => setRate(+e.target.value)}
              className="border rounded px-3 py-2 w-40" />
          </label>
        </div>
        <p className="text-xs text-gray-400">
          Equivale a ~{rate * 60} correos/hora sostenidos tras una ráfaga de {burst}. Sugerido: burst 200, {`${rate}/min`}.
        </p>
        <label className="flex flex-col text-sm">
          <span className="text-gray-600 mb-1">Cuentas exentas del límite y del detector de envío masivo (bulk legítimo) — separadas por coma</span>
          <textarea value={wlText} onChange={(e) => setWlText(e.target.value)} rows={2}
            placeholder="noreply@maquita.org, comunicacion@maquita.org"
            className="border rounded px-3 py-2 w-full" />
          <span className="text-xs text-gray-400 mt-1">Úsala también, de forma temporal, cuando alguien deba enviar un correo a todo el personal: así no se le bloquea la cuenta.</span>
        </label>
        <label className="flex flex-col text-sm">
          <span className="text-gray-600 mb-1">Cuentas de sistema exentas de la Protección de datos (DLP) hacia externos — separadas por coma</span>
          <textarea value={dlpText} onChange={(e) => setDlpText(e.target.value)} rows={2}
            placeholder="noreply@maquita.org"
            className="border rounded px-3 py-2 w-full" />
          <span className="text-xs text-gray-400 mt-1">Solo para remitentes automáticos que por diseño envían datos personales a su propio dueño (p. ej. Raíces Nómina envía a cada trabajador su rol con cédula a su correo personal). No agregar cuentas de personas.</span>
        </label>
        <button onClick={save} disabled={saving}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50">
          {saving ? "Guardando…" : "Guardar y aplicar"}
        </button>
      </div>

      <div className="bg-white rounded-lg shadow p-5 space-y-3">
        <h2 className="font-semibold">Contención manual</h2>
        <div className="flex flex-wrap gap-2 items-center">
          <input value={manualEmail} onChange={(e) => setManualEmail(e.target.value)}
            placeholder="usuario@dominio" className="border rounded px-3 py-2 flex-1 min-w-[220px]" />
          <button onClick={() => lock(manualEmail.trim().toLowerCase())}
            className="bg-red-600 text-white px-3 py-2 rounded hover:bg-red-700">Bloquear</button>
          <button onClick={() => unlock(manualEmail.trim().toLowerCase())}
            className="bg-gray-200 px-3 py-2 rounded hover:bg-gray-300">Desbloquear</button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">Volumen de salida (hoy)</h2>
          <button onClick={() => loadActivity()} className="text-sm text-blue-600 hover:underline">Actualizar</button>
        </div>
        {act.length === 0 ? (
          <p className="text-sm text-gray-400">Sin envíos registrados.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="py-2">Remitente</th><th className="py-2">Envíos</th><th></th>
              </tr>
            </thead>
            <tbody>
              {act.map((r) => (
                <tr key={r.user} className="border-b last:border-0">
                  <td className="py-2">{r.user}</td>
                  <td className="py-2 font-mono">{r.count}</td>
                  <td className="py-2 text-right">
                    <button onClick={() => lock(r.user)}
                      className="text-red-600 hover:underline text-xs">Bloquear</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {anom && (
      <div className="bg-white border border-ms-gray-30 rounded-lg p-4 space-y-3 mt-4">
        <div>
          <h2 className="text-sm font-semibold text-ms-gray-160">Deteccion automatica de envio masivo (cuenta comprometida)</h2>
          <p className="text-xs text-ms-gray-110">Si una cuenta envia a mas destinatarios de lo normal en pocos minutos, se bloquea el envio automaticamente y se avisa. El correo institucional envia pocos al dia; un envio masivo repentino es senal de cuenta robada. Asi evitamos que la IP caiga en listas negras.</p>
        </div>
        <div className="flex flex-wrap gap-4 items-end">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={!!anom.enabled} onChange={(e) => setAnom({ ...anom, enabled: e.target.checked })} />
            Activo
          </label>
          <div>
            <label className="block text-xs text-ms-gray-110">Destinatarios (umbral)</label>
            <input type="number" min={3} value={anom.threshold_recipients} onChange={(e) => setAnom({ ...anom, threshold_recipients: Number(e.target.value) })}
              title="Si una cuenta supera esta cantidad de destinatarios dentro de la ventana, se considera anomalia. Normal institucional: 10-20 al dia." className="border border-ms-gray-30 rounded px-2 py-1 text-sm w-24" />
          </div>
          <div>
            <label className="block text-xs text-ms-gray-110">Ventana (minutos)</label>
            <input type="number" min={1} value={anom.window_minutes} onChange={(e) => setAnom({ ...anom, window_minutes: Number(e.target.value) })}
              title="Periodo en el que se cuentan los envios (ej. 10 minutos)." className="border border-ms-gray-30 rounded px-2 py-1 text-sm w-20" />
          </div>
          <div>
            <label className="block text-xs text-ms-gray-110">Accion</label>
            <select value={anom.action} onChange={(e) => setAnom({ ...anom, action: e.target.value })}
              title="Bloquear: contiene la cuenta y avisa. Solo alertar: unicamente avisa sin bloquear." className="border border-ms-gray-30 rounded px-2 py-1 text-sm">
              <option value="lock">Bloquear cuenta</option>
              <option value="alert">Solo alertar</option>
            </select>
          </div>
          <div className="flex-1" style={{ minWidth: "14rem" }}>
            <label className="block text-xs text-ms-gray-110">Avisar a (correo del administrador)</label>
            <input value={anom.notify_admin} onChange={(e) => setAnom({ ...anom, notify_admin: e.target.value })}
              title="Direccion que recibe el aviso de seguridad cuando se detecta un envio masivo." className="border border-ms-gray-30 rounded px-2 py-1 text-sm w-full" />
          </div>
          <button onClick={saveAnomaly} disabled={saving} className="text-white text-sm px-4 py-2 rounded" style={{ backgroundColor: "#0078d4" }}>Guardar</button>
        </div>

        <div>
          <h3 className="text-xs font-semibold text-ms-gray-160 mt-2 mb-1">Detecciones recientes</h3>
          {anomEvents.length === 0 ? (
            <p className="text-xs text-ms-gray-110">Sin detecciones. (Si aparece alguna, revisa la cuenta: cambia contrasena y activa 2FA.)</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-ms-gray-110 text-left"><tr>
                <th className="py-1">Cuenta</th><th className="py-1">Volumen</th><th className="py-1">Accion</th><th className="py-1">Cuando</th>
              </tr></thead>
              <tbody>
                {anomEvents.map((ev) => (
                  <tr key={ev.id} className="border-t border-ms-gray-30">
                    <td className="py-1">{ev.username}</td>
                    <td className="py-1 font-mono">{ev.recipients} dest / {ev.messages} msj</td>
                    <td className="py-1">{ev.action === "locked" ? "Bloqueada" : "Alertada"}</td>
                    <td className="py-1 text-ms-gray-110">{ev.created_at ? new Date(ev.created_at).toLocaleString() : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
      )}
    </div>
  );
}
