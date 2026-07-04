import { useState, useEffect } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface Item { id: number; username: string; ip: string; country: string; city: string; reason: string; risk: string; distance_km: number | null; status: string; created_at: string | null; }
interface Cfg { enabled: boolean; auto_block: boolean; trusted_countries: string[]; occasional_countries: string[]; }

const RISK: Record<string, string> = { high: "bg-red-100 text-red-700", medium: "bg-amber-100 text-amber-700", low: "bg-ms-gray-20 text-ms-gray-130" };
const inputCls = "px-3 py-2 border border-ms-gray-30 rounded text-sm";

export function RiskyLogins() {
  const [items, setItems] = useState<Item[]>([]);
  const [openCount, setOpenCount] = useState(0);
  const [highCount, setHighCount] = useState(0);
  const [cfg, setCfg] = useState<Cfg>({ enabled: true, auto_block: false, trusted_countries: ["Ecuador"], occasional_countries: [] });
  const [newCountry, setNewCountry] = useState("");
  const [newOcc, setNewOcc] = useState("");
  const [filter, setFilter] = useState("open");
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = (f = filter) => api.get<{ open_count: number; high_count: number; items: Item[] }>(`/risky-logins?status=${f}`)
    .then((d) => { setItems(d.items || []); setOpenCount(d.open_count || 0); setHighCount(d.high_count || 0); }).catch(() => {});

  useEffect(() => {
    Promise.all([load(), api.get<Cfg>("/risky-logins/config").then(setCfg).catch(() => {})]).finally(() => setLoading(false));
  }, []);

  const saveCfg = async (next: Cfg) => {
    setCfg(next);
    try { await api.put("/risky-logins/config", next); setMsg({ ok: true, text: "Configuración guardada." }); }
    catch (e: any) { setMsg({ ok: false, text: e?.message || "Error" }); }
  };
  const addCountry = () => { const c = newCountry.trim(); if (c && !cfg.trusted_countries.includes(c)) saveCfg({ ...cfg, trusted_countries: [...cfg.trusted_countries, c] }); setNewCountry(""); };
  const removeCountry = (c: string) => saveCfg({ ...cfg, trusted_countries: cfg.trusted_countries.filter((x) => x !== c) });
  const addOcc = () => { const c = newOcc.trim(); if (c && !cfg.occasional_countries.includes(c)) saveCfg({ ...cfg, occasional_countries: [...cfg.occasional_countries, c] }); setNewOcc(""); };
  const removeOcc = (c: string) => saveCfg({ ...cfg, occasional_countries: cfg.occasional_countries.filter((x) => x !== c) });

  const act = async (it: Item, status: string) => {
    if (status === "blocked" && !window.confirm(`¿Bloquear la cuenta ${it.username}? No podrá iniciar sesión.`)) return;
    try { await api.post(`/risky-logins/${it.id}/status`, { status }); setMsg({ ok: true, text: status === "blocked" ? `Cuenta ${it.username} bloqueada.` : "Marcado como seguro." }); await load(); }
    catch (e: any) { setMsg({ ok: false, text: e?.message || "Error" }); }
  };

  if (loading) return <div className="p-6 text-sm text-ms-gray-110">Cargando…</div>;

  return (
    <div className="max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-160 mb-1">Inicios de sesión riesgosos</h1>
        <SectionHelp titulo="Inicios de sesión riesgosos" items={[
          { titulo: "Qué es esta sección", desc: "Detecta cuentas de correo posiblemente robadas: avisa cuando alguien inicia sesión desde un país donde la institución no opera o cuando hay un viaje imposible (dos logins muy lejanos en poco tiempo). Los logins desde la red interna no se marcan." },
          { titulo: "Niveles de riesgo", desc: "ALTO: login desde un país fuera de ambas listas (probable robo de cuenta). Medio: login desde un país de viaje ocasional (avisa, no bloquea)." },
          { titulo: "Países confiables", desc: "Lista de países donde SÍ opera la institución (ej.: Ecuador). Todo login fuera de esta lista se evalúa como sospechoso." },
          { titulo: "Países de viaje ocasional", desc: "Países que jefes o dirección visitan de vez en cuando. Un login desde ahí genera riesgo medio para verificar, sin bloquear." },
          { titulo: "Auto-bloqueo", desc: "Si se activa, una alerta de riesgo alto deshabilita la cuenta automáticamente al instante, sin esperar a un administrador." },
          { titulo: "Gestionar alertas", desc: "En cada alerta pendiente puede Bloquear la cuenta (el usuario ya no podrá entrar) o marcarla como segura si el login fue legítimo." },
        ]} />
      </div>
      <p className="text-sm text-ms-gray-110 mb-4">
        Detecta cuentas posiblemente comprometidas: inicios de sesión desde países donde la institución no opera,
        o "viajes imposibles" (login en Ecuador y minutos después en otro continente). Los logins de la red interna
        son confiables y no se marcan.
      </p>
      {msg && <div className={`text-sm mb-4 px-3 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"}`}>{msg.text}</div>}

      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-white border border-ms-gray-30 rounded-lg p-4 text-center"><div className="text-2xl font-bold text-[#d13438]">{highCount}</div><div className="text-xs text-ms-gray-110">Alertas de riesgo alto</div></div>
        <div className="bg-white border border-ms-gray-30 rounded-lg p-4 text-center"><div className="text-2xl font-bold text-ms-gray-160">{openCount}</div><div className="text-xs text-ms-gray-110">Pendientes de revisar</div></div>
        <div className="bg-white border border-ms-gray-30 rounded-lg p-4 text-center"><div className="text-sm font-medium text-ms-gray-160">{cfg.enabled ? "Activa" : "Inactiva"}</div><div className="text-xs text-ms-gray-110">Detección {cfg.auto_block ? "· auto-bloqueo ON" : ""}</div></div>
      </div>

      {/* Config */}
      <div className="bg-white border border-ms-gray-30 rounded-lg p-5 mb-6 space-y-3">
        <label className="flex items-center gap-2 text-sm text-ms-gray-160"><input type="checkbox" className="w-4 h-4" checked={cfg.enabled} onChange={(e) => saveCfg({ ...cfg, enabled: e.target.checked })} title="Activa o desactiva la detección de logins riesgosos. Se guarda de inmediato. Si se desactiva, no se generarán nuevas alertas." /> <b>Detección activada</b></label>
        <label className="flex items-start gap-2 text-sm text-ms-gray-160"><input type="checkbox" className="w-4 h-4 mt-0.5" checked={cfg.auto_block} onChange={(e) => saveCfg({ ...cfg, auto_block: e.target.checked })} title="PRECAUCIÓN: Si se marca, ante un login de riesgo alto la cuenta se deshabilita automáticamente sin intervención. Se guarda de inmediato." /> <span><b>Deshabilitar la cuenta automáticamente</b> ante un login de riesgo alto<br /><span className="text-xs text-ms-gray-110">Máxima protección: corta al instante una cuenta probablemente robada.</span></span></label>
        <div>
          <label className="block text-sm font-medium text-ms-gray-130 mb-1">Países donde SÍ opera la institución</label>
          <p className="text-xs text-ms-gray-110 mb-2">Cualquier login desde un país que <b>no</b> esté en esta lista se marca como <b>riesgo alto</b>. (Ej.: solo Ecuador.)</p>
          <div className="flex gap-2 mb-2">
            <input className={inputCls + " flex-1"} placeholder="Ej.: Ecuador" value={newCountry} onChange={(e) => setNewCountry(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addCountry(); } }} title="Nombre del país donde opera la institución (ej.: Ecuador). Enter o el botón Agregar lo añade a la lista de países confiables." />
            <button onClick={addCountry} title="Agrega el país escrito a la lista de países confiables. Los logins desde esos países no generan alerta. Se guarda de inmediato." className="px-3 py-2 bg-ms-gray-20 text-ms-gray-160 rounded text-sm">Agregar</button>
          </div>
          <div className="flex flex-wrap gap-2">
            {cfg.trusted_countries.length === 0 && <span className="text-xs text-red-600">⚠️ Sin países confiables: no se evaluará por país.</span>}
            {cfg.trusted_countries.map((c) => (
              <span key={c} className="inline-flex items-center gap-1 bg-green-50 border border-green-200 text-ms-gray-160 text-xs rounded-full pl-3 pr-1 py-1">{c}<button onClick={() => removeCountry(c)} title="Quita este país de la lista de confiables. Los próximos logins desde ese país se marcarán como riesgo alto. Se guarda de inmediato." className="w-4 h-4 rounded-full hover:bg-green-200 text-ms-gray-110">×</button></span>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-ms-gray-130 mb-1">Países de viaje ocasional (jefes/dirección)</label>
          <p className="text-xs text-ms-gray-110 mb-2">Viajes legítimos pero raros. Un login desde aquí da <b>riesgo medio</b> (avisa para verificar, <b>no</b> bloquea). Todo país fuera de ambas listas = <b>riesgo alto</b>.</p>
          <div className="flex gap-2 mb-2">
            <input className={inputCls + " flex-1"} placeholder="Ej.: España, China, Colombia…" value={newOcc} onChange={(e) => setNewOcc(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addOcc(); } }} title="Nombre de un país de viaje legítimo pero ocasional. Enter o el botón Agregar lo añade a la lista. Los logins desde ahí darán riesgo medio, no alto." />
            <button onClick={addOcc} title="Agrega el país escrito a la lista de viaje ocasional. Un login desde esos países genera riesgo medio (aviso, sin bloqueo). Se guarda de inmediato." className="px-3 py-2 bg-ms-gray-20 text-ms-gray-160 rounded text-sm">Agregar</button>
          </div>
          <div className="flex flex-wrap gap-2">
            {cfg.occasional_countries.length === 0 && <span className="text-xs text-ms-gray-110">Sin países de viaje ocasional.</span>}
            {cfg.occasional_countries.map((c) => (
              <span key={c} className="inline-flex items-center gap-1 bg-amber-50 border border-amber-200 text-ms-gray-160 text-xs rounded-full pl-3 pr-1 py-1">{c}<button onClick={() => removeOcc(c)} title="Quita este país de la lista de viaje ocasional. Los próximos logins desde ese país se marcarán como riesgo alto. Se guarda de inmediato." className="w-4 h-4 rounded-full hover:bg-amber-200 text-ms-gray-110">×</button></span>
            ))}
          </div>
        </div>
      </div>

      {/* Tabla */}
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-base font-semibold text-ms-gray-160">Alertas</h2>
        <select className="px-2 py-1 border border-ms-gray-30 rounded text-xs" value={filter} onChange={(e) => { setFilter(e.target.value); load(e.target.value); }} title="Filtra las alertas mostradas: Pendientes (aún sin revisar) o Todas (incluye las ya bloqueadas o marcadas como seguras).">
          <option value="open">Pendientes</option><option value="all">Todas</option>
        </select>
      </div>
      <div className="bg-white border border-ms-gray-30 rounded-lg overflow-hidden">
        {items.length === 0 ? <div className="p-4 text-sm text-ms-gray-110">Sin logins riesgosos. 🎉</div> :
          items.map((it) => (
            <div key={it.id} className="border-t border-ms-gray-10 first:border-0 p-3 flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-xs rounded px-2 py-0.5 ${RISK[it.risk] || RISK.low}`}>{it.risk === "high" ? "ALTO" : it.risk}</span>
                  <span className="text-sm font-medium text-ms-gray-160">{it.username}</span>
                  <span className="text-xs text-ms-gray-110">desde <b>{it.city ? it.city + ", " : ""}{it.country}</b> ({it.ip})</span>
                  <span className="text-xs text-ms-gray-110">· {it.created_at ? new Date(it.created_at).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "short" }) : ""}</span>
                </div>
                <div className="text-xs text-ms-gray-130 mt-1">{it.reason}</div>
              </div>
              {it.status === "open" ? (
                <div className="flex flex-col gap-1 shrink-0">
                  <button onClick={() => act(it, "blocked")} title="PRECAUCIÓN: Bloquea la cuenta de este usuario. No podrá iniciar sesión hasta que un administrador la reactive. Pide confirmación." className="px-2 py-1 bg-red-600 text-white rounded text-xs">Bloquear cuenta</button>
                  <button onClick={() => act(it, "safe")} title="Marca la alerta como login legítimo verificado. La alerta se cierra y no se toma ninguna acción contra la cuenta." className="px-2 py-1 bg-ms-gray-20 text-ms-gray-160 rounded text-xs">Es seguro (soy yo)</button>
                </div>
              ) : <span className="text-xs text-ms-gray-110 shrink-0">{it.status === "blocked" ? "bloqueado" : "seguro"}</span>}
            </div>
          ))}
      </div>
    </div>
  );
}
