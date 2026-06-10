import { useState, useEffect } from "react";
import { api } from "../api/client";

interface Cfg {
  enabled: boolean; enforce: boolean; window_hours: number; max_per_user: number;
  quarantine_folder: string; quarantine_suspicious: boolean; scan_archives: boolean;
}
interface Result {
  id: number; username: string; subject: string; sender: string;
  filename: string; verdict: string; reasons: string; status: string; created_at: string | null;
}

const STATUS: Record<string, { label: string; cls: string }> = {
  simulado: { label: "Simulado", cls: "bg-ms-gray-20 text-ms-gray-130" },
  cuarentena: { label: "En cuarentena", cls: "bg-amber-100 text-amber-700" },
  liberado: { label: "Liberado", cls: "bg-green-100 text-green-700" },
  error: { label: "Error", cls: "bg-red-100 text-red-700" },
};
const VERDICT: Record<string, { label: string; cls: string }> = {
  malicious: { label: "Malicioso", cls: "text-red-600" },
  suspicious: { label: "Sospechoso", cls: "text-amber-600" },
  clean: { label: "Limpio", cls: "text-green-600" },
};
const inputCls = "w-full px-3 py-2 border border-ms-gray-30 rounded text-sm";

export function SafeAttachments() {
  const [cfg, setCfg] = useState<Cfg>({ enabled: false, enforce: false, window_hours: 24, max_per_user: 200, quarantine_folder: "Junk", quarantine_suspicious: false, scan_archives: true });
  const [results, setResults] = useState<Result[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const loadResults = () =>
    api.get<Result[]>("/safeattach/results").then((r) => setResults(r || [])).catch(() => {});

  useEffect(() => {
    Promise.all([
      api.get<Cfg>("/safeattach/config").then(setCfg).catch(() => {}),
      loadResults(),
    ]).finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true); setMsg(null);
    try { await api.put("/safeattach/config", cfg); setMsg({ ok: true, text: "Configuración guardada." }); }
    catch (e: any) { setMsg({ ok: false, text: e?.message || "Error al guardar" }); }
    finally { setSaving(false); }
  };

  const scan = async (dry: boolean) => {
    setScanning(true); setMsg(null);
    try {
      const r = await api.post<any>(`/safeattach/scan?dry=${dry ? "true" : "false"}`, {});
      if (r?.ok === false) { setMsg({ ok: false, text: r.reason || "Safe Attachments deshabilitado" }); }
      else setMsg({ ok: true, text: `Revisados ${r.scanned} · Con adjuntos ${r.with_attach} · Detectados ${r.flagged}` + (dry ? " (simulación)" : ` · Retirados ${r.moved}`) });
      await loadResults();
    } catch (e: any) { setMsg({ ok: false, text: e?.message || "Error al escanear" }); }
    finally { setScanning(false); }
  };

  const release = async (a: Result) => {
    if (!confirm(`Soltar a la bandeja de ${a.username} el correo con adjunto "${a.filename}".\n\n¿Continuar?`)) return;
    try {
      await api.post(`/safeattach/release/${a.id}`, {});
      setMsg({ ok: true, text: "Correo devuelto a la bandeja." });
      await loadResults();
    } catch (e: any) { setMsg({ ok: false, text: e?.message || "Error al soltar" }); }
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
        <h1 className="text-xl font-semibold text-ms-gray-160">Análisis de adjuntos (Safe Attachments)</h1>
        <p className="text-sm text-ms-gray-110 mt-1">
          Analiza los adjuntos de los correos entregados (ClamAV, macros de Office, PDF con JavaScript,
          ejecutables disfrazados, ZIP) y, si son maliciosos, retira el correo a cuarentena.
          <strong> Nunca borra</strong>: lo mueve y puedes soltarlo con un clic.
        </p>
      </div>

      {msg && <div className={`text-sm px-4 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>{msg.text}</div>}

      <div className="bg-white border border-ms-gray-30 rounded-lg p-5 space-y-4">
        <Toggle k="enabled" label="Safe Attachments activado" desc="Interruptor general. Si está apagado, no analiza ni retira nada." />
        <div className={cfg.enabled ? "space-y-4 pl-1" : "space-y-4 pl-1 opacity-50 pointer-events-none"}>
          <Toggle k="enforce" label="Retirar de verdad (si está apagado: solo SIMULACIÓN)"
            desc="En simulación detecta y registra qué retiraría, sin tocar los correos. Recomendado: empezar en simulación." />
          <Toggle k="quarantine_suspicious" label="Retirar también los 'sospechosos'"
            desc="Por defecto solo retira los 'maliciosos'. Los sospechosos (ej. documento con macros) pueden dar más falsos positivos." />
          <Toggle k="scan_archives" label="Analizar dentro de archivos comprimidos (ZIP)"
            desc="Inspecciona el contenido de los ZIP de forma recursiva." />
          <div className="flex gap-6">
            <label className="block">
              <span className="text-sm font-medium text-ms-gray-130">Ventana (horas)</span>
              <input type="number" className={inputCls + " w-32"} value={cfg.window_hours} min={1} max={720}
                onChange={(e) => setCfg({ ...cfg, window_hours: parseInt(e.target.value) || 24 })} />
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
        <h2 className="text-sm font-semibold text-ms-gray-160 mb-3">Adjuntos detectados / retirados</h2>
        {results.length === 0 ? (
          <p className="text-sm text-ms-gray-110">Sin registros. Ejecuta un escaneo en simulación para ver qué detectaría.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-ms-gray-110 border-b border-ms-gray-30">
                <th className="py-2 pr-3">Usuario</th><th className="pr-3">Asunto</th><th className="pr-3">Adjunto</th>
                <th className="pr-3">Veredicto</th><th className="pr-3">Motivo</th><th className="pr-3">Estado</th><th></th>
              </tr></thead>
              <tbody>
                {results.map((a) => (
                  <tr key={a.id} className="border-b border-ms-gray-20">
                    <td className="py-2 pr-3 text-ms-gray-130">{a.username}</td>
                    <td className="pr-3 text-ms-gray-130 max-w-[180px] truncate" title={a.subject}>{a.subject}</td>
                    <td className="pr-3 text-ms-gray-130 max-w-[160px] truncate" title={a.filename}>{a.filename}</td>
                    <td className={`pr-3 font-medium ${VERDICT[a.verdict]?.cls || ""}`}>{VERDICT[a.verdict]?.label || a.verdict}</td>
                    <td className="pr-3 text-ms-gray-110 max-w-[260px] truncate" title={a.reasons}>{a.reasons}</td>
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
