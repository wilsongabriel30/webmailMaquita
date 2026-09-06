import { useState, useEffect } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

type Action = "warn" | "block" | "audit";
interface Rule { enabled: boolean; action: Action | null; }
interface DlpCfg {
  enabled: boolean;
  default_action: Action;
  rules: Record<string, Rule>;
  keywords: string[];
  milter_enforce: boolean;
  scan_attachments: boolean;
  trusted_domains: string[];
  remitentes_exentos: string[];
}
interface Violation {
  username: string; recipients: string[]; subject: string;
  data_types: string[]; action: string; overridden: boolean; created_at: string | null;
  reason?: string | null; external?: boolean;
}

/* Niveles de seguridad: presets que rellenan toda la configuración de una vez. */
type Level = "off" | "audit" | "warn" | "block" | "custom";
const LEVELS: { key: Level; label: string; desc: string; color: string }[] = [
  { key: "off",   label: "Desactivado",        desc: "No se revisa nada. Los correos salen sin control.", color: "border-ms-gray-30" },
  { key: "audit", label: "Solo observar",      desc: "Todo sale normal, pero queda registrado aquí lo que contenía datos sensibles.", color: "border-ms-gray-60" },
  { key: "warn",  label: "Avisar",             desc: "El usuario ve un aviso y decide si envía. Desde Outlook/móvil solo se registra.", color: "border-amber-400" },
  { key: "block", label: "Bloquear a externos", desc: "Cédulas, tarjetas, IBAN y cuentas NO salen a dominios externos (webmail y Outlook/móvil). Solo un administrador puede forzar el envío con motivo. Recomendado.", color: "border-red-500" },
];
const BLOCK_TYPES = ["cedula", "tarjeta", "iban", "cuenta"];
function detectLevel(c: DlpCfg): Level {
  if (!c.enabled) return "off";
  const acts = Object.keys(c.rules).map((k) => c.rules[k]?.enabled === false ? "off" : (c.rules[k]?.action || c.default_action));
  const all = (a: string) => acts.length > 0 && acts.every((x) => x === a);
  if (c.default_action === "audit" && all("audit")) return "audit";
  if (c.default_action === "warn" && all("warn")) return "warn";
  const isBlock = BLOCK_TYPES.every((k) => (c.rules[k]?.action || c.default_action) === "block" && c.rules[k]?.enabled !== false)
    && ["ruc", "keyword"].every((k) => (c.rules[k]?.action || c.default_action) !== "block");
  if (isBlock && c.milter_enforce) return "block";
  return "custom";
}
function applyLevel(c: DlpCfg, lv: Level): DlpCfg {
  const keys = ["cedula", "ruc", "tarjeta", "iban", "cuenta", "keyword"];
  const rules: Record<string, Rule> = {};
  if (lv === "off") return { ...c, enabled: false };
  if (lv === "audit" || lv === "warn") {
    keys.forEach((k) => (rules[k] = { enabled: true, action: lv }));
    return { ...c, enabled: true, default_action: lv, rules, milter_enforce: false };
  }
  if (lv === "block") {
    keys.forEach((k) => (rules[k] = { enabled: true, action: BLOCK_TYPES.includes(k) ? "block" : "warn" }));
    return { ...c, enabled: true, default_action: "warn", rules, milter_enforce: true, scan_attachments: true };
  }
  return c;
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
  milter_log: "Outlook/móvil · registrado", milter_warn: "Outlook/móvil · registrado", milter_audit: "Outlook/móvil · registrado",
  milter_block: "Outlook/móvil · registrado (sin rechazo)", milter_reject: "Outlook/móvil · rechazado",
};
const inputCls = "w-full px-3 py-2 border border-ms-gray-30 rounded text-sm";

