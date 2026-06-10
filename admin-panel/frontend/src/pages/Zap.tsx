import { useState, useEffect } from "react";
import { api } from "../api/client";

interface Cfg {
  enabled: boolean; enforce: boolean; window_hours: number;
  include_phishing: boolean; max_per_user: number;
}
interface Action {
  id: number; username: string; subject: string; sender: string;
  bad_host: string; feed: string; status: string; created_at: string | null;
}

const STATUS: Record<string, { label: string; cls: string }> = {
  simulado: { label: "Simulado", cls: "bg-ms-gray-20 text-ms-gray-130" },
  cuarentena: { label: "En cuarentena", cls: "bg-amber-100 text-amber-700" },
  liberado: { label: "Liberado", cls: "bg-green-100 text-green-700" },
  error: { label: "Error", cls: "bg-red-100 text-red-700" },
};
const inputCls = "w-full px-3 py-2 border border-ms-gray-30 rounded text-sm";

export function Zap() {
  const [cfg, setCfg] = useState<Cfg>({ enabled: false, enforce: false, window_hours: 48, include_phishing: false, max_per_user: 200 });
  const [actions, setActions] = useState<Action[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const loadActions = () =>
    api.get<{ actions: Action[] }>("/zap/actions").then((r) => setActions(r.actions || [])).catch(() => {});

  useEffect(() => {
    Promise.all([
      api.get<Cfg>("/zap/config").then(setCfg).catch(() => {}),
      loadActions(),
    ]).finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true); setMsg(null);
    try { await api.put("/zap/config", cfg); setMsg({ ok: true, text: "Configuración guardada." }); }
    catch (e: any) { setMsg({ ok: false, text: e?.message || "Error al guardar" }); }
    finally { setSaving(false); }
  };

  const scan = async (simular: boolean) => {
    setScanning(true); setMsg(null);
    try {
      const r = await api.post<any>(`/zap/scan?simular=${simular ? "true" : "false"}`, {});
      if (r?.ok === false) { setMsg({ ok: false, text: r.reason || "ZAP deshabilitado" }); }
      else setMsg({ ok: true, text: `Revisados ${r.scanned} · Detectados ${r.flagged}` + (simular ? " (simulación)" : ` · Retirados ${r.moved}`) });
      await loadActions();
    } catch (e: any) { setMsg({ ok: false, text: e?.message || "Error al escanear" }); }
    finally { setScanning(false); }
  };

  const release = async (a: Action) => {
    const wl = confirm(`Soltar a la bandeja de ${a.username}.\n\n¿Además poner a "${a.sender}" en lista blanca para que sus correos SIEMPRE lleguen?\n\nAceptar = soltar + lista blanca · Cancelar = solo soltar`);
    try {
      await api.post(`/zap/release/${a.id}`, { whitelist: wl });
      setMsg({ ok: true, text: "Correo devuelto a la bandeja." + (wl ? " Remitente en lista blanca." : "") });
      await loadActions();
    } catch (e: any) { setMsg({ ok: false, text: e?.message || "Error al soltar" }); }
  };

  const clearSim = async () => {
    if (!confirm("¿Limpiar los registros de simulación? (no afecta correos)")) return;
    try { await api.del("/zap/actions/simulados"); await loadActions(); } catch { /* ignore */ }
  };

  const Toggle = ({ k, label, desc }: { k: keyof Cfg; label: string; desc: string }) => (
    <label className="flex items-start gap-3 cursor-pointer">
      <input type="checkbox" className="w-4 h-4 mt-0.5" checked={cfg[k] as boolean}
        onChange={(e) => setCfg({ ...cfg, [k]: e.target.checked })} />
      <span><span className="text-sm font-medium text-ms-gray-130">{label}</span>
        <span className="block text-xs text-ms-gray-110">{desc}</span></span>
    </label>
  );

  if (loading) return <div className="p-6 text-sm text-ms-gray-110">Cargando…</div>;

  return (
    <div className="p-6 max-w-5xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ms-gray-160">Retiro de correos maliciosos (ZAP)</h1>
        <p className="text-sm text-ms-gray-110 mt-1">
          Revisa correos ya entregados y, si un enlace resultó malicioso según la inteligencia de amenazas,
          los retira a cuarentena. <strong>Nunca borra</strong>: los mueve y puedes soltarlos con un clic.
        </p>
      </div>

      {msg && <div className={`text-sm px-4 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>{msg.text}</div>}

      <div className="bg-white border border-ms-gray-30 rounded-lg p-5 space-y-4">
        <Toggle k="enabled" label="ZAP activado" desc="Interruptor general. Si está apagado, no revisa ni retira nada." />
        <div className={cfg.enabled ? "space-y-4 pl-1" : "space-y-4 pl-1 opacity-50 pointer-events-none"}>
          <Toggle k="enforce"
            label="Retirar de verdad (si está apagado: solo SIMULACIÓN)"
            desc="En simulación detecta y registra qué retiraría, sin tocar los correos. Recomendado: empezar en simulación." />
          <Toggle k="include_phishing"
            label="Incluir phishing además de malware"
            desc="Por defecto solo malware (alta confianza). El phishing puede dar más falsos positivos." />
          <div className="flex gap-6">
            <label className="block">
              <span className="text-sm font-medium text-ms-gray-130">Ventana (horas)</span>
              <input type="number" className={inputCls + " w-32"} value={cfg.window_hours} min={1} max={720}
                onChange={(e) => setCfg({ ...cfg, window_hours: parseInt(e.target.value) || 48 })} />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-ms-gray-130">Máx. por usuario</span>
              <input type="number" className={inputCls + " w-32"} value={cfg.max_per_user} min={1} max={2000}
                onChange={(e) => setCfg({ ...cfg, max_per_user: parseInt(e.target.value) || 200 })} />
            </label>
          </div>
        </div>
        <div className="flex gap-3 pt-2">
          <button onClick={save} disabled={saving}
            className="px-4 py-2 bg-ms-blue text-white rounded text-sm disabled:opacity-50">
            {saving ? "Guardando…" : "Guardar configuración"}</button>
          <button onClick={() => scan(true)} disabled={scanning || !cfg.enabled}
            className="px-4 py-2 bg-ms-gray-20 text-ms-gray-160 rounded text-sm disabled:opacity-50">
            {scanning ? "Escaneando…" : "Escanear ahora (simulación)"}</button>
          <button onClick={() => scan(false)} disabled={scanning || !cfg.enabled || !cfg.enforce}
            className="px-4 py-2 bg-amber-600 text-white rounded text-sm disabled:opacity-50"
            title={!cfg.enforce ? "Activa 'Retirar de verdad' para aplicar" : ""}>
            {scanning ? "Escaneando…" : "Escanear y retirar"}</button>
        </div>
      </div>

      <div className="bg-white border border-ms-gray-30 rounded-lg p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-ms-gray-160">Correos detectados / retirados</h2>
          <button onClick={clearSim} className="text-xs text-ms-gray-110 hover:text-ms-gray-160">Limpiar simulaciones</button>
        </div>
        {actions.length === 0 ? (
          <p className="text-sm text-ms-gray-110">Sin registros. Ejecuta un escaneo en simulación para ver qué detectaría.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-ms-gray-110 border-b border-ms-gray-30">
                <th className="py-2 pr-3">Usuario</th><th className="pr-3">Asunto</th><th className="pr-3">Remitente</th>
                <th className="pr-3">Dominio malicioso</th><th className="pr-3">Tipo</th><th className="pr-3">Estado</th><th></th>
              </tr></thead>
              <tbody>
                {actions.map((a) => (
                  <tr key={a.id} className="border-b border-ms-gray-20">
                    <td className="py-2 pr-3 text-ms-gray-130">{a.username}</td>
                    <td className="pr-3 text-ms-gray-130 max-w-[220px] truncate" title={a.subject}>{a.subject}</td>
                    <td className="pr-3 text-ms-gray-110 max-w-[180px] truncate" title={a.sender}>{a.sender}</td>
                    <td className="pr-3 text-red-600">{a.bad_host}</td>
                    <td className="pr-3 text-ms-gray-110">{a.feed === "malware" ? "Malware" : "Phishing"}</td>
                    <td className="pr-3"><span className={`text-xs px-2 py-0.5 rounded ${STATUS[a.status]?.cls || ""}`}>{STATUS[a.status]?.label || a.status}</span></td>
                    <td className="text-right">
                      {a.status === "cuarentena" && (
                        <button onClick={() => release(a)} className="text-xs text-ms-blue hover:underline">Soltar a bandeja</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
