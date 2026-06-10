import { useState, useEffect } from "react";
import { api } from "../api/client";

type Action = "warn" | "block" | "audit";
interface Rule { enabled: boolean; action: Action | null; }
interface DlpCfg {
  enabled: boolean;
  default_action: Action;
  rules: Record<string, Rule>;
  keywords: string[];
}
interface Violation {
  username: string; recipients: string[]; subject: string;
  data_types: string[]; action: string; overridden: boolean; created_at: string | null;
}

const DATA_TYPES: { key: string; label: string; desc: string; icon: string }[] = [
  { key: "cedula", label: "Cédula", desc: "Documentos de identidad ecuatorianos (10 dígitos, validados).", icon: "🪪" },
  { key: "ruc", label: "RUC", desc: "Registro Único de Contribuyentes (13 dígitos, validados).", icon: "🏢" },
  { key: "tarjeta", label: "Tarjetas de crédito", desc: "Números de tarjeta (Visa, Mastercard…), validados con Luhn.", icon: "💳" },
  { key: "iban", label: "IBAN", desc: "Cuentas bancarias internacionales (formato IBAN).", icon: "🌐" },
  { key: "cuenta", label: "Cuentas bancarias", desc: "Números de cuenta cuando aparecen junto a la palabra «cuenta».", icon: "🏦" },
  { key: "keyword", label: "Palabras clave", desc: "Las palabras confidenciales que definas más abajo.", icon: "🔑" },
];

const ACTION_LABEL: Record<string, string> = {
  warn: "Advertir y dejar decidir", block: "Bloquear el envío", audit: "Solo registrar",
};
const inputCls = "w-full px-3 py-2 border border-ms-gray-30 rounded text-sm";

