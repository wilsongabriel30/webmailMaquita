import { useState, useEffect, useCallback } from "react";
import { api } from "../../api/client";

// ─── Types ───
interface ActivityEntry {
  id: number; username: string; action: string; category: string;
  message_id: string | null; mailbox: string | null; folder: string | null;
  target: string | null; ip_address: string | null; user_agent: string | null;
  details: Record<string, unknown> | null; risk_level: string; created_at: string;
}

interface MailTraceEntry {
  id: number; queue_id: string; message_id: string; direction: string;
  sender: string; recipient: string; source_ip: string | null;
  spf_result: string | null; dkim_result: string | null; dmarc_result: string | null;
  rspamd_score: number | null; rspamd_action: string | null; status: string;
  dsn: string | null; delay_seconds: number | null; relay: string | null;
  tls_version: string | null; size_bytes: number | null; created_at: string;
}

interface ComplianceCase {
  id: number; title: string; description: string; reason: string;
  case_type: string; status: string; priority: string;
  created_by: string; approved_by: string | null; assigned_to: string | null;
  created_at: string; updated_at: string; closed_at: string | null;
  searches_count?: number; results_count?: number; active_holds?: number; exports_count?: number;
}

interface FraudAlert {
  id: number; alert_type: string; severity: string; username: string;
  description: string; details: Record<string, unknown> | null;
  source_ip: string | null; is_acknowledged: boolean;
  acknowledged_by: string | null; case_id: number | null; created_at: string;
}

interface LegalHold {
  id: number; case_id: number; mailbox: string; scope: string;
  reason: string; enabled_by: string; enabled_at: string;
  is_active: boolean; released_by: string | null; released_at: string | null;
}

interface SearchResult {
  id: number; search_id: number; mailbox: string; folder: string;
  uid: number; message_id: string; subject: string; sender: string;
  recipients: string; sent_at: string; size_bytes: number;
  has_attachments: boolean; hash_sha256: string;
}

interface Paginated<T> { entries?: T[]; cases?: T[]; alerts?: T[]; searches?: T[]; total: number; page: number; per_page?: number; }

