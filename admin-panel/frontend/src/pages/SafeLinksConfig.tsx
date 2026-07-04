import { useState, useEffect } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface BlockItem { pattern: string; kind: string; note?: string; }
interface Cfg {
  enabled: boolean; rewrite_enabled: boolean; warn_suspicious: boolean;
  block_listed: boolean; milter_inbound_enabled: boolean; blocklist: BlockItem[];
}
interface Click { url: string; host: string; verdict: string; proceeded: boolean; ip: string; created_at: string | null; }

const KIND_LABEL: Record<string, string> = { domain: "Dominio", url: "Dirección", keyword: "Término" };
const VERDICT: Record<string, { label: string; cls: string }> = {
  blocked: { label: "Bloqueado", cls: "bg-red-100 text-red-700" },
  suspicious: { label: "Sospechoso", cls: "bg-amber-100 text-amber-700" },
  untrusted: { label: "Sin verificar", cls: "bg-ms-gray-20 text-ms-gray-130" },
};
const inputCls = "w-full px-3 py-2 border border-ms-gray-30 rounded text-sm";

export function SafeLinksConfig() {
  const [cfg, setCfg] = useState<Cfg>({ enabled: true, rewrite_enabled: true, warn_suspicious: true, block_listed: true, milter_inbound_enabled: false, blocklist: [] });
  const [clicks, setClicks] = useState<Click[]>([]);
  const [newPat, setNewPat] = useState("");
  const [newKind, setNewKind] = useState("domain");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<Cfg>("/safelinks-config").then(setCfg).catch(() => {}),
      api.get<{ clicks: Click[] }>("/safelinks-config/clicks").then((r) => setClicks(r.clicks || [])).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const addPat = () => {
    const p = newPat.trim().toLowerCase();
    if (p && !cfg.blocklist.some((b) => b.pattern === p && b.kind === newKind))
      setCfg({ ...cfg, blocklist: [...cfg.blocklist, { pattern: p, kind: newKind }] });
    setNewPat("");
  };
  const removePat = (b: BlockItem) =>
    setCfg({ ...cfg, blocklist: cfg.blocklist.filter((x) => !(x.pattern === b.pattern && x.kind === b.kind)) });

  const save = async () => {
    setSaving(true); setMsg(null);
    try { await api.put("/safelinks-config", cfg); setMsg({ ok: true, text: "Cambios guardados." }); }
    catch (e: any) { setMsg({ ok: false, text: e?.message || "Error al guardar" }); }
    finally { setSaving(false); }
  };

  if (loading) return <div className="p-6 text-sm text-ms-gray-110">Cargando…</div>;

  const Toggle = ({ k, label, desc }: { k: keyof Cfg; label: string; desc: string }) => (
    <label className="flex items-start gap-3 text-sm">
      <input type="checkbox" className="w-4 h-4 mt-0.5" checked={cfg[k] as boolean}
        title={`${label}. ${desc} Recuerda pulsar Guardar cambios para aplicar.`}
        onChange={(e) => setCfg({ ...cfg, [k]: e.target.checked })} />
      <span><b className="text-ms-gray-160">{label}</b><br /><span className="text-ms-gray-110 text-xs">{desc}</span></span>
    </label>
  );

  return (
    <div className="max-w-3xl">
      <div className="flex justify-end">
        <SectionHelp
          titulo="Protección de enlaces (Safe Links)"
          items={[
            { titulo: "Qué es", desc: "Los enlaces de los correos se reescriben para pasar por una pasarela propia que evalúa el destino en el momento del clic (imitación de marcas, dominios falsos, IPs, acortadores). Si hay riesgo, el usuario ve una página de aviso antes de continuar." },
            { titulo: "Interruptor y reescritura", desc: "El interruptor general enciende toda la protección; la reescritura de enlaces es necesaria para poder evaluarlos al hacer clic. Apagados, los enlaces se abren directo sin revisión." },
            { titulo: "Avisos y bloqueos", desc: "«Avisar de enlaces sospechosos» muestra advertencia ante señales de riesgo; «Bloquear lo de la lista negra» impide abrir lo que definas abajo." },
            { titulo: "Todos los clientes", desc: "La opción de milter reescribe los enlaces en el servidor al recibir el correo, protegiendo también Outlook y móvil (no solo el webmail). Es a prueba de fallos: nunca retiene ni corrompe correos." },
            { titulo: "Lista negra", desc: "Bloquea por dominio, dirección completa o término dentro de la URL. Se aplica al hacer clic si «Bloquear lo que esté en la lista negra» está activo." },
            { titulo: "Clics peligrosos", desc: "Tabla con los clics en enlaces sospechosos o bloqueados: destino, resultado y si el usuario decidió continuar de todos modos." },
          ]}
        />
      </div>
      <h1 className="text-xl font-semibold text-ms-gray-160 mb-1">Protección de enlaces (Safe Links)</h1>
      <p className="text-sm text-ms-gray-110 mb-4">
        Protege a los usuarios de enlaces peligrosos. Maquita <b>revisa cada enlace en el momento de hacer clic</b>:
        si es sospechoso o está en tu lista negra, muestra una advertencia en vez de abrirlo.
      </p>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-5 text-sm text-ms-gray-130">
        <b>¿Cómo funciona?</b> Los enlaces de los correos se “envuelven” en una pasarela de Maquita.
        Al hacer clic, se evalúa el destino (imitación de marcas, dominios falsos, IPs, acortadores…)
        y, si hay riesgo, el usuario ve una página de aviso clara antes de continuar.
      </div>

      <div className="bg-white border border-ms-gray-30 rounded-lg p-5 space-y-4">
        <Toggle k="enabled" label="Protección de enlaces ACTIVADA" desc="Interruptor general de Safe Links." />
        <div className={cfg.enabled ? "space-y-4 pl-1" : "space-y-4 pl-1 opacity-50 pointer-events-none"}>
          <Toggle k="rewrite_enabled" label="Reescribir enlaces de los correos" desc="Necesario para revisar el enlace al hacer clic." />
          <Toggle k="warn_suspicious" label="Avisar de enlaces sospechosos" desc="Imitación de marcas, IPs, acortadores, etc." />
          <Toggle k="block_listed" label="Bloquear lo que esté en la lista negra" desc="Dominios/direcciones/términos que definas abajo." />
        </div>

        <div className="mt-4 pt-4 border-t border-ms-gray-30">
          <Toggle k="milter_inbound_enabled"
            label="Proteger enlaces en TODOS los clientes (Outlook, móvil, etc.)"
            desc="Reescribe los enlaces de los correos entrantes a nivel del servidor, no solo en el webmail. Si lo apagas, los correos vuelven a entregarse sin tocar al instante. Diseño a prueba de fallos: nunca retiene ni corrompe un correo." />
        </div>

        <div className={cfg.enabled ? "" : "opacity-50 pointer-events-none"}>
          <label className="block text-sm font-medium text-ms-gray-130 mb-1">Lista negra</label>
          <p className="text-xs text-ms-gray-110 mb-2">Bloquea por dominio (ej. <code>malo.com</code>), dirección completa o un término que aparezca en la URL.</p>
          <div className="flex gap-2 mb-2">
            <select className="px-2 py-2 border border-ms-gray-30 rounded text-sm" value={newKind} onChange={(e) => setNewKind(e.target.value)}
              title="Tipo de entrada para la lista negra: Dominio bloquea todo un sitio (ej. malo.com), Dirección bloquea una URL exacta y Término bloquea cualquier enlace cuya URL contenga ese texto.">
              <option value="domain">Dominio</option><option value="url">Dirección</option><option value="keyword">Término</option>
            </select>
            <input className={inputCls} placeholder="Ej.: sitio-falso.com" value={newPat}
              title="Escribe el dominio, la dirección o el término a bloquear y pulsa Enter o Agregar. Los usuarios que hagan clic en un enlace que coincida verán una página de bloqueo en vez del sitio."
              onChange={(e) => setNewPat(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addPat(); } }} />
            <button onClick={addPat} title="Agrega el patrón escrito a la lista negra. El bloqueo se hace efectivo al pulsar Guardar cambios." className="px-3 py-2 bg-ms-gray-20 text-ms-gray-160 rounded text-sm whitespace-nowrap">Agregar</button>
          </div>
          <div className="flex flex-wrap gap-2">
            {cfg.blocklist.length === 0 && <span className="text-xs text-ms-gray-110">Lista negra vacía.</span>}
            {cfg.blocklist.map((b, i) => (
              <span key={i} className="inline-flex items-center gap-1 bg-red-50 border border-red-200 text-ms-gray-160 text-xs rounded-full pl-2 pr-1 py-1">
                <span className="text-red-700">{KIND_LABEL[b.kind]}:</span> {b.pattern}
                <button onClick={() => removePat(b)} title={`Quita «${b.pattern}» de la lista negra: los enlaces que coincidan dejarán de bloquearse. El cambio se aplica al pulsar Guardar cambios.`} className="w-4 h-4 rounded-full hover:bg-red-200 text-ms-gray-110">×</button>
              </span>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3 pt-1">
          <button onClick={save} disabled={saving} title="Guarda toda la configuración de Safe Links (interruptores y lista negra). Los cambios se aplican de inmediato a los clics de todos los usuarios." className="px-4 py-2 bg-ms-blue text-white rounded text-sm font-medium disabled:opacity-60">
            {saving ? "Guardando…" : "Guardar cambios"}
          </button>
          {msg && <span className={`text-sm ${msg.ok ? "text-green-700" : "text-red-600"}`}>{msg.text}</span>}
        </div>
      </div>

      <h2 className="text-base font-semibold text-ms-gray-160 mt-7 mb-1">Clics peligrosos recientes</h2>
      <p className="text-sm text-ms-gray-110 mb-3">Enlaces que se detectaron como sospechosos o bloqueados.</p>
      <div className="bg-white border border-ms-gray-30 rounded-lg overflow-hidden">
        {clicks.length === 0 ? (
          <div className="p-4 text-sm text-ms-gray-110">Sin clics peligrosos registrados. 🎉</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-ms-gray-10 text-ms-gray-110 text-xs">
              <tr>
                <th className="text-left px-3 py-2 font-medium">Cuándo</th>
                <th className="text-left px-3 py-2 font-medium">Destino</th>
                <th className="text-left px-3 py-2 font-medium">Resultado</th>
                <th className="text-left px-3 py-2 font-medium">¿Continuó?</th>
              </tr>
            </thead>
            <tbody>
              {clicks.map((c, i) => {
                const v = VERDICT[c.verdict] || { label: c.verdict, cls: "bg-ms-gray-20 text-ms-gray-130" };
                return (
                  <tr key={i} className="border-t border-ms-gray-20">
                    <td className="px-3 py-2 text-ms-gray-110 whitespace-nowrap">
                      {c.created_at ? new Date(c.created_at).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "short" }) : "—"}
                    </td>
                    <td className="px-3 py-2 text-ms-gray-130 max-w-[260px] truncate" title={c.url}>{c.host || c.url}</td>
                    <td className="px-3 py-2"><span className={`text-xs rounded px-2 py-0.5 ${v.cls}`}>{v.label}</span></td>
                    <td className="px-3 py-2 text-ms-gray-130">{c.proceeded ? "Sí ⚠️" : "No"}</td>
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