export function DlpConfig() {
  const [cfg, setCfg] = useState<DlpCfg>({ enabled: true, default_action: "warn", rules: {}, keywords: [] });
  const [violations, setViolations] = useState<Violation[]>([]);
  const [newKw, setNewKw] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<DlpCfg>("/dlp-config").then(setCfg).catch(() => {}),
      api.get<{ violations: Violation[] }>("/dlp-config/violations").then((r) => setViolations(r.violations || [])).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const rule = (k: string): Rule => cfg.rules[k] || { enabled: true, action: null };
  const setRule = (k: string, patch: Partial<Rule>) =>
    setCfg({ ...cfg, rules: { ...cfg.rules, [k]: { ...rule(k), ...patch } } });

  const addKw = () => {
    const v = newKw.trim();
    if (v && !cfg.keywords.includes(v)) setCfg({ ...cfg, keywords: [...cfg.keywords, v] });
    setNewKw("");
  };
  const removeKw = (k: string) => setCfg({ ...cfg, keywords: cfg.keywords.filter((x) => x !== k) });

  const save = async () => {
    setSaving(true); setMsg(null);
    try {
      await api.put("/dlp-config", cfg);
      setMsg({ ok: true, text: "Cambios guardados. Ya están activos para todos los usuarios." });
    } catch (e: any) {
      setMsg({ ok: false, text: e?.message || "Error al guardar" });
    } finally { setSaving(false); }
  };

  if (loading) return <div className="p-6 text-sm text-ms-gray-110">Cargando…</div>;

  return (
    <div className="max-w-3xl">
      <h1 className="text-xl font-semibold text-ms-gray-160 mb-1">Protección de datos (DLP)</h1>
      <p className="text-sm text-ms-gray-110 mb-4">
        Evita que <b>datos sensibles salgan por correo</b> sin querer (cédulas, tarjetas, cuentas…).
        Cuando alguien intenta enviar uno, el sistema lo detecta y actúa según lo que configures aquí.
      </p>

      {/* Explicación amigable */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-5 text-sm text-ms-gray-130">
        <b>¿Cómo funciona, en simple?</b>
        <ul className="list-disc ml-5 mt-2 space-y-1">
          <li><b>Advertir:</b> el usuario ve un aviso antes de enviar y decide si continúa o cancela.</li>
          <li><b>Bloquear:</b> el correo no se envía. Máxima protección.</li>
          <li><b>Solo registrar:</b> el correo sale normal, pero queda anotado para que tú lo revises.</li>
        </ul>
        <p className="mt-2">Todo se revisa <b>dentro de tus servidores</b>; nada se manda a terceros.</p>
      </div>

      <div className="bg-white border border-ms-gray-30 rounded-lg p-5 space-y-5">
        {/* Interruptor maestro */}
        <label className="flex items-center gap-3 text-sm font-medium text-ms-gray-160">
          <input type="checkbox" className="w-4 h-4" checked={cfg.enabled}
            onChange={(e) => setCfg({ ...cfg, enabled: e.target.checked })} />
          <span>Protección de datos <b>{cfg.enabled ? "ACTIVADA" : "desactivada"}</b></span>
        </label>

        {/* Acción general */}
        <div className={cfg.enabled ? "" : "opacity-50 pointer-events-none"}>
          <label className="block text-sm font-medium text-ms-gray-130 mb-1">
            ¿Qué hacer cuando se detecta un dato sensible? <span className="text-ms-gray-110">(acción general)</span>
          </label>
          <select className={inputCls} value={cfg.default_action}
            onChange={(e) => setCfg({ ...cfg, default_action: e.target.value as Action })}>
            <option value="warn">Advertir y dejar decidir al usuario (recomendado)</option>
            <option value="block">Bloquear el envío</option>
            <option value="audit">Solo registrar (no molesta al usuario)</option>
          </select>
        </div>

        {/* Tipos de dato */}
        <div className={cfg.enabled ? "" : "opacity-50 pointer-events-none"}>
          <div className="text-sm font-medium text-ms-gray-130 mb-2">¿Qué datos vigilar?</div>
          <div className="space-y-2">
            {DATA_TYPES.map((dt) => (
              <div key={dt.key} className="flex items-center gap-3 border border-ms-gray-20 rounded-lg p-3">
                <input type="checkbox" className="w-4 h-4 shrink-0" checked={rule(dt.key).enabled}
                  onChange={(e) => setRule(dt.key, { enabled: e.target.checked })} />
                <span className="text-xl shrink-0">{dt.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-ms-gray-160">{dt.label}</div>
                  <div className="text-xs text-ms-gray-110">{dt.desc}</div>
                </div>
                <select className="px-2 py-1.5 border border-ms-gray-30 rounded text-xs shrink-0"
                  value={rule(dt.key).action || ""}
                  disabled={!rule(dt.key).enabled}
                  onChange={(e) => setRule(dt.key, { action: (e.target.value || null) as Action | null })}>
                  <option value="">Usar acción general ({ACTION_LABEL[cfg.default_action]})</option>
                  <option value="warn">Advertir</option>
                  <option value="block">Bloquear</option>
                  <option value="audit">Solo registrar</option>
                </select>
              </div>
            ))}
          </div>
        </div>

        {/* Palabras clave */}
        <div className={cfg.enabled ? "" : "opacity-50 pointer-events-none"}>
          <label className="block text-sm font-medium text-ms-gray-130 mb-1">
            Palabras clave confidenciales
          </label>
          <p className="text-xs text-ms-gray-110 mb-2">
            Ej.: «confidencial», «salarios», nombres de proyectos. Si aparecen en un correo, se aplica la regla de «Palabras clave».
          </p>
          <div className="flex gap-2 mb-2">
            <input className={inputCls} placeholder="Escribe una palabra y pulsa Agregar"
              value={newKw} onChange={(e) => setNewKw(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addKw(); } }} />
            <button onClick={addKw} className="px-3 py-2 bg-ms-gray-20 text-ms-gray-160 rounded text-sm whitespace-nowrap">Agregar</button>
          </div>
          <div className="flex flex-wrap gap-2">
            {cfg.keywords.length === 0 && <span className="text-xs text-ms-gray-110">Sin palabras clave aún.</span>}
            {cfg.keywords.map((k) => (
              <span key={k} className="inline-flex items-center gap-1 bg-blue-50 border border-blue-200 text-ms-gray-160 text-xs rounded-full pl-3 pr-1 py-1">
                {k}
                <button onClick={() => removeKw(k)} className="w-4 h-4 rounded-full hover:bg-blue-200 text-ms-gray-110">×</button>
              </span>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3 pt-1">
          <button onClick={save} disabled={saving}
            className="px-4 py-2 bg-ms-blue text-white rounded text-sm font-medium disabled:opacity-60">
            {saving ? "Guardando…" : "Guardar cambios"}
          </button>
          {msg && <span className={`text-sm ${msg.ok ? "text-green-700" : "text-red-600"}`}>{msg.text}</span>}
        </div>
      </div>

      {/* Actividad reciente */}
      <h2 className="text-base font-semibold text-ms-gray-160 mt-7 mb-1">Actividad reciente</h2>
      <p className="text-sm text-ms-gray-110 mb-3">Últimos correos donde se detectaron datos sensibles.</p>
      <div className="bg-white border border-ms-gray-30 rounded-lg overflow-hidden">
        {violations.length === 0 ? (
          <div className="p-4 text-sm text-ms-gray-110">Sin actividad todavía. 🎉</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-ms-gray-10 text-ms-gray-110 text-xs">
              <tr>
                <th className="text-left px-3 py-2 font-medium">Cuándo</th>
                <th className="text-left px-3 py-2 font-medium">Usuario</th>
                <th className="text-left px-3 py-2 font-medium">Datos detectados</th>
                <th className="text-left px-3 py-2 font-medium">Qué pasó</th>
              </tr>
            </thead>
            <tbody>
              {violations.map((v, i) => (
                <tr key={i} className="border-t border-ms-gray-20">
                  <td className="px-3 py-2 text-ms-gray-110 whitespace-nowrap">
                    {v.created_at ? new Date(v.created_at).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "short" }) : "—"}
                  </td>
                  <td className="px-3 py-2 text-ms-gray-160">{v.username}</td>
                  <td className="px-3 py-2 text-ms-gray-130">{v.data_types.join(", ")}</td>
                  <td className="px-3 py-2">
                    <span className={`text-xs rounded px-2 py-0.5 ${
                      v.action === "block" ? "bg-red-100 text-red-700" :
                      v.action === "warn" ? "bg-amber-100 text-amber-700" : "bg-ms-gray-20 text-ms-gray-130"}`}>
                      {ACTION_LABEL[v.action] || v.action}{v.overridden ? " · envió igual" : ""}
                    </span>
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