export function DlpConfig() {
  const [cfg, setCfg] = useState<DlpCfg>({ enabled: true, default_action: "warn", rules: {}, keywords: [], milter_enforce: false, scan_attachments: true, trusted_domains: [], remitentes_exentos: [] });
  const [newDom, setNewDom] = useState("");
  const level = detectLevel(cfg);
  const addDom = () => {
    const v = newDom.trim().toLowerCase().replace(/^@/, "");
    if (v && !cfg.trusted_domains.includes(v)) setCfg({ ...cfg, trusted_domains: [...cfg.trusted_domains, v] });
    setNewDom("");
  };
  const removeDom = (d: string) => setCfg({ ...cfg, trusted_domains: cfg.trusted_domains.filter((x) => x !== d) });
  const [newExento, setNewExento] = useState("");
  const addExento = () => {
    const v = newExento.trim().toLowerCase();
    if (v && v.includes("@") && !cfg.remitentes_exentos.includes(v)) {
      setCfg({ ...cfg, remitentes_exentos: [...cfg.remitentes_exentos, v] });
      setNewExento("");
    }
  };
  const removeExento = (d: string) =>
    setCfg({ ...cfg, remitentes_exentos: cfg.remitentes_exentos.filter((x) => x !== d) });
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
      <div className="flex justify-end">
        <SectionHelp
          titulo="Protección de datos (DLP)"
          items={[
            { titulo: "Qué es", desc: "Detecta datos sensibles (cédulas, RUC, tarjetas, cuentas, IBAN o palabras clave) en los correos salientes y actúa antes de que salgan. Todo se analiza en tus propios servidores, sin terceros." },
            { titulo: "Interruptor general", desc: "Activa o desactiva toda la protección. Desactivado, los correos salen sin revisión y no se registra nada." },
            { titulo: "Acción general", desc: "Qué hacer al detectar un dato sensible: Advertir (el usuario decide), Bloquear (el correo no sale) o Solo registrar (sale normal pero queda anotado aquí)." },
            { titulo: "Tipos de dato", desc: "Marca qué datos vigilar y, si quieres, define una acción distinta por tipo; si no, se usa la acción general." },
            { titulo: "Palabras clave", desc: "Términos confidenciales propios (proyectos, salarios…). Si aparecen en un correo saliente, se aplica la regla de Palabras clave." },
            { titulo: "Actividad reciente", desc: "Tabla con los últimos correos donde se detectaron datos sensibles: quién, qué dato y qué acción se aplicó (y si el usuario envió igual)." },
          ]}
        />
      </div>
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

      {/* Nivel de seguridad (presets) */}
      <div className="bg-white border border-ms-gray-30 rounded-lg p-5 mb-5">
        <div className="text-sm font-medium text-ms-gray-160 mb-1">Nivel de seguridad</div>
        <p className="text-xs text-ms-gray-110 mb-3">Elige un nivel y pulsa <b>Guardar cambios</b>. Aplica al webmail y a Outlook/móvil. Abajo puedes afinar cada detalle.</p>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
          {LEVELS.map((l) => (
            <button key={l.key} type="button" onClick={() => setCfg(applyLevel(cfg, l.key))}
              title={l.desc}
              className={`text-left border-2 rounded-lg p-3 ${l.color} ${level === l.key ? "bg-blue-50 ring-2 ring-ms-blue" : "bg-white hover:bg-ms-gray-10"}`}>
              <div className="text-sm font-semibold text-ms-gray-160">{l.label}{l.key === "block" ? " ★" : ""}</div>
              <div className="text-xs text-ms-gray-110 mt-1">{l.desc}</div>
            </button>
          ))}
        </div>
        {level === "custom" && <div className="text-xs text-amber-700 mt-2">Configuración personalizada (no coincide con ningún nivel predefinido).</div>}
        <div className="mt-3 text-sm">
          Estado actual: {cfg.enabled ? <span className="text-green-700 font-medium">ACTIVADA</span> : <span className="text-red-600 font-medium">DESACTIVADA</span>}
          {cfg.enabled && <span className="text-ms-gray-110"> · Outlook/móvil: {cfg.milter_enforce ? "rechaza en servidor" : "solo registra"} · Adjuntos: {cfg.scan_attachments ? "se revisan" : "no se revisan"}</span>}
        </div>
      </div>

      <div className="bg-white border border-ms-gray-30 rounded-lg p-5 space-y-5">
        {/* Interruptor maestro */}
        <label className="flex items-center gap-3 text-sm font-medium text-ms-gray-160">
          <input type="checkbox" className="w-4 h-4" checked={cfg.enabled}
            title="Interruptor general de la protección de datos. Activado: se revisan los correos salientes en busca de datos sensibles. Desactivado: los correos salen sin ninguna revisión ni registro. Recuerda pulsar Guardar cambios."
            onChange={(e) => setCfg({ ...cfg, enabled: e.target.checked })} />
          <span>Protección de datos <b>{cfg.enabled ? "ACTIVADA" : "desactivada"}</b></span>
        </label>

        {/* Acción general */}
        <div className={cfg.enabled ? "" : "opacity-50 pointer-events-none"}>
          <label className="block text-sm font-medium text-ms-gray-130 mb-1">
            ¿Qué hacer cuando se detecta un dato sensible? <span className="text-ms-gray-110">(acción general)</span>
          </label>
          <select className={inputCls} value={cfg.default_action}
            title="Acción por defecto al detectar un dato sensible en un correo saliente: Advertir muestra un aviso y el usuario decide si envía; Bloquear impide el envío; Solo registrar deja salir el correo pero lo anota en la actividad reciente. Los tipos de dato sin acción propia usan esta."
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
                  title={`Activa o desactiva la vigilancia de «${dt.label}» en los correos salientes. Desactivado, este tipo de dato saldrá por correo sin aviso ni registro.`}
                  onChange={(e) => setRule(dt.key, { enabled: e.target.checked })} />
                <span className="text-xl shrink-0">{dt.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-ms-gray-160">{dt.label}</div>
                  <div className="text-xs text-ms-gray-110">{dt.desc}</div>
                </div>
                <select className="px-2 py-1.5 border border-ms-gray-30 rounded text-xs shrink-0"
                  title={`Acción específica cuando se detecta «${dt.label}»: Advertir (el usuario decide), Bloquear (el correo no sale) o Solo registrar. Si eliges «Usar acción general», se aplica la acción configurada arriba.`}
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

        {/* Alcance: Outlook/móvil y adjuntos */}
        <div className={cfg.enabled ? "space-y-2" : "opacity-50 pointer-events-none space-y-2"}>
          <div className="text-sm font-medium text-ms-gray-130">Alcance</div>
          <label className="flex items-center gap-3 text-sm text-ms-gray-160">
            <input type="checkbox" className="w-4 h-4" checked={cfg.milter_enforce}
              title="Activado: los correos enviados desde Outlook, celular u otro programa que contengan datos con acción «Bloquear» hacia externos son rechazados por el servidor (el usuario recibe un rebote explicando el motivo). Desactivado: solo se registran."
              onChange={(e) => setCfg({ ...cfg, milter_enforce: e.target.checked })} />
            <span>Rechazar también en <b>Outlook / móvil</b> (bloqueo en el servidor de correo)</span>
          </label>
          <label className="flex items-center gap-3 text-sm text-ms-gray-160">
            <input type="checkbox" className="w-4 h-4" checked={cfg.scan_attachments}
              title="Activado: se revisa el contenido de los adjuntos (Word, Excel, PDF, ZIP, texto) buscando los mismos datos sensibles. Imágenes y ZIP con contraseña se marcan como «no inspeccionable»."
              onChange={(e) => setCfg({ ...cfg, scan_attachments: e.target.checked })} />
            <span>Revisar el contenido de los <b>adjuntos</b> (Word, Excel, PDF, ZIP)</span>
          </label>
          <p className="text-xs text-ms-gray-110">El bloqueo solo aplica a destinatarios <b>externos</b>; entre cuentas de Maquita únicamente se avisa.</p>
        </div>

        {/* Dominios de confianza */}
        <div className={cfg.enabled ? "" : "opacity-50 pointer-events-none"}>
          <label className="block text-sm font-medium text-ms-gray-130 mb-1">Dominios externos de confianza</label>
          <p className="text-xs text-ms-gray-110 mb-2">Se tratan como internos: no se bloquea el envío hacia ellos (ej. cooperantes, universidades aliadas).</p>
          <div className="flex gap-2 mb-2">
            <input className={inputCls} placeholder="ej. uide.edu.ec" value={newDom} onChange={(e) => setNewDom(e.target.value)}
              title="Escribe el dominio (sin @) y pulsa Enter o Agregar."
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addDom(); } }} />
            <button onClick={addDom} className="px-3 py-2 bg-ms-gray-20 text-ms-gray-160 rounded text-sm whitespace-nowrap">Agregar</button>
          </div>
          <div className="flex flex-wrap gap-2">
            {cfg.trusted_domains.length === 0 && <span className="text-xs text-ms-gray-110">Sin dominios de confianza.</span>}
            {cfg.trusted_domains.map((d) => (
              <span key={d} className="inline-flex items-center gap-1 bg-green-50 border border-green-200 text-ms-gray-160 text-xs rounded-full pl-3 pr-1 py-1">
                {d}<button onClick={() => removeDom(d)} className="w-4 h-4 rounded-full hover:bg-green-200 text-ms-gray-110">×</button>
              </span>
            ))}
          </div>
        </div>

        {/* Remitentes exentos */}
        <div className={cfg.enabled ? "" : "opacity-50 pointer-events-none"}>
          <label className="block text-sm font-medium text-ms-gray-130 mb-1">Remitentes autorizados a enviar datos sensibles</label>
          <p className="text-xs text-ms-gray-110 mb-2">
            Buzones de sistemas que <strong>deben</strong> enviar datos personales fuera, como los roles de pago de nómina, que llevan cédula y van a correos personales.
            Estos remitentes <strong>no se bloquean</strong>, pero <strong>se siguen registrando</strong>: aparecen igual en Incidentes, para poder revisar si alguno empieza a enviar algo fuera de lo normal.
          </p>
          <div className="flex gap-2 mb-2">
            <input className={inputCls} placeholder="ej. noreply@maquita.org" value={newExento} onChange={(e) => setNewExento(e.target.value)}
              title="Escribe la dirección completa del buzón y pulsa Enter o Agregar."
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addExento(); } }} />
            <button onClick={addExento} className="px-3 py-2 bg-ms-gray-20 text-ms-gray-160 rounded text-sm whitespace-nowrap">Agregar</button>
          </div>
          <div className="flex flex-wrap gap-2">
            {cfg.remitentes_exentos.length === 0 && <span className="text-xs text-ms-gray-110">Sin remitentes exentos: a todos se les aplica el bloqueo.</span>}
            {cfg.remitentes_exentos.map((d) => (
              <span key={d} className="inline-flex items-center gap-1 bg-amber-50 border border-amber-200 text-ms-gray-160 text-xs rounded-full pl-3 pr-1 py-1">
                {d}<button onClick={() => removeExento(d)} className="w-4 h-4 rounded-full hover:bg-amber-200 text-ms-gray-110">×</button>
              </span>
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
              title="Escribe una palabra o frase confidencial (ej. «salarios», nombre de un proyecto) y pulsa Enter o Agregar. Si aparece en un correo saliente, se aplicará la regla de Palabras clave."
              value={newKw} onChange={(e) => setNewKw(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addKw(); } }} />
            <button onClick={addKw} title="Agrega la palabra escrita a la lista de palabras clave vigiladas. El cambio se aplica al pulsar Guardar cambios." className="px-3 py-2 bg-ms-gray-20 text-ms-gray-160 rounded text-sm whitespace-nowrap">Agregar</button>
          </div>
          <div className="flex flex-wrap gap-2">
            {cfg.keywords.length === 0 && <span className="text-xs text-ms-gray-110">Sin palabras clave aún.</span>}
            {cfg.keywords.map((k) => (
              <span key={k} className="inline-flex items-center gap-1 bg-blue-50 border border-blue-200 text-ms-gray-160 text-xs rounded-full pl-3 pr-1 py-1">
                {k}
                <button onClick={() => removeKw(k)} title={`Quita «${k}» de la lista: esta palabra dejará de vigilarse en los correos salientes. El cambio se aplica al pulsar Guardar cambios.`} className="w-4 h-4 rounded-full hover:bg-blue-200 text-ms-gray-110">×</button>
              </span>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3 pt-1">
          <button onClick={save} disabled={saving}
            title="Guarda toda la configuración de DLP (interruptor, acciones, tipos de dato y palabras clave). Los cambios quedan activos de inmediato para todos los usuarios."
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
                    {v.external && <span className="ml-1 text-xs rounded px-2 py-0.5 bg-purple-100 text-purple-700">externo</span>}
                    {v.reason && <div className="text-xs text-ms-gray-110 mt-1">Motivo: {v.reason}</div>}
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
