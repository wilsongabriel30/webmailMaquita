import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";

// ─── Traducciones de acciones ───
const ACTION_LABELS: Record<string, string> = {
  login_success: "Inicio de sesión", login_failed: "Intento fallido", logout: "Cierre de sesión",
  password_change: "Cambio de contraseña", email_send: "Enviar correo", email_delete: "Eliminar correo",
  email_read: "Leer correo", sieve_create: "Crear filtro", forward_create: "Crear reenvío",
  impersonate: "Impersonar", impersonation_start: "Inicio impersonación", impersonation_end: "Fin impersonación",
  totp_disable: "Desactivar TOTP", totp_enable: "Activar TOTP", ediscovery_search: "Búsqueda eDiscovery",
  case_created: "Caso creado", case_updated: "Caso actualizado", case_closed: "Caso cerrado",
  mailbox_create: "Crear buzón", mailbox_update: "Actualizar buzón", mailbox_delete: "Eliminar buzón",
  mailbox_impersonate: "Impersonar buzón", alias_create: "Crear alias", alias_delete: "Eliminar alias",
  group_create: "Crear grupo", group_member_add: "Agregar miembro", group_member_remove: "Quitar miembro",
  signature_create: "Crear firma", signature_update: "Actualizar firma", domain_create: "Crear dominio",
};

// ─── Types ───
interface ActivityEntry {
  id: number; username: string; action: string; category: string;
  risk_level: string; ip_address: string | null; target: string | null; created_at: string;
}
interface MailTraceEntry {
  id: number; queue_id: string; message_id: string; direction: string;
  sender: string; recipient: string; source_ip: string | null;
  spf_result: string | null; dkim_result: string | null; dmarc_result: string | null;
  rspamd_score: number | null; status: string; size_bytes: number | null; created_at: string;
}
interface ComplianceCase {
  id: number; title: string; description: string; reason: string;
  case_type: string; status: string; priority: string; created_by: string;
  created_at: string; searches_count?: number; results_count?: number;
  active_holds?: number; exports_count?: number;
}
interface FraudAlert {
  id: number; alert_type: string; severity: string; username: string;
  description: string; source_ip: string | null; is_acknowledged: boolean; created_at: string;
}
interface LegalHold {
  id: number; case_id: number; mailbox: string; reason: string;
  enabled_by: string; enabled_at: string; is_active: boolean;
}
interface SearchResult {
  id: number; mailbox: string; folder: string; uid: number; message_id: string;
  subject: string; sender: string; sent_at: string; size_bytes: number; hash_sha256: string;
}

// ─── Helpers ───
const TABS = [
  { id: "dashboard", label: "Dashboard" },
  { id: "activity", label: "Actividad" },
  { id: "trace", label: "Mail Trace" },
  { id: "cases", label: "Casos" },
  { id: "ediscovery", label: "eDiscovery" },
  { id: "holds", label: "Legal Hold" },
  { id: "alerts", label: "Alertas" },
];

const riskBg: Record<string, string> = { low: "bg-gray-100 text-gray-600", medium: "bg-yellow-100 text-yellow-700", high: "bg-orange-100 text-orange-700", critical: "bg-red-100 text-red-700" };
const statusBg: Record<string, string> = { open: "bg-blue-100 text-blue-700", approved: "bg-green-100 text-green-700", in_progress: "bg-yellow-100 text-yellow-700", closed: "bg-gray-100 text-gray-500" };