// ─── Helpers ───
const TABS = [
  { id: "dashboard", label: "Dashboard", icon: "M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" },
  { id: "activity", label: "Actividad", icon: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" },
  { id: "trace", label: "Mail Trace", icon: "M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" },
  { id: "cases", label: "Casos", icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" },
  { id: "ediscovery", label: "eDiscovery", icon: "M10 21h7a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v11m0 5l4.879-4.879m0 0a3 3 0 104.243-4.242 3 3 0 00-4.243 4.242z" },
  { id: "holds", label: "Legal Hold", icon: "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" },
  { id: "alerts", label: "Alertas", icon: "M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" },
];

const riskColors: Record<string, string> = {
  low: "bg-slate-100 text-slate-600",
  medium: "bg-amber-100 text-amber-700",
  high: "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};

const statusColors: Record<string, string> = {
  open: "bg-blue-100 text-blue-700",
  approved: "bg-green-100 text-green-700",
  in_progress: "bg-amber-100 text-amber-700",
  closed: "bg-slate-100 text-slate-600",
  archived: "bg-slate-50 text-slate-400",
};

const directionLabels: Record<string, string> = {
  inbound: "Entrante", outbound: "Saliente", internal: "Interno",
};

function Badge({ text, color }: { text: string; color: string }) {
  return <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>{text}</span>;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString("es-EC", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }); }
  catch { return iso.substring(0, 19); }
}

function fmtSize(b: number | null): string {
  if (!b) return "—";
  if (b < 1024) return b + " B";
  if (b < 1048576) return (b / 1024).toFixed(1) + " KB";
  return (b / 1048576).toFixed(1) + " MB";
}

// ─── Main Component ───
export function CompliancePanel() {
  const [tab, setTab] = useState("dashboard");

  return (
    <div className="p-6 max-w-[1400px]">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
          <svg className="w-7 h-7 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
          Compliance & eDiscovery
        </h1>
        <p className="text-sm text-slate-500 mt-1">Auditoria, trazabilidad y busqueda forense — tipo Microsoft Purview</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-slate-100 p-1 rounded-xl overflow-x-auto">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
              tab === t.id ? "bg-white text-indigo-700 shadow-sm" : "text-slate-500 hover:text-slate-700 hover:bg-white/50"
            }`}>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={t.icon} />
            </svg>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "dashboard" && <DashboardTab />}
      {tab === "activity" && <ActivityTab />}
      {tab === "trace" && <MailTraceTab />}
      {tab === "cases" && <CasesTab />}
      {tab === "ediscovery" && <EDiscoveryTab />}
      {tab === "holds" && <HoldsTab />}
      {tab === "alerts" && <AlertsTab />}
    </div>
  );
}

// ═══════════════════════════════════════════
// DASHBOARD TAB
// ═══════════════════════════════════════════
function DashboardTab() {
  const [actStats, setActStats] = useState<any>(null);
  const [traceStats, setTraceStats] = useState<any>(null);
  const [alertStats, setAlertStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<any>("/compliance/activity/stats?days=30").catch(() => null),
      api.get<any>("/compliance/mail-trace/stats?hours=24").catch(() => null),
      api.get<any>("/compliance/alerts/stats?days=30").catch(() => null),
    ]).then(([a, t, al]) => {
      setActStats(a); setTraceStats(t); setAlertStats(al); setLoading(false);
    });
  }, []);

  if (loading) return <div className="flex items-center justify-center py-20"><div className="animate-spin w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full" /></div>;

  return (
    <div className="space-y-6">
      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Actividad (30d)" value={actStats?.total ?? 0} icon="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" color="indigo" />
        <StatCard label="Mail Trace (24h)" value={traceStats?.total ?? 0} icon="M3 8l7.89 5.26a2 2 0 002.22 0L21 8" color="blue" />
        <StatCard label="Alertas (30d)" value={alertStats?.total ?? 0} icon="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11" color="amber" />
        <StatCard label="Sin revisar" value={alertStats?.unacknowledged ?? 0} icon="M12 9v2m0 4h.01" color="red" />
      </div>

      {/* Risk breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h3 className="font-semibold text-slate-800 mb-4">Actividad por riesgo (30d)</h3>
          {actStats?.by_risk && Object.entries(actStats.by_risk).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between py-2 border-b border-slate-50">
              <Badge text={k} color={riskColors[k] || "bg-slate-100 text-slate-600"} />
              <span className="font-mono text-sm font-bold text-slate-700">{v as number}</span>
            </div>
          ))}
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h3 className="font-semibold text-slate-800 mb-4">Top acciones (30d)</h3>
          {actStats?.top_actions?.slice(0, 8).map((a: any) => (
            <div key={a.action} className="flex items-center justify-between py-2 border-b border-slate-50">
              <span className="text-sm text-slate-600 font-mono">{a.action}</span>
              <span className="font-mono text-sm font-bold text-slate-700">{a.total}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Mail trace by status */}
      {traceStats?.by_status && (
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h3 className="font-semibold text-slate-800 mb-4">Correos por estado (24h)</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(traceStats.by_status).map(([k, v]) => (
              <div key={k} className="text-center p-3 bg-slate-50 rounded-lg">
                <div className="text-2xl font-bold text-slate-800">{v as number}</div>
                <div className="text-xs text-slate-500 mt-1">{k}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Alert types */}
      {alertStats?.by_type && Object.keys(alertStats.by_type).length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h3 className="font-semibold text-slate-800 mb-4">Alertas por tipo (30d)</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(alertStats.by_type).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between p-3 bg-amber-50 rounded-lg">
                <span className="text-sm text-slate-700">{k.replace(/_/g, " ")}</span>
                <span className="font-bold text-amber-700">{v as number}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, icon, color }: { label: string; value: number; icon: string; color: string }) {
  const colors: Record<string, string> = {
    indigo: "bg-indigo-50 text-indigo-600", blue: "bg-blue-50 text-blue-600",
    amber: "bg-amber-50 text-amber-600", red: "bg-red-50 text-red-600",
  };
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-3xl font-bold text-slate-800">{value.toLocaleString()}</div>
          <div className="text-sm text-slate-500 mt-1">{label}</div>
        </div>
        <div className={`p-3 rounded-xl ${colors[color]}`}>
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={icon} />
          </svg>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════
// ACTIVITY TAB
// ═══════════════════════════════════════════
function ActivityTab() {
  const [entries, setEntries] = useState<ActivityEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ username: "", action: "", category: "", risk_level: "", date_from: "", date_to: "" });

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(p), per_page: "50" });
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
    try {
      const data = await api.get<Paginated<ActivityEntry>>(`/compliance/activity?${params}`);
      setEntries(data.entries || []); setTotal(data.total); setPage(p);
    } catch { }
    setLoading(false);
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      {/* Filters */}
      <div className="bg-slate-50 rounded-xl border border-slate-200 p-4 mb-4">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <input placeholder="Usuario" value={filters.username} onChange={e => setFilters(f => ({ ...f, username: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
          <select value={filters.action} onChange={e => setFilters(f => ({ ...f, action: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white">
            <option value="">Todas las acciones</option>
            <option value="login_success">Login OK</option>
            <option value="login_failed">Login fallido</option>
            <option value="password_change">Cambio password</option>
            <option value="email_send">Enviar correo</option>
            <option value="email_delete">Eliminar correo</option>
            <option value="email_export">Exportar correo</option>
            <option value="sieve_create">Crear filtro Sieve</option>
            <option value="forward_create">Crear reenvio</option>
            <option value="impersonate">Impersonar</option>
            <option value="totp_setup">Activar 2FA</option>
            <option value="totp_disable">Desactivar 2FA</option>
          </select>
          <select value={filters.category} onChange={e => setFilters(f => ({ ...f, category: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white">
            <option value="">Todas categorias</option>
            <option value="auth">Autenticacion</option>
            <option value="email">Correo</option>
            <option value="sieve">Filtros/Sieve</option>
            <option value="security">Seguridad</option>
            <option value="compliance">Compliance</option>
            <option value="admin">Admin</option>
          </select>
          <select value={filters.risk_level} onChange={e => setFilters(f => ({ ...f, risk_level: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white">
            <option value="">Todo riesgo</option>
            <option value="low">Bajo</option>
            <option value="medium">Medio</option>
            <option value="high">Alto</option>
            <option value="critical">Critico</option>
          </select>
          <input type="date" value={filters.date_from} onChange={e => setFilters(f => ({ ...f, date_from: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
          <input type="date" value={filters.date_to} onChange={e => setFilters(f => ({ ...f, date_to: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
        </div>
        <div className="mt-3 flex gap-2">
          <button onClick={() => load(1)} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">Buscar</button>
          <button onClick={() => { setFilters({ username: "", action: "", category: "", risk_level: "", date_from: "", date_to: "" }); }}
            className="px-4 py-2 bg-white border border-slate-300 text-slate-600 rounded-lg text-sm hover:bg-slate-50">Limpiar</button>
        </div>
      </div>

      <div className="text-sm text-slate-500 mb-3">{total.toLocaleString()} registros</div>

      {loading ? <Loader /> : (
        <div className="border border-slate-200 rounded-xl overflow-hidden overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="bg-slate-50 border-b border-slate-200">
              <th className="text-left px-3 py-2.5 font-semibold text-slate-600">Fecha</th>
              <th className="text-left px-3 py-2.5 font-semibold text-slate-600">Usuario</th>
              <th className="text-left px-3 py-2.5 font-semibold text-slate-600">Accion</th>
              <th className="text-left px-3 py-2.5 font-semibold text-slate-600">Categoria</th>
              <th className="text-left px-3 py-2.5 font-semibold text-slate-600">Riesgo</th>
              <th className="text-left px-3 py-2.5 font-semibold text-slate-600">IP</th>
              <th className="text-left px-3 py-2.5 font-semibold text-slate-600">Target</th>
            </tr></thead>
            <tbody>
              {entries.map(e => (
                <tr key={e.id} className="border-b border-slate-50 hover:bg-indigo-50/30">
                  <td className="px-3 py-2 text-xs text-slate-500 whitespace-nowrap">{fmtDate(e.created_at)}</td>
                  <td className="px-3 py-2 font-medium text-slate-700">{e.username}</td>
                  <td className="px-3 py-2 font-mono text-xs">{e.action}</td>
                  <td className="px-3 py-2"><Badge text={e.category} color="bg-slate-100 text-slate-600" /></td>
                  <td className="px-3 py-2"><Badge text={e.risk_level} color={riskColors[e.risk_level]} /></td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-400">{e.ip_address || "—"}</td>
                  <td className="px-3 py-2 text-xs text-slate-500 max-w-[200px] truncate">{e.target || "—"}</td>
                </tr>
              ))}
              {entries.length === 0 && <tr><td colSpan={7} className="text-center py-8 text-slate-400">Sin registros</td></tr>}
            </tbody>
          </table>
        </div>
      )}
      <Pagination page={page} total={total} perPage={50} onPage={load} />
    </div>
  );
}

// ═══════════════════════════════════════════
// MAIL TRACE TAB
// ═══════════════════════════════════════════
function MailTraceTab() {
  const [entries, setEntries] = useState<MailTraceEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ sender: "", recipient: "", status: "", direction: "", date_from: "", date_to: "" });

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(p), per_page: "50" });
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
    try {
      const data = await api.get<Paginated<MailTraceEntry>>(`/compliance/mail-trace?${params}`);
      setEntries(data.entries || []); setTotal(data.total); setPage(p);
    } catch { }
    setLoading(false);
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <div className="bg-slate-50 rounded-xl border border-slate-200 p-4 mb-4">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <input placeholder="Remitente" value={filters.sender} onChange={e => setFilters(f => ({ ...f, sender: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
          <input placeholder="Destinatario" value={filters.recipient} onChange={e => setFilters(f => ({ ...f, recipient: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
          <select value={filters.status} onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white">
            <option value="">Todo estado</option>
            <option value="sent">Enviado</option>
            <option value="deferred">Diferido</option>
            <option value="bounced">Rebotado</option>
            <option value="rejected">Rechazado</option>
          </select>
          <select value={filters.direction} onChange={e => setFilters(f => ({ ...f, direction: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white">
            <option value="">Toda direccion</option>
            <option value="inbound">Entrante</option>
            <option value="outbound">Saliente</option>
            <option value="internal">Interno</option>
          </select>
          <input type="date" value={filters.date_from} onChange={e => setFilters(f => ({ ...f, date_from: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
          <input type="date" value={filters.date_to} onChange={e => setFilters(f => ({ ...f, date_to: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
        </div>
        <div className="mt-3 flex gap-2">
          <button onClick={() => load(1)} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">Buscar</button>
          <button onClick={() => setFilters({ sender: "", recipient: "", status: "", direction: "", date_from: "", date_to: "" })}
            className="px-4 py-2 bg-white border border-slate-300 text-slate-600 rounded-lg text-sm hover:bg-slate-50">Limpiar</button>
        </div>
      </div>

      <div className="text-sm text-slate-500 mb-3">{total.toLocaleString()} registros</div>

      {loading ? <Loader /> : (
        <div className="border border-slate-200 rounded-xl overflow-hidden overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="bg-slate-50 border-b border-slate-200">
              <th className="text-left px-3 py-2.5 font-semibold text-slate-600">Fecha</th>
              <th className="text-left px-3 py-2.5 font-semibold text-slate-600">Dir</th>
              <th className="text-left px-3 py-2.5 font-semibold text-slate-600">Remitente</th>
              <th className="text-left px-3 py-2.5 font-semibold text-slate-600">Destinatario</th>
              <th className="text-left px-3 py-2.5 font-semibold text-slate-600">Estado</th>
              <th className="text-left px-3 py-2.5 font-semibold text-slate-600">Score</th>
              <th className="text-left px-3 py-2.5 font-semibold text-slate-600">SPF/DKIM/DMARC</th>
              <th className="text-left px-3 py-2.5 font-semibold text-slate-600">IP</th>
              <th className="text-right px-3 py-2.5 font-semibold text-slate-600">Tam</th>
            </tr></thead>
            <tbody>
              {entries.map(e => (
                <tr key={e.id} className="border-b border-slate-50 hover:bg-blue-50/30">
                  <td className="px-3 py-2 text-xs text-slate-500 whitespace-nowrap">{fmtDate(e.created_at)}</td>
                  <td className="px-3 py-2"><Badge text={directionLabels[e.direction] || e.direction} color={e.direction === "inbound" ? "bg-green-100 text-green-700" : e.direction === "outbound" ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-600"} /></td>
                  <td className="px-3 py-2 text-slate-700 max-w-[180px] truncate">{e.sender || "—"}</td>
                  <td className="px-3 py-2 text-slate-700 max-w-[180px] truncate">{e.recipient || "—"}</td>
                  <td className="px-3 py-2"><Badge text={e.status} color={e.status === "sent" ? "bg-green-100 text-green-700" : e.status === "bounced" ? "bg-red-100 text-red-700" : e.status === "deferred" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-600"} /></td>
                  <td className="px-3 py-2 font-mono text-xs">{e.rspamd_score != null ? e.rspamd_score.toFixed(1) : "—"}</td>
                  <td className="px-3 py-2 text-xs font-mono">{[e.spf_result, e.dkim_result, e.dmarc_result].filter(Boolean).join("/") || "—"}</td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-400">{e.source_ip || "—"}</td>
                  <td className="px-3 py-2 text-right text-xs text-slate-400">{fmtSize(e.size_bytes)}</td>
                </tr>
              ))}
              {entries.length === 0 && <tr><td colSpan={9} className="text-center py-8 text-slate-400">Sin registros</td></tr>}
            </tbody>
          </table>
        </div>
      )}
      <Pagination page={page} total={total} perPage={50} onPage={load} />
    </div>
  );
}

// ═══════════════════════════════════════════
// CASES TAB
// ═══════════════════════════════════════════
function CasesTab() {
  const [cases, setCases] = useState<ComplianceCase[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [newCase, setNewCase] = useState({ title: "", description: "", reason: "", case_type: "investigation", priority: "normal" });
  const [selectedCase, setSelectedCase] = useState<ComplianceCase | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<{ cases: ComplianceCase[]; total: number }>("/compliance/cases?per_page=50");
      setCases(data.cases || []); setTotal(data.total);
    } catch { }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  async function createCase() {
    if (!newCase.title || !newCase.reason) return;
    try {
      await api.post("/compliance/cases", newCase);
      setShowNew(false); setNewCase({ title: "", description: "", reason: "", case_type: "investigation", priority: "normal" });
      load();
    } catch { }
  }

  async function updateStatus(id: number, status: string) {
    try {
      await api.put(`/compliance/cases/${id}`, { status });
      load(); setSelectedCase(null);
    } catch { }
  }

  async function viewCase(id: number) {
    try {
      const data = await api.get<ComplianceCase>(`/compliance/cases/${id}`);
      setSelectedCase(data);
    } catch { }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="text-sm text-slate-500">{total} casos</div>
        <button onClick={() => setShowNew(!showNew)}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
          Nuevo caso
        </button>
      </div>

      {showNew && (
        <div className="bg-indigo-50 rounded-xl border border-indigo-200 p-5 mb-4">
          <h3 className="font-semibold text-slate-800 mb-3">Crear caso de compliance</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
            <input placeholder="Titulo del caso *" value={newCase.title} onChange={e => setNewCase(c => ({ ...c, title: e.target.value }))}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
            <select value={newCase.case_type} onChange={e => setNewCase(c => ({ ...c, case_type: e.target.value }))}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white">
              <option value="investigation">Investigacion</option>
              <option value="fraud">Fraude</option>
              <option value="compliance">Compliance</option>
              <option value="legal">Legal</option>
              <option value="hr">Recursos Humanos</option>
              <option value="security">Seguridad</option>
            </select>
          </div>
          <textarea placeholder="Motivo / justificacion *" value={newCase.reason} onChange={e => setNewCase(c => ({ ...c, reason: e.target.value }))}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm mb-3" rows={2} />
          <textarea placeholder="Descripcion adicional" value={newCase.description} onChange={e => setNewCase(c => ({ ...c, description: e.target.value }))}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm mb-3" rows={2} />
          <div className="flex gap-2">
            <button onClick={createCase} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">Crear caso</button>
            <button onClick={() => setShowNew(false)} className="px-4 py-2 bg-white border border-slate-300 text-slate-600 rounded-lg text-sm">Cancelar</button>
          </div>
        </div>
      )}

      {/* Case detail modal */}
      {selectedCase && (
        <div className="bg-white border-2 border-indigo-200 rounded-xl p-5 mb-4 shadow-lg">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="font-bold text-lg text-slate-800">{selectedCase.title}</h3>
              <p className="text-sm text-slate-500 mt-1">{selectedCase.reason}</p>
            </div>
            <button onClick={() => setSelectedCase(null)} className="text-slate-400 hover:text-slate-600 text-xl">&times;</button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4 text-sm">
            <div><span className="text-slate-500">Estado:</span> <Badge text={selectedCase.status} color={statusColors[selectedCase.status]} /></div>
            <div><span className="text-slate-500">Tipo:</span> <span className="font-medium">{selectedCase.case_type}</span></div>
            <div><span className="text-slate-500">Creado:</span> <span className="font-medium">{fmtDate(selectedCase.created_at)}</span></div>
            <div><span className="text-slate-500">Por:</span> <span className="font-medium">{selectedCase.created_by}</span></div>
          </div>
          {selectedCase.searches_count != null && (
            <div className="grid grid-cols-4 gap-3 mb-4">
              <div className="text-center p-2 bg-slate-50 rounded-lg"><div className="font-bold">{selectedCase.searches_count}</div><div className="text-xs text-slate-500">Busquedas</div></div>
              <div className="text-center p-2 bg-slate-50 rounded-lg"><div className="font-bold">{selectedCase.results_count}</div><div className="text-xs text-slate-500">Resultados</div></div>
              <div className="text-center p-2 bg-slate-50 rounded-lg"><div className="font-bold">{selectedCase.active_holds}</div><div className="text-xs text-slate-500">Holds activos</div></div>
              <div className="text-center p-2 bg-slate-50 rounded-lg"><div className="font-bold">{selectedCase.exports_count}</div><div className="text-xs text-slate-500">Exportaciones</div></div>
            </div>
          )}
          <div className="flex gap-2">
            {selectedCase.status === "open" && <button onClick={() => updateStatus(selectedCase.id, "approved")} className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700">Aprobar</button>}
            {selectedCase.status === "approved" && <button onClick={() => updateStatus(selectedCase.id, "in_progress")} className="px-3 py-1.5 bg-amber-600 text-white rounded-lg text-sm hover:bg-amber-700">Iniciar</button>}
            {["open","approved","in_progress"].includes(selectedCase.status) && <button onClick={() => updateStatus(selectedCase.id, "closed")} className="px-3 py-1.5 bg-slate-600 text-white rounded-lg text-sm hover:bg-slate-700">Cerrar</button>}
          </div>
        </div>
      )}

      {loading ? <Loader /> : (
        <div className="space-y-3">
          {cases.map(c => (
            <div key={c.id} onClick={() => viewCase(c.id)}
              className="bg-white border border-slate-200 rounded-xl p-4 hover:border-indigo-300 hover:shadow-sm transition-all cursor-pointer">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-lg font-bold text-slate-300">#{c.id}</span>
                  <div>
                    <div className="font-semibold text-slate-800">{c.title}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{c.reason.substring(0, 100)}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Badge text={c.case_type} color="bg-slate-100 text-slate-600" />
                  <Badge text={c.status} color={statusColors[c.status] || "bg-slate-100 text-slate-600"} />
                  <span className="text-xs text-slate-400">{fmtDate(c.created_at)}</span>
                </div>
              </div>
            </div>
          ))}
          {cases.length === 0 && <div className="text-center py-12 text-slate-400">Sin casos. Crea uno para iniciar una investigacion.</div>}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════
// eDISCOVERY TAB
// ═══════════════════════════════════════════
function EDiscoveryTab() {
  const [cases, setCases] = useState<ComplianceCase[]>([]);
  const [searches, setSearches] = useState<any[]>([]);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [selectedSearchId, setSelectedSearchId] = useState<number | null>(null);
  const [resultsTotal, setResultsTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [form, setForm] = useState({
    case_id: "", mailboxes_scope: "", keywords: "", date_from: "", date_to: "",
    senders_filter: "", recipients_filter: "",
  });

  useEffect(() => {
    api.get<{ cases: ComplianceCase[] }>("/compliance/cases?per_page=100").then(d => setCases(d.cases || [])).catch(() => {});
    api.get<{ searches: any[]; total: number }>("/compliance/ediscovery/searches?per_page=50").then(d => setSearches(d.searches || [])).catch(() => {});
  }, []);

  async function runSearch() {
    if (!form.case_id) return;
    setSearchLoading(true);
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
      // Reload searches
      const d = await api.get<{ searches: any[] }>("/compliance/ediscovery/searches?per_page=50");
      setSearches(d.searches || []);
      if (res.search_id) viewResults(res.search_id);
    } catch (e: any) {
      alert("Error: " + (e.message || ""));
    }
    setSearchLoading(false);
  }

  async function viewResults(searchId: number) {
    setLoading(true);
    setSelectedSearchId(searchId);
    try {
      const data = await api.get<{ results: SearchResult[]; total: number }>(`/compliance/ediscovery/results/${searchId}?per_page=100`);
      setResults(data.results || []); setResultsTotal(data.total);
    } catch { }
    setLoading(false);
  }

  async function exportSearch(searchId: number, caseId: number) {
    try {
      const res = await api.post<any>("/compliance/ediscovery/export", {
        case_id: caseId, search_id: searchId, reason: "Exportacion desde panel admin",
      });
      alert(`Exportados ${res.exported} mensajes.\nHash: ${res.manifest_hash}\nRuta: ${res.export_path}`);
    } catch (e: any) {
      alert("Error: " + (e.message || ""));
    }
  }

  return (
    <div>
      {/* New Search */}
      <div className="bg-slate-50 rounded-xl border border-slate-200 p-5 mb-6">
        <h3 className="font-semibold text-slate-800 mb-3">Nueva busqueda forense</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-3">
          <select value={form.case_id} onChange={e => setForm(f => ({ ...f, case_id: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white">
            <option value="">Seleccionar caso *</option>
            {cases.filter(c => ["open","approved","in_progress"].includes(c.status)).map(c => (
              <option key={c.id} value={c.id}>#{c.id} — {c.title}</option>
            ))}
          </select>
          <input placeholder="Buzones (separados por coma, vacio=todos)" value={form.mailboxes_scope}
            onChange={e => setForm(f => ({ ...f, mailboxes_scope: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
          <input placeholder="Palabras clave (separadas por coma)" value={form.keywords}
            onChange={e => setForm(f => ({ ...f, keywords: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
          <input placeholder="Remitentes (filtro)" value={form.senders_filter}
            onChange={e => setForm(f => ({ ...f, senders_filter: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
          <input placeholder="Destinatarios (filtro)" value={form.recipients_filter}
            onChange={e => setForm(f => ({ ...f, recipients_filter: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
          <input type="date" placeholder="Desde" value={form.date_from} onChange={e => setForm(f => ({ ...f, date_from: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
          <input type="date" placeholder="Hasta" value={form.date_to} onChange={e => setForm(f => ({ ...f, date_to: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
        </div>
        <button onClick={runSearch} disabled={searchLoading || !form.case_id}
          className="px-5 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2">
          {searchLoading ? <><div className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" /> Buscando...</> : "Ejecutar busqueda"}
        </button>
      </div>

      {/* Search history */}
      <h3 className="font-semibold text-slate-800 mb-3">Busquedas anteriores</h3>
      <div className="space-y-2 mb-6">
        {searches.map(s => (
          <div key={s.id} className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors ${
            selectedSearchId === s.id ? "border-indigo-400 bg-indigo-50" : "border-slate-200 hover:border-slate-300 bg-white"
          }`} onClick={() => viewResults(s.id)}>
            <div className="flex items-center gap-3">
              <span className="font-mono text-xs text-slate-400">#{s.id}</span>
              <span className="text-sm">Caso #{s.case_id}</span>
              {s.keywords && <span className="text-xs text-slate-500">Keywords: {Array.isArray(s.keywords) ? s.keywords.join(", ") : s.keywords}</span>}
            </div>
            <div className="flex items-center gap-3">
              <Badge text={s.status || "?"} color={s.status === "completed" ? "bg-green-100 text-green-700" : s.status === "running" ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"} />
              <span className="text-sm font-bold text-slate-700">{s.result_count ?? 0} resultados</span>
              <span className="text-xs text-slate-400">{s.duration_ms ? `${s.duration_ms}ms` : ""}</span>
              <button onClick={(e) => { e.stopPropagation(); exportSearch(s.id, s.case_id); }}
                className="p-1.5 rounded-lg hover:bg-indigo-100 text-slate-400 hover:text-indigo-600" title="Exportar con hash SHA256">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </button>
            </div>
          </div>
        ))}
        {searches.length === 0 && <div className="text-center py-6 text-slate-400 text-sm">Sin busquedas. Crea un caso primero.</div>}
      </div>

      {/* Results */}
      {selectedSearchId && (
        <>
          <h3 className="font-semibold text-slate-800 mb-3">Resultados de busqueda #{selectedSearchId} ({resultsTotal})</h3>
          {loading ? <Loader /> : (
            <div className="border border-slate-200 rounded-xl overflow-hidden overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="bg-slate-50 border-b border-slate-200">
                  <th className="text-left px-3 py-2.5 font-semibold text-slate-600">Buzon</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-slate-600">Carpeta</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-slate-600">Asunto</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-slate-600">Remitente</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-slate-600">Fecha</th>
                  <th className="text-right px-3 py-2.5 font-semibold text-slate-600">Tam</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-slate-600">SHA256</th>
                </tr></thead>
                <tbody>
                  {results.map(r => (
                    <tr key={r.id} className="border-b border-slate-50 hover:bg-indigo-50/30">
                      <td className="px-3 py-2"><Badge text={r.mailbox.split("@")[0]} color="bg-blue-100 text-blue-700" /></td>
                      <td className="px-3 py-2 text-xs text-slate-500">{r.folder}</td>
                      <td className="px-3 py-2 font-medium text-slate-800 max-w-[250px] truncate">{r.subject || "(sin asunto)"}</td>
                      <td className="px-3 py-2 text-slate-600 max-w-[150px] truncate">{r.sender}</td>
                      <td className="px-3 py-2 text-xs text-slate-500 whitespace-nowrap">{fmtDate(r.sent_at)}</td>
                      <td className="px-3 py-2 text-right text-xs text-slate-400">{fmtSize(r.size_bytes)}</td>
                      <td className="px-3 py-2 font-mono text-[10px] text-slate-400 max-w-[100px] truncate" title={r.hash_sha256}>{r.hash_sha256?.substring(0, 12)}...</td>
                    </tr>
                  ))}
                  {results.length === 0 && <tr><td colSpan={7} className="text-center py-8 text-slate-400">Sin resultados</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════
// LEGAL HOLDS TAB
// ═══════════════════════════════════════════
function HoldsTab() {
  const [holds, setHolds] = useState<LegalHold[]>([]);
  const [cases, setCases] = useState<ComplianceCase[]>([]);
  const [loading, setLoading] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ case_id: "", mailbox: "", reason: "", scope: "all" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<LegalHold[]>("/compliance/holds?active_only=false");
      setHolds(Array.isArray(data) ? data : []);
    } catch { }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    api.get<{ cases: ComplianceCase[] }>("/compliance/cases?per_page=100").then(d => setCases(d.cases || [])).catch(() => {});
  }, [load]);

  async function createHold() {
    if (!form.case_id || !form.mailbox || !form.reason) return;
    try {
      await api.post("/compliance/holds", { ...form, case_id: Number(form.case_id) });
      setShowNew(false); setForm({ case_id: "", mailbox: "", reason: "", scope: "all" });
      load();
    } catch (e: any) { alert("Error: " + (e.message || "")); }
  }

  async function releaseHold(id: number) {
    if (!confirm("Liberar esta retencion legal?")) return;
    try { await api.del(`/compliance/holds/${id}`); load(); } catch { }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="text-sm text-slate-500">{holds.length} retenciones</div>
        <button onClick={() => setShowNew(!showNew)}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
          Nueva retencion
        </button>
      </div>

      {showNew && (
        <div className="bg-indigo-50 rounded-xl border border-indigo-200 p-5 mb-4">
          <h3 className="font-semibold text-slate-800 mb-3">Crear retencion legal</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <select value={form.case_id} onChange={e => setForm(f => ({ ...f, case_id: e.target.value }))}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white">
              <option value="">Caso asociado *</option>
              {cases.filter(c => c.status !== "closed").map(c => (
                <option key={c.id} value={c.id}>#{c.id} — {c.title}</option>
              ))}
            </select>
            <input placeholder="Buzon (ej: contabilidad@maquita.org) *" value={form.mailbox}
              onChange={e => setForm(f => ({ ...f, mailbox: e.target.value }))}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
            <select value={form.scope} onChange={e => setForm(f => ({ ...f, scope: e.target.value }))}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white">
              <option value="all">Todo el buzon</option>
              <option value="inbox">Solo INBOX</option>
              <option value="sent">Solo Enviados</option>
            </select>
          </div>
          <textarea placeholder="Motivo de la retencion *" value={form.reason}
            onChange={e => setForm(f => ({ ...f, reason: e.target.value }))}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm mb-3" rows={2} />
          <div className="flex gap-2">
            <button onClick={createHold} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">Crear retencion</button>
            <button onClick={() => setShowNew(false)} className="px-4 py-2 bg-white border border-slate-300 text-slate-600 rounded-lg text-sm">Cancelar</button>
          </div>
        </div>
      )}

      {loading ? <Loader /> : (
        <div className="space-y-3">
          {holds.map(h => (
            <div key={h.id} className={`border rounded-xl p-4 ${h.is_active ? "border-red-200 bg-red-50/30" : "border-slate-200 bg-white opacity-60"}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <svg className={`w-5 h-5 ${h.is_active ? "text-red-500" : "text-slate-300"}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                  <div>
                    <div className="font-semibold text-slate-800">{h.mailbox}</div>
                    <div className="text-xs text-slate-500">Caso #{h.case_id} — {h.reason.substring(0, 80)}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Badge text={h.is_active ? "ACTIVO" : "Liberado"} color={h.is_active ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-500"} />
                  <span className="text-xs text-slate-400">{fmtDate(h.enabled_at)}</span>
                  {h.is_active && (
                    <button onClick={() => releaseHold(h.id)}
                      className="px-3 py-1 bg-white border border-slate-300 text-slate-600 rounded-lg text-xs hover:bg-slate-50">
                      Liberar
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
          {holds.length === 0 && <div className="text-center py-12 text-slate-400">Sin retenciones legales activas</div>}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════
// ALERTS TAB
// ═══════════════════════════════════════════
function AlertsTab() {
  const [alerts, setAlerts] = useState<FraudAlert[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ alert_type: "", severity: "", acknowledged: "" });

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(p), per_page: "50" });
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
    try {
      const data = await api.get<{ alerts: FraudAlert[]; total: number }>(`/compliance/alerts?${params}`);
      setAlerts(data.alerts || []); setTotal(data.total); setPage(p);
    } catch { }
    setLoading(false);
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  async function acknowledge(id: number) {
    try { await api.post(`/compliance/alerts/${id}/acknowledge`); load(page); } catch { }
  }

  const severityColors: Record<string, string> = {
    low: "border-l-slate-300", medium: "border-l-amber-400", high: "border-l-orange-500", critical: "border-l-red-600",
  };

  return (
    <div>
      <div className="bg-slate-50 rounded-xl border border-slate-200 p-4 mb-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <select value={filters.alert_type} onChange={e => setFilters(f => ({ ...f, alert_type: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white">
            <option value="">Todos los tipos</option>
            <option value="mass_send">Envio masivo</option>
            <option value="evidence_destruction">Destruccion evidencia</option>
            <option value="external_forward">Reenvio externo</option>
            <option value="unusual_login">Login inusual</option>
            <option value="suspicious_sieve">Sieve sospechoso</option>
            <option value="mass_download">Descarga masiva</option>
          </select>
          <select value={filters.severity} onChange={e => setFilters(f => ({ ...f, severity: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white">
            <option value="">Toda severidad</option>
            <option value="low">Baja</option>
            <option value="medium">Media</option>
            <option value="high">Alta</option>
            <option value="critical">Critica</option>
          </select>
          <select value={filters.acknowledged} onChange={e => setFilters(f => ({ ...f, acknowledged: e.target.value }))}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white">
            <option value="">Todas</option>
            <option value="false">Sin revisar</option>
            <option value="true">Revisadas</option>
          </select>
        </div>
        <button onClick={() => load(1)} className="mt-3 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">Filtrar</button>
      </div>

      <div className="text-sm text-slate-500 mb-3">{total} alertas</div>

      {loading ? <Loader /> : (
        <div className="space-y-2">
          {alerts.map(a => (
            <div key={a.id} className={`border-l-4 ${severityColors[a.severity] || "border-l-slate-300"} bg-white border border-slate-200 rounded-r-xl p-4 ${a.is_acknowledged ? "opacity-50" : ""}`}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Badge text={a.alert_type.replace(/_/g, " ")} color="bg-slate-100 text-slate-700" />
                    <Badge text={a.severity} color={riskColors[a.severity]} />
                    {a.is_acknowledged && <Badge text="Revisada" color="bg-green-100 text-green-600" />}
                  </div>
                  <div className="text-sm text-slate-800 font-medium">{a.description}</div>
                  <div className="text-xs text-slate-500 mt-1">
                    Usuario: <span className="font-mono">{a.username}</span>
                    {a.source_ip && <> — IP: <span className="font-mono">{a.source_ip}</span></>}
                    {a.case_id && <> — Caso #{a.case_id}</>}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400 whitespace-nowrap">{fmtDate(a.created_at)}</span>
                  {!a.is_acknowledged && (
                    <button onClick={() => acknowledge(a.id)}
                      className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs hover:bg-green-700">
                      Revisar
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
          {alerts.length === 0 && <div className="text-center py-12 text-slate-400">Sin alertas antifraude</div>}
        </div>
      )}
      <Pagination page={page} total={total} perPage={50} onPage={load} />
    </div>
  );
}

// ─── Shared components ───
function Loader() {
  return <div className="flex items-center justify-center py-12"><div className="animate-spin w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full" /></div>;
}

function Pagination({ page, total, perPage, onPage }: { page: number; total: number; perPage: number; onPage: (p: number) => void }) {
  const totalPages = Math.ceil(total / perPage);
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-between mt-4">
      <span className="text-xs text-slate-500">Pagina {page} de {totalPages}</span>
      <div className="flex gap-1">
        <button onClick={() => onPage(page - 1)} disabled={page <= 1}
          className="px-3 py-1.5 border border-slate-300 rounded-lg text-sm disabled:opacity-30 hover:bg-slate-50">Anterior</button>
        <button onClick={() => onPage(page + 1)} disabled={page >= totalPages}
          className="px-3 py-1.5 border border-slate-300 rounded-lg text-sm disabled:opacity-30 hover:bg-slate-50">Siguiente</button>
      </div>
    </div>
  );
}
