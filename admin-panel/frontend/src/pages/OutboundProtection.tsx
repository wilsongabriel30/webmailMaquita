import { useState, useEffect } from "react";
import { api } from "../api/client";

interface Limits {
  burst: number | null;
  rate_per_min: number | null;
  whitelist: string[];
}
interface ActivityRow { user: string; count: number; }
interface Activity { hours: number; note?: string; top: ActivityRow[]; }

export function OutboundProtection() {
  const [burst, setBurst] = useState<number>(200);
  const [rate, setRate] = useState<number>(3);
  const [wlText, setWlText] = useState("");
  const [act, setAct] = useState<ActivityRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [manualEmail, setManualEmail] = useState("");

  const wl = (txt: string) =>
    txt.split(/[,\s]+/).map((s) => s.trim().toLowerCase()).filter(Boolean);

  async function loadLimits() {
    const l = await api.get<Limits>("/admin/outbound/limits");
    if (l.burst != null) setBurst(l.burst);
    if (l.rate_per_min != null) setRate(l.rate_per_min);
    setWlText((l.whitelist || []).join(", "));
  }
  async function loadActivity() {
    const a = await api.get<Activity>("/admin/outbound/activity?hours=1");
    setAct(a.top || []);
  }

  useEffect(() => {
    Promise.all([loadLimits(), loadActivity()])
      .catch((e) => setMsg({ ok: false, text: e.message }))
      .finally(() => setLoading(false));
  }, []);

  async function save() {
    setSaving(true); setMsg(null);
    try {
      await api.put("/admin/outbound/limits", { burst, rate_per_min: rate, whitelist: wl(wlText) });
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
          <span className="text-gray-600 mb-1">Cuentas exentas (bulk legítimo) — separadas por coma</span>
          <textarea value={wlText} onChange={(e) => setWlText(e.target.value)} rows={2}
            placeholder="ventas@maquita.org, notificaciones@maquita.org"
            className="border rounded px-3 py-2 w-full" />
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
    </div>
  );
}
