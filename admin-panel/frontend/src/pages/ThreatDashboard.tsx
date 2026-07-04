import { useState, useEffect } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface Summary { window: string; spam_blocked: number; auth_fail: number; login_fail: number; bad_clicks: number; acct_alerts: number; }
interface FeedItem { type: string; when: string | null; source: string; detail: string; severity: string; }
interface Sender { sender: string; count: number; max_score: number | null; }
interface Blocked { id: number; pattern: string; note: string; created_by: string; created_at: string | null; }
interface Action { action: string; target: string; detail: string; actor: string; auto: boolean; created_at: string | null; }
interface Cfg { auto_disable_on_compromise: boolean; auto_block_dmarc_reject: boolean; }

const SEV: Record<string, string> = { high: "bg-red-100 text-red-700", medium: "bg-amber-100 text-amber-700", low: "bg-ms-gray-20 text-ms-gray-130" };
const TYPE_ICON: Record<string, string> = { correo: "✉️", enlace: "🔗", cuenta: "👤", acceso: "🔑" };

export function ThreatDashboard() {
  const [sum, setSum] = useState<Summary | null>(null);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [senders, setSenders] = useState<Sender[]>([]);
  const [blocked, setBlocked] = useState<Blocked[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [cfg, setCfg] = useState<Cfg>({ auto_disable_on_compromise: false, auto_block_dmarc_reject: false });
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [blockPat, setBlockPat] = useState("");
  const [disableUser, setDisableUser] = useState("");

  const loadAll = () => Promise.all([
    api.get<Summary>("/threats/summary").then(setSum).catch(() => {}),
    api.get<{ items: FeedItem[] }>("/threats/feed").then((r) => setFeed(r.items || [])).catch(() => {}),
    api.get<{ senders: Sender[] }>("/threats/top-senders").then((r) => setSenders(r.senders || [])).catch(() => {}),
    api.get<{ senders: Blocked[] }>("/threats/blocked-senders").then((r) => setBlocked(r.senders || [])).catch(() => {}),
    api.get<{ actions: Action[] }>("/threats/actions").then((r) => setActions(r.actions || [])).catch(() => {}),
    api.get<Cfg>("/threats/config").then(setCfg).catch(() => {}),
  ]);

  useEffect(() => { loadAll().finally(() => setLoading(false)); }, []);

  const saveCfg = async (next: Cfg) => {
    setCfg(next);
    try { await api.put("/threats/config", next); setMsg({ ok: true, text: "Respuesta automática actualizada." }); }
    catch (e: any) { setMsg({ ok: false, text: e?.message || "Error" }); }
  };

  const block = async () => {
    if (!blockPat.trim()) return;
    try { const r: any = await api.post("/threats/block-sender", { pattern: blockPat, note: "Bloqueado desde panel" });
      setMsg({ ok: true, text: r.rspamd_reloaded ? `Dominio ${blockPat} bloqueado en el filtro antispam.` : `Guardado, pero no se pudo recargar rspamd.` });
      setBlockPat(""); await loadAll();
    } catch (e: any) { setMsg({ ok: false, text: e?.message || "Error al bloquear" }); }
  };

  const disable = async () => {
    if (!disableUser.trim() || !window.confirm(`¿Deshabilitar el buzón ${disableUser}? No podrá iniciar sesión.`)) return;
    try { await api.post("/threats/disable-mailbox", { username: disableUser }); setMsg({ ok: true, text: `Buzón ${disableUser} deshabilitado.` }); setDisableUser(""); await loadAll(); }
    catch (e: any) { setMsg({ ok: false, text: e?.message || "Error" }); }
  };

  if (loading) return <div className="p-6 text-sm text-ms-gray-110">Cargando…</div>;

  const cards = sum ? [
    ["Spam detectado", sum.spam_blocked, "#ca5010"],
    ["Accesos fallidos", sum.login_fail, "#d13438"],
    ["Clics peligrosos", sum.bad_clicks, "#8764b8"],
    ["Alertas de cuenta", sum.acct_alerts, "#107c10"],
  ] : [];

  return (
    <div className="max-w-4xl">
      <div className="flex justify-end">
        <SectionHelp
          titulo="Panel de amenazas"
          items={[
            { titulo: "Tarjetas resumen", desc: "Contadores del período: spam detectado, accesos fallidos, clics en enlaces peligrosos y alertas de cuenta. Sirven para ver de un vistazo si algo anda mal." },
            { titulo: "Respuesta automática (AIR)", desc: "Acciones que el sistema toma solo: al activar la casilla, una cuenta que empiece a enviar correo masivo anómalo (señal de robo) se deshabilita al instante sin esperar al administrador." },
            { titulo: "Bloquear remitente", desc: "Añade un dominio o dirección a la lista negra del filtro antispam (rspamd); el bloqueo se aplica de inmediato a todo el correo entrante." },
            { titulo: "Deshabilitar buzón", desc: "Corta el acceso de una cuenta sospechosa: no podrá iniciar sesión ni enviar correo hasta que la reactives desde Buzones." },
            { titulo: "Amenazas recientes", desc: "Feed cronológico de eventos de seguridad (correos, enlaces, cuentas, accesos) con su severidad: alta en rojo, media en ámbar." },
            { titulo: "Listas inferiores", desc: "«Remitentes bloqueados» muestra los patrones activos en el filtro; «Acciones recientes» registra qué hizo el sistema o el administrador, marcando con «automático» lo que hizo AIR solo." },
          ]}
        />
      </div>
      <h1 className="text-xl font-semibold text-ms-gray-160 mb-1">Panel de amenazas</h1>
      <p className="text-sm text-ms-gray-110 mb-4">Vista unificada de la seguridad del correo y respuesta automática a incidentes.</p>
      {msg && <div className={`text-sm mb-4 px-3 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"}`}>{msg.text}</div>}

      {/* Tarjetas resumen */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {cards.map(([lbl, val, col]: any) => (
          <div key={lbl} className="bg-white border border-ms-gray-30 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold" style={{ color: col }}>{val}</div>
            <div className="text-xs text-ms-gray-110 mt-1">{lbl}</div>
          </div>
        ))}
      </div>

      {/* Respuesta automática */}
      <div className="bg-white border border-ms-gray-30 rounded-lg p-5 mb-6">
        <h2 className="text-base font-semibold text-ms-gray-160 mb-1">Respuesta automática (AIR)</h2>
        <p className="text-xs text-ms-gray-110 mb-3">Acciones que el sistema toma solo, sin esperar al admin.</p>
        <label className="flex items-start gap-3 text-sm">
          <input type="checkbox" className="w-4 h-4 mt-0.5" checked={cfg.auto_disable_on_compromise}
            title="Se guarda al instante: si lo activas, cualquier cuenta que muestre señales de robo (envío masivo anómalo) se deshabilitará automáticamente sin intervención del administrador; el usuario afectado perderá el acceso hasta que la reactives."
            onChange={(e) => saveCfg({ ...cfg, auto_disable_on_compromise: e.target.checked })} />
          <span><b className="text-ms-gray-160">Deshabilitar cuentas comprometidas automáticamente</b><br />
            <span className="text-ms-gray-110 text-xs">Si una cuenta empieza a enviar correo masivo anómalo (señal de robo), se deshabilita al instante.</span></span>
        </label>
      </div>

      {/* Acciones rápidas */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-white border border-ms-gray-30 rounded-lg p-4">
          <div className="text-sm font-medium text-ms-gray-160 mb-2">🚫 Bloquear remitente</div>
          <div className="flex gap-2">
            <input className="flex-1 px-3 py-2 border border-ms-gray-30 rounded text-sm" placeholder="dominio.com" value={blockPat} onChange={(e) => setBlockPat(e.target.value)}
              title="Escribe el dominio (ej.: dominio.com) o la dirección de correo del remitente malicioso que quieres bloquear en el filtro antispam." />
            <button onClick={block} title="Añade el remitente a la lista negra del filtro antispam (rspamd) y lo recarga de inmediato: todo el correo que envíe será rechazado o marcado como spam para toda la organización." className="px-3 py-2 bg-red-600 text-white rounded text-sm">Bloquear</button>
          </div>
          <p className="text-xs text-ms-gray-110 mt-1">Se aplica en el filtro antispam (rspamd) de inmediato.</p>
        </div>
        <div className="bg-white border border-ms-gray-30 rounded-lg p-4">
          <div className="text-sm font-medium text-ms-gray-160 mb-2">⛔ Deshabilitar buzón</div>
          <div className="flex gap-2">
            <input className="flex-1 px-3 py-2 border border-ms-gray-30 rounded text-sm" placeholder="usuario@maquita.org" value={disableUser} onChange={(e) => setDisableUser(e.target.value)}
              title="Escribe la dirección completa del buzón que quieres deshabilitar, por ejemplo cuando sospechas que la cuenta fue robada." />
            <button onClick={disable} title="Deshabilita el buzón indicado: el usuario no podrá iniciar sesión ni enviar correo hasta que lo reactives. Pide confirmación antes de aplicar." className="px-3 py-2 bg-ms-gray-160 text-white rounded text-sm">Deshabilitar</button>
          </div>
          <p className="text-xs text-ms-gray-110 mt-1">La cuenta no podrá iniciar sesión hasta reactivarla.</p>
        </div>
      </div>

      {/* Feed de amenazas */}
      <h2 className="text-base font-semibold text-ms-gray-160 mb-2">Amenazas recientes</h2>
      <div className="bg-white border border-ms-gray-30 rounded-lg overflow-hidden mb-6">
        {feed.length === 0 ? <div className="p-4 text-sm text-ms-gray-110">Sin amenazas registradas. 🎉</div> : (
          <table className="w-full text-sm">
            <tbody>
              {feed.map((f, i) => (
                <tr key={i} className="border-t border-ms-gray-10 first:border-0">
                  <td className="px-3 py-2 w-8 text-center">{TYPE_ICON[f.type] || "•"}</td>
                  <td className="px-3 py-2 text-ms-gray-160 max-w-[200px] truncate" title={f.source}>{f.source}</td>
                  <td className="px-3 py-2 text-ms-gray-130">{f.detail}</td>
                  <td className="px-3 py-2 text-right"><span className={`text-xs rounded px-2 py-0.5 ${SEV[f.severity] || SEV.low}`}>{f.severity}</span></td>
                  <td className="px-3 py-2 text-ms-gray-110 text-xs whitespace-nowrap">{f.when ? new Date(f.when).toLocaleDateString("es-EC", { day: "2-digit", month: "short" }) : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Top remitentes + bloqueados + acciones */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <h3 className="text-sm font-semibold text-ms-gray-160 mb-2">Remitentes bloqueados</h3>
          <div className="bg-white border border-ms-gray-30 rounded-lg overflow-hidden">
            {blocked.length === 0 ? <div className="p-3 text-xs text-ms-gray-110">Ninguno aún.</div> :
              blocked.map((b) => <div key={b.id} className="px-3 py-2 text-sm border-t border-ms-gray-10 first:border-0 text-ms-gray-160">{b.pattern}</div>)}
          </div>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-ms-gray-160 mb-2">Acciones recientes</h3>
          <div className="bg-white border border-ms-gray-30 rounded-lg overflow-hidden">
            {actions.length === 0 ? <div className="p-3 text-xs text-ms-gray-110">Sin acciones aún.</div> :
              actions.slice(0, 8).map((a, i) => (
                <div key={i} className="px-3 py-2 text-xs border-t border-ms-gray-10 first:border-0">
                  <span className="text-ms-gray-160">{a.action === "block_sender" ? "Bloqueó" : a.action === "disable_mailbox" ? "Deshabilitó" : a.action === "enable_mailbox" ? "Reactivó" : a.action}</span>{" "}
                  <b className="text-ms-gray-160">{a.target}</b>
                  {a.auto && <span className="ml-1 text-[#107c10]">· automático</span>}
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}
