import { useState, useEffect } from "react";
import { api } from "../api/client";

interface Status { anti_spoof: boolean; protected_domains: string[]; reject_score: number; }
interface Cfg {
  impersonation_enabled: boolean;
  impersonation_terms: string[];
  dlp_block_cards_external: boolean;
  status: Status;
}

function Toggle({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} className={`relative w-11 h-6 rounded-full transition shrink-0 ${on ? "bg-[#0078d4]" : "bg-ms-gray-40"}`}>
      <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition ${on ? "translate-x-5" : ""}`} />
    </button>
  );
}

export function SecurityPolicies() {
  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [newTerm, setNewTerm] = useState("");

  useEffect(() => {
    api.get<Cfg>("/security-policies").then((d) => setCfg(d)).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const save = async () => {
    if (!cfg) return;
    setSaving(true); setMsg(null);
    try {
      await api.post("/security-policies", {
        impersonation_enabled: cfg.impersonation_enabled,
        impersonation_terms: cfg.impersonation_terms,
        dlp_block_cards_external: cfg.dlp_block_cards_external,
      });
      setMsg({ ok: true, text: "Cambios guardados. El filtro los aplica en ~20 segundos." });
    } catch {
      setMsg({ ok: false, text: "No se pudo guardar." });
    }
    setSaving(false);
  };

  if (loading) return <div className="p-6 text-ms-gray-110">Cargando…</div>;
  if (!cfg) return <div className="p-6 text-red-700">No se pudo cargar la configuración.</div>;

  return (
    <div className="p-6 max-w-3xl">
      <h1 className="text-xl font-semibold text-ms-gray-130 mb-1">Anti-suplantación y políticas</h1>
      <p className="text-sm text-ms-gray-110 mb-6">Controles contra suplantación de identidad y fuga de datos en el correo.</p>

      <div className="border border-ms-gray-30 rounded-lg p-4 mb-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-ms-gray-130">Anti-spoofing de dominio propio</h2>
            <p className="text-sm text-ms-gray-110">Rechaza correo que dice venir de tus dominios pero llega desde el exterior sin autenticación válida (SPF/DKIM/DMARC).</p>
          </div>
          <span className="text-xs px-2 py-1 rounded bg-green-100 text-green-800 font-medium shrink-0">Activo</span>
        </div>
        <div className="mt-3 text-xs text-ms-gray-110">
          Dominios protegidos ({cfg.status.protected_domains.length}):
          <div className="flex flex-wrap gap-1 mt-1">
            {cfg.status.protected_domains.map((d) => <span key={d} className="px-2 py-0.5 bg-ms-gray-10 rounded">{d}</span>)}
          </div>
          <p className="mt-2 italic">Incluye subdominios. Gestionado por reglas Rspamd.</p>
        </div>
      </div>

      <div className="border border-ms-gray-30 rounded-lg p-4 mb-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-ms-gray-130">Anti-impersonation por nombre visible</h2>
            <p className="text-sm text-ms-gray-110">Pone en cuarentena el correo de dominios ajenos cuyo nombre mostrado suplanta tu marca (ej. «Dirección Maquita &lt;x@gmail.com&gt;»).</p>
          </div>
          <Toggle on={cfg.impersonation_enabled} onClick={() => setCfg({ ...cfg, impersonation_enabled: !cfg.impersonation_enabled })} />
        </div>
        {cfg.impersonation_enabled && (
          <div className="mt-3">
            <label className="text-xs text-ms-gray-110">Términos de marca a proteger:</label>
            <div className="flex flex-wrap gap-1 mt-1">
              {cfg.impersonation_terms.map((t) => (
                <span key={t} className="px-2 py-0.5 bg-blue-50 text-blue-800 rounded text-xs flex items-center gap-1">
                  {t}
                  <button onClick={() => setCfg({ ...cfg, impersonation_terms: cfg.impersonation_terms.filter((x) => x !== t) })} className="text-blue-500 hover:text-red-600 font-bold">×</button>
                </span>
              ))}
            </div>
            <div className="flex gap-2 mt-2">
              <input value={newTerm} onChange={(e) => setNewTerm(e.target.value)} placeholder="agregar término (ej. fundacion)"
                className="px-2 py-1 border border-ms-gray-30 rounded text-sm flex-1" />
              <button onClick={() => { const t = newTerm.trim().toLowerCase(); if (t && !cfg.impersonation_terms.includes(t)) setCfg({ ...cfg, impersonation_terms: [...cfg.impersonation_terms, t] }); setNewTerm(""); }}
                className="px-3 py-1 bg-ms-gray-20 rounded text-sm">Agregar</button>
            </div>
          </div>
        )}
      </div>

      <div className="border border-ms-gray-30 rounded-lg p-4 mb-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-ms-gray-130">Bloqueo de tarjetas de crédito salientes</h2>
            <p className="text-sm text-ms-gray-110">Rechaza el correo a destinatarios externos que contenga números de tarjeta (validados con Luhn). El correo interno no se bloquea.</p>
          </div>
          <Toggle on={cfg.dlp_block_cards_external} onClick={() => setCfg({ ...cfg, dlp_block_cards_external: !cfg.dlp_block_cards_external })} />
        </div>
      </div>

      <div className="border border-ms-gray-30 rounded-lg p-4 mb-6">
        <h2 className="font-semibold text-ms-gray-130">Umbral de rechazo de spam</h2>
        <p className="text-sm text-ms-gray-110">El correo con puntaje de spam ≥ <b>{cfg.status.reject_score}</b> se rechaza en la conexión (basura evidente, como sextorsión). Gestionado en Rspamd.</p>
      </div>

      {msg && <div className={`mb-3 text-sm ${msg.ok ? "text-green-700" : "text-red-700"}`}>{msg.text}</div>}
      <button onClick={save} disabled={saving} className="px-5 py-2 bg-[#0078d4] text-white rounded font-medium disabled:opacity-50">
        {saving ? "Guardando…" : "Guardar cambios"}
      </button>
    </div>
  );
}