function Badge({ text, color }: { text: string; color?: string }) {
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold ${color || "bg-gray-100 text-gray-600"}`}>{text}</span>;
}
function fmtDate(d: string | null) {
  if (!d) return "—";
  try { return new Date(d).toLocaleString("es-EC", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }); } catch { return d.substring(0, 19); }
}
function fmtSize(b: number | null) {
  if (!b) return "—";
  if (b < 1024) return b + " B";
  if (b < 1048576) return (b / 1024).toFixed(1) + " KB";
  return (b / 1048576).toFixed(1) + " MB";
}
function Loader() { return <div className="flex justify-center py-12"><div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full" /></div>; }

function Pager({ page, total, perPage, onPage }: { page: number; total: number; perPage: number; onPage: (p: number) => void }) {
  const tp = Math.ceil(total / perPage);
  if (tp <= 1) return null;
  return (
    <div className="flex items-center justify-between mt-3 text-xs text-gray-500">
      <span>Pag. {page}/{tp}</span>
      <div className="flex gap-1">
        <button onClick={() => onPage(page - 1)} disabled={page <= 1} className="px-2 py-1 border rounded disabled:opacity-30">Ant</button>
        <button onClick={() => onPage(page + 1)} disabled={page >= tp} className="px-2 py-1 border rounded disabled:opacity-30">Sig</button>
      </div>
    </div>
  );
}

// ─── Main ───
export function Compliance() {
  const [tab, setTab] = useState("dashboard");
  return (
    <div className="p-6">
      <div className="mb-5">
        <h1 className="text-xl font-bold text-gray-800">Compliance & eDiscovery</h1>
        <p className="text-xs text-gray-500 mt-1">Auditoria, trazabilidad y busqueda forense</p>
      </div>
      <div className="flex gap-1 mb-5 border-b border-gray-200 overflow-x-auto">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
              tab === t.id ? "border-ms-blue text-ms-blue" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>{t.label}</button>
        ))}
      </div>
      {tab === "dashboard" && <DashboardTab />}
      {tab === "activity" && <ActivityTab />}
      {tab === "trace" && <TraceTab />}
      {tab === "cases" && <CasesTab />}
      {tab === "ediscovery" && <EDiscoveryTab />}
      {tab === "holds" && <HoldsTab />}
      {tab === "alerts" && <AlertsTab />}
    </div>
  );
}

// ═══ DASHBOARD ═══
function DashboardTab() {
  const [d, setD] = useState<any>(null);
  useEffect(() => {
    Promise.all([
      api.get<any>("/compliance/activity/stats?days=30").catch(() => ({})),
      api.get<any>("/compliance/mail-trace/stats?hours=24").catch(() => ({})),
      api.get<any>("/compliance/alerts/stats?days=30").catch(() => ({})),
    ]).then(([a, t, al]) => setD({ act: a, trace: t, alerts: al }));
  }, []);
  if (!d) return <Loader />;
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card label="Actividad (30d)" value={d.act?.total ?? 0} />
        <Card label="Mail Trace (24h)" value={d.trace?.total ?? 0} />
        <Card label="Alertas (30d)" value={d.alerts?.total ?? 0} />
        <Card label="Sin revisar" value={d.alerts?.unacknowledged ?? 0} accent />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="bg-white border rounded-lg p-4">
          <h3 className="font-semibold text-gray-700 text-sm mb-3">Por riesgo (30d)</h3>
          {d.act?.by_risk && Object.entries(d.act.by_risk).map(([k, v]) => (
            <div key={k} className="flex justify-between py-1.5 border-b border-gray-50 text-sm">
              <Badge text={k} color={riskBg[k]} /><span className="font-mono font-bold">{v as number}</span>
            </div>
          ))}
          {!d.act?.by_risk && <p className="text-xs text-gray-400">Sin datos aun</p>}
        </div>
        <div className="bg-white border rounded-lg p-4">
          <h3 className="font-semibold text-gray-700 text-sm mb-3">Top acciones (30d)</h3>
          {d.act?.top_actions?.slice(0, 8).map((a: any) => (
            <div key={a.action} className="flex justify-between py-1.5 border-b border-gray-50 text-sm">
              <span className="text-xs text-gray-600" title={a.action}>{ACTION_LABELS[a.action] || a.action}</span>
              <span className="font-mono font-bold">{a.total}</span>
            </div>
          ))}
          {!d.act?.top_actions?.length && <p className="text-xs text-gray-400">Sin datos aun</p>}
        </div>
      </div>
      {d.trace?.by_status && Object.keys(d.trace.by_status).length > 0 && (
        <div className="bg-white border rounded-lg p-4">
          <h3 className="font-semibold text-gray-700 text-sm mb-3">Correos por estado (24h)</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(d.trace.by_status).map(([k, v]) => (
              <div key={k} className="text-center p-3 bg-gray-50 rounded"><div className="text-xl font-bold">{v as number}</div><div className="text-xs text-gray-500">{k}</div></div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
function Card({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <div className={`border rounded-lg p-4 ${accent && value > 0 ? "bg-red-50 border-red-200" : "bg-white"}`}>
      <div className={`text-2xl font-bold ${accent && value > 0 ? "text-red-600" : "text-gray-800"}`}>{value.toLocaleString()}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  );
}

// ═══ ACTIVITY ═══
function ActivityTab() {
  const [rows, setRows] = useState<ActivityEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [pg, setPg] = useState(1);
  const [loading, setLoading] = useState(false);
  const [f, setF] = useState({ username: "", action: "", category: "", risk_level: "" });

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    const q = new URLSearchParams({ page: String(p), per_page: "50" });
    Object.entries(f).forEach(([k, v]) => { if (v) q.set(k, String(v)); });
    try { const d = await api.get<any>(`/compliance/activity?${q}`); setRows(d.entries || []); setTotal(d.total); setPg(p); } catch {}
    setLoading(false);
  }, [f]);
  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-4">
        <input placeholder="Usuario" value={f.username} onChange={e => setF(x => ({ ...x, username: e.target.value }))} className="px-2 py-1.5 border rounded text-sm w-40" />
        <select value={f.action} onChange={e => setF(x => ({ ...x, action: e.target.value }))} className="px-2 py-1.5 border rounded text-sm">
          <option value="">Toda accion</option>
          {["login_success","login_failed","password_change","email_send","email_delete","sieve_create","forward_create","impersonate","totp_disable"].map(a =>
            <option key={a} value={a}>{a}</option>)}
        </select>
        <select value={f.risk_level} onChange={e => setF(x => ({ ...x, risk_level: e.target.value }))} className="px-2 py-1.5 border rounded text-sm">
          <option value="">Todo riesgo</option>
          <option value="low">Bajo</option><option value="medium">Medio</option><option value="high">Alto</option><option value="critical">Critico</option>
        </select>
        <button onClick={() => load(1)} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm">Buscar</button>
      </div>
      <div className="text-xs text-gray-500 mb-2">{total} registros</div>
      {loading ? <Loader /> : (
        <div className="overflow-x-auto border rounded-lg">
          <table className="w-full text-sm">
            <thead><tr className="bg-gray-50 border-b">
              <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">Fecha</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">Usuario</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">Accion</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">Riesgo</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">IP</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">Target</th>
            </tr></thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id} className="border-b border-gray-50 hover:bg-blue-50/30">
                  <td className="px-3 py-2 text-xs text-gray-500 whitespace-nowrap">{fmtDate(r.created_at)}</td>
                  <td className="px-3 py-2 font-medium">{r.username}</td>
                  <td className="px-3 py-2 font-mono text-xs">{r.action}</td>
                  <td className="px-3 py-2"><Badge text={r.risk_level} color={riskBg[r.risk_level]} /></td>
                  <td className="px-3 py-2 font-mono text-xs text-gray-400">{r.ip_address || "—"}</td>
                  <td className="px-3 py-2 text-xs text-gray-500 max-w-[180px] truncate">{r.target || "—"}</td>
                </tr>
              ))}
              {!rows.length && <tr><td colSpan={6} className="text-center py-8 text-gray-400">Sin registros</td></tr>}
            </tbody>
          </table>
        </div>
      )}
      <Pager page={pg} total={total} perPage={50} onPage={load} />
    </div>
  );
}

// ═══ MAIL TRACE ═══
function TraceTab() {
  const [rows, setRows] = useState<MailTraceEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [pg, setPg] = useState(1);
  const [loading, setLoading] = useState(false);
  const [f, setF] = useState({ sender: "", recipient: "", status: "", direction: "" });

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    const q = new URLSearchParams({ page: String(p), per_page: "50" });
    Object.entries(f).forEach(([k, v]) => { if (v) q.set(k, String(v)); });
    try { const d = await api.get<any>(`/compliance/mail-trace?${q}`); setRows(d.entries || []); setTotal(d.total); setPg(p); } catch {}
    setLoading(false);
  }, [f]);
  useEffect(() => { load(); }, [load]);

  const dirLabel: Record<string, string> = { inbound: "Entrada", outbound: "Salida", internal: "Interno" };
  const dirColor: Record<string, string> = { inbound: "bg-green-100 text-green-700", outbound: "bg-blue-100 text-blue-700", internal: "bg-gray-100 text-gray-600" };

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-4">
        <input placeholder="Remitente" value={f.sender} onChange={e => setF(x => ({ ...x, sender: e.target.value }))} className="px-2 py-1.5 border rounded text-sm w-44" />
        <input placeholder="Destinatario" value={f.recipient} onChange={e => setF(x => ({ ...x, recipient: e.target.value }))} className="px-2 py-1.5 border rounded text-sm w-44" />
        <select value={f.status} onChange={e => setF(x => ({ ...x, status: e.target.value }))} className="px-2 py-1.5 border rounded text-sm">
          <option value="">Todo estado</option><option value="sent">Enviado</option><option value="deferred">Diferido</option><option value="bounced">Rebotado</option>
        </select>
        <select value={f.direction} onChange={e => setF(x => ({ ...x, direction: e.target.value }))} className="px-2 py-1.5 border rounded text-sm">
          <option value="">Toda dir</option><option value="inbound">Entrada</option><option value="outbound">Salida</option><option value="internal">Interno</option>
        </select>
        <button onClick={() => load(1)} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm">Buscar</button>
      </div>
      <div className="text-xs text-gray-500 mb-2">{total} registros</div>
      {loading ? <Loader /> : (
        <div className="overflow-x-auto border rounded-lg">
          <table className="w-full text-sm">
            <thead><tr className="bg-gray-50 border-b">
              <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">Fecha</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">Dir</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">Remitente</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">Destinatario</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">Estado</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">Score</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">Auth</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">IP</th>
              <th className="text-right px-3 py-2 text-xs font-semibold text-gray-500">Tam</th>
            </tr></thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id} className="border-b border-gray-50 hover:bg-blue-50/30">
                  <td className="px-3 py-2 text-xs text-gray-500 whitespace-nowrap">{fmtDate(r.created_at)}</td>
                  <td className="px-3 py-2"><Badge text={dirLabel[r.direction] || r.direction} color={dirColor[r.direction]} /></td>
                  <td className="px-3 py-2 max-w-[160px] truncate">{r.sender}</td>
                  <td className="px-3 py-2 max-w-[160px] truncate">{r.recipient}</td>
                  <td className="px-3 py-2"><Badge text={r.status} color={r.status === "sent" ? "bg-green-100 text-green-700" : r.status === "bounced" ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-600"} /></td>
                  <td className="px-3 py-2 font-mono text-xs">{r.rspamd_score != null ? r.rspamd_score.toFixed(1) : "—"}</td>
                  <td className="px-3 py-2 text-xs font-mono">{[r.spf_result, r.dkim_result, r.dmarc_result].filter(Boolean).join("/") || "—"}</td>
                  <td className="px-3 py-2 font-mono text-xs text-gray-400">{r.source_ip || "—"}</td>
                  <td className="px-3 py-2 text-right text-xs text-gray-400">{fmtSize(r.size_bytes)}</td>
                </tr>
              ))}
              {!rows.length && <tr><td colSpan={9} className="text-center py-8 text-gray-400">Sin registros</td></tr>}
            </tbody>
          </table>
        </div>
      )}
      <Pager page={pg} total={total} perPage={50} onPage={load} />
    </div>
  );
}

// ═══ CASES ═══
function CasesTab() {
  const [cases, setCases] = useState<ComplianceCase[]>([]);
  const [loading, setLoading] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ title: "", reason: "", description: "", case_type: "investigation" });
  const [detail, setDetail] = useState<ComplianceCase | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { const d = await api.get<any>("/compliance/cases?per_page=50"); setCases(d.cases || []); } catch {}
    setLoading(false);
  }, []);
  useEffect(() => { load(); }, [load]);

  async function create() {
    if (!form.title || !form.reason) return;
    await api.post("/compliance/cases", form);
    setShowNew(false); setForm({ title: "", reason: "", description: "", case_type: "investigation" }); load();
  }
  async function viewDetail(id: number) {
    try { setDetail(await api.get<ComplianceCase>(`/compliance/cases/${id}`)); } catch {}
  }
  async function updateStatus(id: number, status: string) {
    await api.put(`/compliance/cases/${id}`, { status }); setDetail(null); load();
  }

  return (
    <div>
      <div className="flex justify-between mb-4">
        <span className="text-xs text-gray-500">{cases.length} casos</span>
        <button onClick={() => setShowNew(!showNew)} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm">+ Nuevo caso</button>
      </div>
      {showNew && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
            <input placeholder="Titulo *" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} className="px-2 py-1.5 border rounded text-sm" />
            <select value={form.case_type} onChange={e => setForm(f => ({ ...f, case_type: e.target.value }))} className="px-2 py-1.5 border rounded text-sm">
              <option value="investigation">Investigacion</option><option value="fraud">Fraude</option><option value="compliance">Compliance</option><option value="legal">Legal</option><option value="security">Seguridad</option>
            </select>
          </div>
          <textarea placeholder="Motivo *" value={form.reason} onChange={e => setForm(f => ({ ...f, reason: e.target.value }))} className="w-full px-2 py-1.5 border rounded text-sm mb-3" rows={2} />
          <div className="flex gap-2">
            <button onClick={create} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm">Crear</button>
            <button onClick={() => setShowNew(false)} className="px-3 py-1.5 bg-white border text-gray-600 rounded text-sm">Cancelar</button>
          </div>
        </div>
      )}
      {detail && (
        <div className="bg-white border-2 border-blue-300 rounded-lg p-4 mb-4 shadow">
          <div className="flex justify-between mb-3">
            <h3 className="font-bold text-gray-800">#{detail.id} — {detail.title}</h3>
            <button onClick={() => setDetail(null)} className="text-gray-400 hover:text-gray-600">&times;</button>
          </div>
          <p className="text-sm text-gray-600 mb-3">{detail.reason}</p>
          <div className="flex gap-4 text-sm mb-3">
            <span>Estado: <Badge text={detail.status} color={statusBg[detail.status]} /></span>
            <span>Tipo: {detail.case_type}</span>
            <span>Creado: {fmtDate(detail.created_at)}</span>
          </div>
          {detail.searches_count != null && (
            <div className="grid grid-cols-4 gap-2 mb-3 text-center text-sm">
              <div className="bg-gray-50 rounded p-2"><div className="font-bold">{detail.searches_count}</div><div className="text-xs text-gray-500">Busquedas</div></div>
              <div className="bg-gray-50 rounded p-2"><div className="font-bold">{detail.results_count}</div><div className="text-xs text-gray-500">Resultados</div></div>
              <div className="bg-gray-50 rounded p-2"><div className="font-bold">{detail.active_holds}</div><div className="text-xs text-gray-500">Holds</div></div>
              <div className="bg-gray-50 rounded p-2"><div className="font-bold">{detail.exports_count}</div><div className="text-xs text-gray-500">Exports</div></div>
            </div>
          )}
          <div className="flex gap-2">
            {detail.status === "open" && <button onClick={() => updateStatus(detail.id, "approved")} className="px-3 py-1 bg-green-600 text-white rounded text-xs">Aprobar</button>}
            {detail.status === "approved" && <button onClick={() => updateStatus(detail.id, "in_progress")} className="px-3 py-1 bg-yellow-600 text-white rounded text-xs">Iniciar</button>}
            {["open","approved","in_progress"].includes(detail.status) && <button onClick={() => updateStatus(detail.id, "closed")} className="px-3 py-1 bg-gray-600 text-white rounded text-xs">Cerrar</button>}
          </div>
        </div>
      )}
      {loading ? <Loader /> : (
        <div className="space-y-2">
          {cases.map(c => (
            <div key={c.id} onClick={() => viewDetail(c.id)} className="bg-white border rounded-lg p-3 hover:border-blue-300 cursor-pointer flex justify-between items-center">
              <div>
                <span className="text-gray-300 font-bold mr-2">#{c.id}</span>
                <span className="font-semibold text-gray-800">{c.title}</span>
                <div className="text-xs text-gray-500 mt-0.5">{c.reason.substring(0, 80)}</div>
              </div>
              <div className="flex items-center gap-2">
                <Badge text={c.case_type} /><Badge text={c.status} color={statusBg[c.status]} />
                <span className="text-xs text-gray-400">{fmtDate(c.created_at)}</span>
              </div>
            </div>
          ))}
          {!cases.length && <div className="text-center py-8 text-gray-400 text-sm">Sin casos</div>}
        </div>
      )}
    </div>
  );
}

// ═══ eDISCOVERY ═══
function EDiscoveryTab() {
  const [cases, setCases] = useState<ComplianceCase[]>([]);
  const [searches, setSearches] = useState<any[]>([]);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [selSearch, setSelSearch] = useState<number | null>(null);
  const [rTotal, setRTotal] = useState(0);
  const [sLoading, setSLoading] = useState(false);
  const [form, setForm] = useState({ case_id: "", mailboxes_scope: "", keywords: "", date_from: "", date_to: "", senders_filter: "", recipients_filter: "" });

  useEffect(() => {
    api.get<any>("/compliance/cases?per_page=100").then(d => setCases(d.cases || [])).catch(() => {});
    api.get<any>("/compliance/ediscovery/searches?per_page=50").then(d => setSearches(d.searches || [])).catch(() => {});
  }, []);

  async function runSearch() {
    if (!form.case_id) return;
    setSLoading(true);
    try {
      const body = {
        case_id: Number(form.case_id),
        mailboxes_scope: form.mailboxes_scope ? form.mailboxes_scope.split(",").map(s => s.trim()) : [],
        keywords: form.keywords ? form.keywords.split(",").map(s => s.trim()) : [],
        senders_filter: form.senders_filter ? form.senders_filter.split(",").map(s => s.trim()) : [],
        recipients_filter: form.recipients_filter ? form.recipients_filter.split(",").map(s => s.trim()) : [],
        date_from: form.date_from, date_to: form.date_to,
      };
      const res = await api.post<any>("/compliance/ediscovery/search", body);
      const d = await api.get<any>("/compliance/ediscovery/searches?per_page=50");
      setSearches(d.searches || []);
      if (res.search_id) viewResults(res.search_id);
    } catch (e: any) { alert(e.message); }
    setSLoading(false);
  }

  async function viewResults(sid: number) {
    setSelSearch(sid);
    try { const d = await api.get<any>(`/compliance/ediscovery/results/${sid}?per_page=100`); setResults(d.results || []); setRTotal(d.total); } catch {}
  }

  async function exportSearch(sid: number, cid: number) {
    try {
      const r = await api.post<any>("/compliance/ediscovery/export", { case_id: cid, search_id: sid, reason: "Export desde admin panel" });
      alert(`Exportados: ${r.exported}\nHash: ${r.manifest_hash}\nRuta: ${r.export_path}`);
    } catch (e: any) { alert(e.message); }
  }

  return (
    <div>
      <div className="bg-gray-50 border rounded-lg p-4 mb-5">
        <h3 className="font-semibold text-gray-700 text-sm mb-3">Nueva busqueda forense</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
          <select value={form.case_id} onChange={e => setForm(f => ({ ...f, case_id: e.target.value }))} className="px-2 py-1.5 border rounded text-sm">
            <option value="">Caso *</option>
            {cases.filter(c => c.status !== "closed").map(c => <option key={c.id} value={c.id}>#{c.id} — {c.title}</option>)}
          </select>
          <input placeholder="Buzones (coma)" value={form.mailboxes_scope} onChange={e => setForm(f => ({ ...f, mailboxes_scope: e.target.value }))} className="px-2 py-1.5 border rounded text-sm" />
          <input placeholder="Palabras clave (coma)" value={form.keywords} onChange={e => setForm(f => ({ ...f, keywords: e.target.value }))} className="px-2 py-1.5 border rounded text-sm" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
          <input placeholder="Remitentes" value={form.senders_filter} onChange={e => setForm(f => ({ ...f, senders_filter: e.target.value }))} className="px-2 py-1.5 border rounded text-sm" />
          <input placeholder="Destinatarios" value={form.recipients_filter} onChange={e => setForm(f => ({ ...f, recipients_filter: e.target.value }))} className="px-2 py-1.5 border rounded text-sm" />
          <input type="date" value={form.date_from} onChange={e => setForm(f => ({ ...f, date_from: e.target.value }))} className="px-2 py-1.5 border rounded text-sm" />
          <input type="date" value={form.date_to} onChange={e => setForm(f => ({ ...f, date_to: e.target.value }))} className="px-2 py-1.5 border rounded text-sm" />
        </div>
        <button onClick={runSearch} disabled={sLoading || !form.case_id} className="px-4 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">
          {sLoading ? "Buscando..." : "Ejecutar busqueda"}
        </button>
      </div>

      <h3 className="font-semibold text-gray-700 text-sm mb-2">Busquedas</h3>
      <div className="space-y-2 mb-5">
        {searches.map(s => (
          <div key={s.id} onClick={() => viewResults(s.id)} className={`flex justify-between items-center p-3 rounded border cursor-pointer ${selSearch === s.id ? "border-blue-400 bg-blue-50" : "hover:border-gray-300"}`}>
            <div className="flex items-center gap-2 text-sm">
              <span className="font-mono text-gray-400 text-xs">#{s.id}</span>
              <span>Caso #{s.case_id}</span>
              {s.keywords && <span className="text-xs text-gray-500">{Array.isArray(s.keywords) ? s.keywords.join(", ") : ""}</span>}
            </div>
            <div className="flex items-center gap-2">
              <Badge text={s.status || "?"} color={s.status === "completed" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"} />
              <span className="text-sm font-bold">{s.result_count ?? 0}</span>
              <button onClick={e => { e.stopPropagation(); exportSearch(s.id, s.case_id); }} className="p-1 hover:bg-blue-100 rounded text-gray-400 hover:text-blue-600" title="Exportar">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
              </button>
            </div>
          </div>
        ))}
        {!searches.length && <p className="text-center text-sm text-gray-400 py-4">Crea un caso primero</p>}
      </div>

      {selSearch && (
        <>
          <h3 className="font-semibold text-gray-700 text-sm mb-2">Resultados #{selSearch} ({rTotal})</h3>
          <div className="overflow-x-auto border rounded-lg">
            <table className="w-full text-sm">
              <thead><tr className="bg-gray-50 border-b">
                <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">Buzon</th>
                <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">Asunto</th>
                <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">Remitente</th>
                <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">Fecha</th>
                <th className="text-right px-3 py-2 text-xs font-semibold text-gray-500">Tam</th>
                <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500">SHA256</th>
              </tr></thead>
              <tbody>
                {results.map(r => (
                  <tr key={r.id} className="border-b border-gray-50 hover:bg-blue-50/30">
                    <td className="px-3 py-2"><Badge text={r.mailbox.split("@")[0]} color="bg-blue-100 text-blue-700" /></td>
                    <td className="px-3 py-2 font-medium max-w-[220px] truncate">{r.subject || "(sin asunto)"}</td>
                    <td className="px-3 py-2 text-gray-600 max-w-[140px] truncate">{r.sender}</td>
                    <td className="px-3 py-2 text-xs text-gray-500 whitespace-nowrap">{fmtDate(r.sent_at)}</td>
                    <td className="px-3 py-2 text-right text-xs text-gray-400">{fmtSize(r.size_bytes)}</td>
                    <td className="px-3 py-2 font-mono text-[10px] text-gray-400 max-w-[90px] truncate" title={r.hash_sha256}>{r.hash_sha256?.substring(0, 12)}...</td>
                  </tr>
                ))}
                {!results.length && <tr><td colSpan={6} className="text-center py-6 text-gray-400">Sin resultados</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

// ═══ LEGAL HOLDS ═══
function HoldsTab() {
  const [holds, setHolds] = useState<LegalHold[]>([]);
  const [cases, setCases] = useState<ComplianceCase[]>([]);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ case_id: "", mailbox: "", reason: "", scope: "all" });

  const load = useCallback(async () => {
    try { const d = await api.get<LegalHold[]>("/compliance/holds?active_only=false"); setHolds(Array.isArray(d) ? d : []); } catch {}
  }, []);
  useEffect(() => {
    load();
    api.get<any>("/compliance/cases?per_page=100").then(d => setCases(d.cases || [])).catch(() => {});
  }, [load]);

  async function create() {
    if (!form.case_id || !form.mailbox || !form.reason) return;
    await api.post("/compliance/holds", { ...form, case_id: Number(form.case_id) });
    setShowNew(false); setForm({ case_id: "", mailbox: "", reason: "", scope: "all" }); load();
  }
  async function release(id: number) {
    if (!confirm("Liberar retencion?")) return;
    await api.del(`/compliance/holds/${id}`); load();
  }

  return (
    <div>
      <div className="flex justify-between mb-4">
        <span className="text-xs text-gray-500">{holds.length} retenciones</span>
        <button onClick={() => setShowNew(!showNew)} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm">+ Nueva retencion</button>
      </div>
      {showNew && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <select value={form.case_id} onChange={e => setForm(f => ({ ...f, case_id: e.target.value }))} className="px-2 py-1.5 border rounded text-sm">
              <option value="">Caso *</option>
              {cases.filter(c => c.status !== "closed").map(c => <option key={c.id} value={c.id}>#{c.id} — {c.title}</option>)}
            </select>
            <input placeholder="Buzon (ej: contabilidad@ejemplo.com) *" value={form.mailbox} onChange={e => setForm(f => ({ ...f, mailbox: e.target.value }))} className="px-2 py-1.5 border rounded text-sm" />
            <select value={form.scope} onChange={e => setForm(f => ({ ...f, scope: e.target.value }))} className="px-2 py-1.5 border rounded text-sm">
              <option value="all">Todo el buzon</option><option value="inbox">Solo INBOX</option><option value="sent">Solo Enviados</option>
            </select>
          </div>
          <textarea placeholder="Motivo *" value={form.reason} onChange={e => setForm(f => ({ ...f, reason: e.target.value }))} className="w-full px-2 py-1.5 border rounded text-sm mb-3" rows={2} />
          <div className="flex gap-2">
            <button onClick={create} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm">Crear</button>
            <button onClick={() => setShowNew(false)} className="px-3 py-1.5 bg-white border text-gray-600 rounded text-sm">Cancelar</button>
          </div>
        </div>
      )}
      <div className="space-y-2">
        {holds.map(h => (
          <div key={h.id} className={`border rounded-lg p-3 flex justify-between items-center ${h.is_active ? "border-red-200 bg-red-50/30" : "opacity-50"}`}>
            <div>
              <div className="font-semibold text-gray-800">{h.mailbox}</div>
              <div className="text-xs text-gray-500">Caso #{h.case_id} — {h.reason.substring(0, 80)}</div>
            </div>
            <div className="flex items-center gap-2">
              <Badge text={h.is_active ? "ACTIVO" : "Liberado"} color={h.is_active ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-500"} />
              <span className="text-xs text-gray-400">{fmtDate(h.enabled_at)}</span>
              {h.is_active && <button onClick={() => release(h.id)} className="px-2 py-1 bg-white border text-gray-600 rounded text-xs">Liberar</button>}
            </div>
          </div>
        ))}
        {!holds.length && <div className="text-center py-8 text-gray-400 text-sm">Sin retenciones</div>}
      </div>
    </div>
  );
}

// ═══ ALERTS ═══
function AlertsTab() {
  const [alerts, setAlerts] = useState<FraudAlert[]>([]);
  const [total, setTotal] = useState(0);
  const [pg, setPg] = useState(1);
  const [loading, setLoading] = useState(false);
  const [f, setF] = useState({ alert_type: "", severity: "", acknowledged: "" });

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    const q = new URLSearchParams({ page: String(p), per_page: "50" });
    Object.entries(f).forEach(([k, v]) => { if (v) q.set(k, String(v)); });
    try { const d = await api.get<any>(`/compliance/alerts?${q}`); setAlerts(d.alerts || []); setTotal(d.total); setPg(p); } catch {}
    setLoading(false);
  }, [f]);
  useEffect(() => { load(); }, [load]);

  async function ack(id: number) { await api.post(`/compliance/alerts/${id}/acknowledge`); load(pg); }

  const sevBorder: Record<string, string> = { low: "border-l-gray-300", medium: "border-l-yellow-400", high: "border-l-orange-500", critical: "border-l-red-600" };

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-4">
        <select value={f.alert_type} onChange={e => setF(x => ({ ...x, alert_type: e.target.value }))} className="px-2 py-1.5 border rounded text-sm">
          <option value="">Todos los tipos</option>
          <option value="mass_send">Envio masivo</option><option value="evidence_destruction">Destruccion evidencia</option>
          <option value="external_forward">Reenvio externo</option><option value="unusual_login">Login inusual</option>
        </select>
        <select value={f.severity} onChange={e => setF(x => ({ ...x, severity: e.target.value }))} className="px-2 py-1.5 border rounded text-sm">
          <option value="">Toda severidad</option><option value="high">Alta</option><option value="critical">Critica</option>
        </select>
        <select value={f.acknowledged} onChange={e => setF(x => ({ ...x, acknowledged: e.target.value }))} className="px-2 py-1.5 border rounded text-sm">
          <option value="">Todas</option><option value="false">Sin revisar</option><option value="true">Revisadas</option>
        </select>
        <button onClick={() => load(1)} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm">Filtrar</button>
      </div>
      <div className="text-xs text-gray-500 mb-2">{total} alertas</div>
      {loading ? <Loader /> : (
        <div className="space-y-2">
          {alerts.map(a => (
            <div key={a.id} className={`border-l-4 ${sevBorder[a.severity] || "border-l-gray-300"} bg-white border border-gray-200 rounded-r-lg p-3 ${a.is_acknowledged ? "opacity-50" : ""}`}>
              <div className="flex justify-between items-start">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Badge text={a.alert_type.replace(/_/g, " ")} />
                    <Badge text={a.severity} color={riskBg[a.severity]} />
                    {a.is_acknowledged && <Badge text="Revisada" color="bg-green-100 text-green-600" />}
                  </div>
                  <div className="text-sm text-gray-800">{a.description}</div>
                  <div className="text-xs text-gray-500 mt-1">
                    <span className="font-mono">{a.username}</span>
                    {a.source_ip && <> — IP: <span className="font-mono">{a.source_ip}</span></>}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs text-gray-400">{fmtDate(a.created_at)}</span>
                  {!a.is_acknowledged && <button onClick={() => ack(a.id)} className="px-2 py-1 bg-green-600 text-white rounded text-xs">Revisar</button>}
                </div>
              </div>
            </div>
          ))}
          {!alerts.length && <div className="text-center py-8 text-gray-400 text-sm">Sin alertas</div>}
        </div>
      )}
      <Pager page={pg} total={total} perPage={50} onPage={load} />
    </div>
  );
}
