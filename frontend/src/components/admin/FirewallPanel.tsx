import { useEffect, useState, useCallback } from 'react';
import { api } from '../../api/client';

// ── Tipos ───────────────────────────────────────────────────

interface DashboardData {
  total_blocked_permanent: number;
  total_banned_fail2ban: number;
  attacks_24h: number;
  active_jails: number;
  jail_stats: Record<string, { currently_banned: number; total_banned: number }>;
  top_attacking_ips: { ip: string; count: number; type: string }[];
}

interface AttackEntry {
  ip: string;
  count: number;
  type: string;
  username_attempted: string;
  timestamp: string;
  events: { timestamp: string; type: string; username_attempted: string }[];
}

interface BannedEntry {
  ip: string;
  jail: string;
  status: string;
}

interface BlacklistEntry {
  ip: string;
  reason: string;
  date: string;
}

interface JailConfig {
  name: string;
  bantime: number | null;
  maxretry: number | null;
  findtime: number | null;
  bantime_human: string;
  findtime_human: string;
}

type Tab = 'dashboard' | 'attacks' | 'banned' | 'blacklist' | 'config';

// ── Componente Principal ────────────────────────────────────

export function FirewallPanel() {
  const [tab, setTab] = useState<Tab>('dashboard');

  const tabs: { key: Tab; label: string; icon: string }[] = [
    {
      key: 'dashboard',
      label: 'Panel de Ataques',
      icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
    },
    {
      key: 'attacks',
      label: 'Ataques en Tiempo Real',
      icon: 'M13 10V3L4 14h7v7l9-11h-7z',
    },
    {
      key: 'banned',
      label: 'IPs Baneadas (Fail2ban)',
      icon: 'M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636',
    },
    {
      key: 'blacklist',
      label: 'Blacklist Permanente',
      icon: 'M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z',
    },
    {
      key: 'config',
      label: 'Configuracion Fail2ban',
      icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z',
    },
  ];

  return (
    <div className="p-8 max-w-7xl">
      <h1 className="text-2xl font-bold text-slate-800 mb-2">Firewall y Proteccion</h1>
      <p className="text-sm text-slate-500 mb-6">
        Gestiona fail2ban, blacklist permanente y monitorea ataques al servidor de correo
      </p>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-slate-200 overflow-x-auto">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
              tab === t.key
                ? 'border-orange-500 text-orange-700'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={t.icon} />
            </svg>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'dashboard' && <DashboardTab />}
      {tab === 'attacks' && <AttacksTab />}
      {tab === 'banned' && <BannedTab />}
      {tab === 'blacklist' && <BlacklistTab />}
      {tab === 'config' && <ConfigTab />}
    </div>
  );
}

// ── Spinner ─────────────────────────────────────────────────

function Spinner() {
  return (
    <div className="p-8 flex items-center justify-center">
      <div className="animate-spin w-8 h-8 border-2 border-orange-600 border-t-transparent rounded-full" />
    </div>
  );
}

function ErrorMsg({ msg }: { msg: string }) {
  return (
    <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
      <span className="font-semibold">Error:</span> {msg}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// TAB 1: Panel de Ataques (Dashboard)
// ══════════════════════════════════════════════════════════════

function DashboardTab() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError('');
    api
      .get<DashboardData>('/admin/firewall/dashboard')
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, [load]);

  const handleBlock = async (ip: string) => {
    if (!window.confirm(`Bloquear permanentemente la IP ${ip}?`)) return;
    setActionLoading(ip);
    try {
      await api.post('/admin/firewall/blacklist', { ip, reason: 'Bloqueado desde panel de ataques' });
      load();
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  if (loading && !data) return <Spinner />;
  if (error && !data) return <ErrorMsg msg={error} />;
  if (!data) return null;

  const cards = [
    {
      label: 'IPs Bloqueadas Permanentes',
      value: data.total_blocked_permanent,
      color: 'bg-blue-50 text-blue-700 border-blue-200',
      iconColor: 'text-blue-500',
      icon: 'M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z',
    },
    {
      label: 'IPs Baneadas (fail2ban)',
      value: data.total_banned_fail2ban,
      color: 'bg-orange-50 text-orange-700 border-orange-200',
      iconColor: 'text-orange-500',
      icon: 'M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636',
    },
    {
      label: 'Ataques (24h)',
      value: data.attacks_24h,
      color: 'bg-red-50 text-red-700 border-red-200',
      iconColor: 'text-red-500',
      icon: 'M13 10V3L4 14h7v7l9-11h-7z',
    },
    {
      label: 'Jails Activos',
      value: data.active_jails,
      color: 'bg-green-50 text-green-700 border-green-200',
      iconColor: 'text-green-500',
      icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((c) => (
          <div key={c.label} className={`rounded-xl border p-5 ${c.color}`}>
            <div className="flex items-center justify-between mb-3">
              <svg className={`w-6 h-6 ${c.iconColor}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={c.icon} />
              </svg>
              <span className="text-3xl font-bold">{c.value.toLocaleString()}</span>
            </div>
            <p className="text-xs font-medium opacity-80">{c.label}</p>
          </div>
        ))}
      </div>

      {/* Jail stats */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Estado de Jails</h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {Object.entries(data.jail_stats).map(([jail, stats]) => (
            <div key={jail} className="bg-slate-50 rounded-lg p-3 text-center">
              <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-700 mb-2">
                {jail}
              </span>
              <p className="text-xl font-bold text-slate-800">{stats.currently_banned}</p>
              <p className="text-xs text-slate-500">baneados ahora</p>
              <p className="text-xs text-slate-400 mt-1">Total historico: {stats.total_banned}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Top attacking IPs */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">Top IPs Atacantes (24h)</h3>
          <button
            onClick={load}
            className="text-xs text-orange-600 hover:text-orange-800 flex items-center gap-1"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refrescar
          </button>
        </div>
        {data.top_attacking_ips.length === 0 ? (
          <p className="p-5 text-sm text-slate-400 text-center">Sin ataques registrados en las ultimas 24h</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left px-5 py-2.5 font-medium">IP</th>
                <th className="text-left px-5 py-2.5 font-medium">Intentos</th>
                <th className="text-left px-5 py-2.5 font-medium">Tipo</th>
                <th className="text-right px-5 py-2.5 font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.top_attacking_ips.map((row) => (
                <tr key={row.ip} className="hover:bg-slate-50">
                  <td className="px-5 py-3 font-mono text-xs">{row.ip}</td>
                  <td className="px-5 py-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${
                        row.count > 50
                          ? 'bg-red-100 text-red-700'
                          : row.count > 10
                          ? 'bg-orange-100 text-orange-700'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {row.count}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-xs text-slate-500">{_typeLabel(row.type)}</td>
                  <td className="px-5 py-3 text-right">
                    <button
                      onClick={() => handleBlock(row.ip)}
                      disabled={actionLoading === row.ip}
                      className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50 transition-colors"
                    >
                      {actionLoading === row.ip ? (
                        <span className="animate-spin w-3 h-3 border border-white border-t-transparent rounded-full" />
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                        </svg>
                      )}
                      Bloquear Permanente
                    </button>
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

// ══════════════════════════════════════════════════════════════
// TAB 2: Ataques en Tiempo Real
// ══════════════════════════════════════════════════════════════

function AttacksTab() {
  const [attacks, setAttacks] = useState<AttackEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [hours, setHours] = useState(24);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError('');
    api
      .get<{ attacks: AttackEntry[] }>(`/admin/firewall/attacks?hours=${hours}&limit=100`)
      .then((d) => setAttacks(d.attacks))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [hours]);

  useEffect(() => {
    load();
  }, [load]);

  const handleBlock = async (ip: string) => {
    if (!window.confirm(`Bloquear permanentemente la IP ${ip}?`)) return;
    setActionLoading(ip);
    try {
      await api.post('/admin/firewall/blacklist', { ip, reason: `Bloqueado desde ataques tiempo real (${hours}h)` });
      load();
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const hourOptions = [6, 12, 24, 48];

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex gap-2">
          {hourOptions.map((h) => (
            <button
              key={h}
              onClick={() => setHours(h)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                hours === h
                  ? 'bg-orange-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {h}h
            </button>
          ))}
        </div>
        <button
          onClick={load}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-orange-700 bg-orange-50 hover:bg-orange-100 rounded-lg transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refrescar
        </button>
      </div>

      {loading && !attacks.length ? (
        <Spinner />
      ) : error ? (
        <ErrorMsg msg={error} />
      ) : attacks.length === 0 ? (
        <div className="text-center py-12 text-slate-400">
          <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
          <p className="text-sm">Sin ataques en las ultimas {hours} horas</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left px-5 py-2.5 font-medium">Hora</th>
                <th className="text-left px-5 py-2.5 font-medium">IP</th>
                <th className="text-left px-5 py-2.5 font-medium">Tipo de Ataque</th>
                <th className="text-left px-5 py-2.5 font-medium">Usuario Intentado</th>
                <th className="text-left px-5 py-2.5 font-medium">Intentos</th>
                <th className="text-right px-5 py-2.5 font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {attacks.map((row) => (
                <tr
                  key={row.ip}
                  className={
                    row.count > 10
                      ? 'bg-red-50 hover:bg-red-100'
                      : row.count > 5
                      ? 'bg-orange-50 hover:bg-orange-100'
                      : 'hover:bg-slate-50'
                  }
                >
                  <td className="px-5 py-3 text-xs text-slate-500 whitespace-nowrap">{row.timestamp}</td>
                  <td className="px-5 py-3 font-mono text-xs">{row.ip}</td>
                  <td className="px-5 py-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                        row.type === 'sasl_fail'
                          ? 'bg-red-100 text-red-700'
                          : row.type === 'auth_fail'
                          ? 'bg-orange-100 text-orange-700'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {_typeLabel(row.type)}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-xs text-slate-600 font-mono">
                    {row.username_attempted || '-'}
                  </td>
                  <td className="px-5 py-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-bold ${
                        row.count > 50
                          ? 'bg-red-600 text-white'
                          : row.count > 10
                          ? 'bg-red-100 text-red-700'
                          : row.count > 5
                          ? 'bg-orange-100 text-orange-700'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {row.count}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right">
                    <button
                      onClick={() => handleBlock(row.ip)}
                      disabled={actionLoading === row.ip}
                      className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50 transition-colors"
                    >
                      {actionLoading === row.ip ? (
                        <span className="animate-spin w-3 h-3 border border-white border-t-transparent rounded-full" />
                      ) : null}
                      Bloquear
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// TAB 3: IPs Baneadas (Fail2ban)
// ══════════════════════════════════════════════════════════════

function BannedTab() {
  const [banned, setBanned] = useState<BannedEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError('');
    api
      .get<{ banned: BannedEntry[] }>('/admin/firewall/banned')
      .then((d) => setBanned(d.banned))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleMakePermanent = async (ip: string) => {
    if (!window.confirm(`Promover la IP ${ip} a blacklist permanente?`)) return;
    setActionLoading(ip);
    try {
      await api.post('/admin/firewall/ban-to-permanent', { ip });
      load();
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const jailColors: Record<string, string> = {
    'postfix-sasl': 'bg-red-100 text-red-700',
    'dovecot': 'bg-blue-100 text-blue-700',
    'postfix-rbl': 'bg-purple-100 text-purple-700',
    'recidive': 'bg-orange-100 text-orange-700',
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorMsg msg={error} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">
          {banned.length} IP{banned.length !== 1 ? 's' : ''} baneada{banned.length !== 1 ? 's' : ''} actualmente
        </p>
        <button
          onClick={load}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-orange-700 bg-orange-50 hover:bg-orange-100 rounded-lg transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refrescar
        </button>
      </div>

      {banned.length === 0 ? (
        <div className="text-center py-12 text-slate-400">
          <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
          <p className="text-sm">No hay IPs baneadas en este momento</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left px-5 py-2.5 font-medium">IP</th>
                <th className="text-left px-5 py-2.5 font-medium">Jail</th>
                <th className="text-left px-5 py-2.5 font-medium">Estado</th>
                <th className="text-right px-5 py-2.5 font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {banned.map((row, i) => (
                <tr key={`${row.ip}-${row.jail}-${i}`} className="hover:bg-slate-50">
                  <td className="px-5 py-3 font-mono text-xs">{row.ip}</td>
                  <td className="px-5 py-3">
                    <span
                      className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        jailColors[row.jail] || 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {row.jail}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <span className="inline-flex items-center gap-1 text-xs">
                      <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                      <span className="text-red-600 font-medium">Baneado</span>
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right">
                    <button
                      onClick={() => handleMakePermanent(row.ip)}
                      disabled={actionLoading === row.ip}
                      className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-orange-600 hover:bg-orange-700 rounded-lg disabled:opacity-50 transition-colors"
                    >
                      {actionLoading === row.ip ? (
                        <span className="animate-spin w-3 h-3 border border-white border-t-transparent rounded-full" />
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                        </svg>
                      )}
                      Hacer Permanente
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// TAB 4: Blacklist Permanente
// ══════════════════════════════════════════════════════════════

function BlacklistTab() {
  const [entries, setEntries] = useState<BlacklistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [newIp, setNewIp] = useState('');
  const [newReason, setNewReason] = useState('');
  const [addLoading, setAddLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError('');
    api
      .get<{ blacklist: BlacklistEntry[] }>('/admin/firewall/blacklist')
      .then((d) => setEntries(d.blacklist))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = entries.filter(
    (e) =>
      e.ip.toLowerCase().includes(search.toLowerCase()) ||
      e.reason.toLowerCase().includes(search.toLowerCase())
  );

  const handleAdd = async () => {
    if (!newIp.trim()) return;
    setAddLoading(true);
    try {
      await api.post('/admin/firewall/blacklist', {
        ip: newIp.trim(),
        reason: newReason.trim() || 'Agregado manualmente',
      });
      setNewIp('');
      setNewReason('');
      setShowAdd(false);
      load();
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    } finally {
      setAddLoading(false);
    }
  };

  const handleDelete = async (ip: string) => {
    if (!window.confirm(`Eliminar la IP ${ip} de la blacklist permanente? Esta accion permitira que esta IP vuelva a conectarse.`)) return;
    setActionLoading(ip);
    try {
      await api.del(`/admin/firewall/blacklist/${encodeURIComponent(ip)}`);
      load();
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorMsg msg={error} />;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500">{entries.length} IPs en la blacklist</span>
          <div className="relative">
            <svg
              className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar IP o motivo..."
              className="pl-8 pr-3 py-1.5 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-300 w-64"
            />
          </div>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-orange-600 hover:bg-orange-700 rounded-lg transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Agregar IP
        </button>
      </div>

      {/* Add form */}
      {showAdd && (
        <div className="bg-orange-50 border border-orange-200 rounded-xl p-5 space-y-3">
          <h4 className="text-sm font-semibold text-orange-800">Agregar nueva IP a la blacklist</h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">IP o CIDR</label>
              <input
                type="text"
                value={newIp}
                onChange={(e) => setNewIp(e.target.value)}
                placeholder="ej: 192.168.1.100 o 10.0.0.0/24"
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Motivo</label>
              <input
                type="text"
                value={newReason}
                onChange={(e) => setNewReason(e.target.value)}
                placeholder="ej: Spam repetido, ataque brute force..."
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
            </div>
          </div>
          <div className="flex gap-2 pt-1">
            <button
              onClick={handleAdd}
              disabled={addLoading || !newIp.trim()}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-orange-600 hover:bg-orange-700 rounded-lg disabled:opacity-50 transition-colors"
            >
              {addLoading && <span className="animate-spin w-3 h-3 border border-white border-t-transparent rounded-full" />}
              Agregar
            </button>
            <button
              onClick={() => { setShowAdd(false); setNewIp(''); setNewReason(''); }}
              className="px-4 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg transition-colors"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="text-center py-12 text-slate-400">
          <p className="text-sm">{search ? 'Sin resultados para esa busqueda' : 'La blacklist esta vacia'}</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left px-5 py-2.5 font-medium">IP / CIDR</th>
                <th className="text-left px-5 py-2.5 font-medium">Motivo</th>
                <th className="text-left px-5 py-2.5 font-medium">Fecha</th>
                <th className="text-right px-5 py-2.5 font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((row, i) => (
                <tr key={`${row.ip}-${i}`} className="hover:bg-slate-50">
                  <td className="px-5 py-3 font-mono text-xs">
                    <span className="inline-flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-red-500" />
                      {row.ip}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-xs text-slate-600 max-w-xs truncate">{row.reason || '-'}</td>
                  <td className="px-5 py-3 text-xs text-slate-400">{row.date || '-'}</td>
                  <td className="px-5 py-3 text-right">
                    <button
                      onClick={() => handleDelete(row.ip)}
                      disabled={actionLoading === row.ip}
                      className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg disabled:opacity-50 transition-colors"
                    >
                      {actionLoading === row.ip ? (
                        <span className="animate-spin w-3 h-3 border border-red-600 border-t-transparent rounded-full" />
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      )}
                      Eliminar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// TAB 5: Configuracion Fail2ban
// ══════════════════════════════════════════════════════════════

function ConfigTab() {
  const [jails, setJails] = useState<Record<string, JailConfig>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api
      .get<{ jails: Record<string, JailConfig> }>('/admin/firewall/fail2ban/config')
      .then((d) => setJails(d.jails))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner />;
  if (error) return <ErrorMsg msg={error} />;

  const jailColors: Record<string, { bg: string; border: string; text: string; icon: string }> = {
    'postfix-sasl': { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700', icon: 'text-red-500' },
    'dovecot': { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700', icon: 'text-blue-500' },
    'postfix-rbl': { bg: 'bg-purple-50', border: 'border-purple-200', text: 'text-purple-700', icon: 'text-purple-500' },
    'recidive': { bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-700', icon: 'text-orange-500' },
  };

  const defaultColor = { bg: 'bg-slate-50', border: 'border-slate-200', text: 'text-slate-700', icon: 'text-slate-500' };

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">Configuracion actual de los jails de fail2ban (solo lectura)</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Object.values(jails).map((jail) => {
          const c = jailColors[jail.name] || defaultColor;
          return (
            <div key={jail.name} className={`rounded-xl border ${c.border} ${c.bg} p-5`}>
              <div className="flex items-center gap-2 mb-4">
                <svg className={`w-5 h-5 ${c.icon}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                  />
                </svg>
                <h3 className={`text-base font-bold ${c.text}`}>{jail.name}</h3>
              </div>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span className="text-xs text-slate-600">Tiempo de baneo</span>
                  </div>
                  <span className={`text-sm font-semibold ${c.text}`}>{jail.bantime_human}</span>
                </div>
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14" />
                    </svg>
                    <span className="text-xs text-slate-600">Intentos maximos</span>
                  </div>
                  <span className={`text-sm font-semibold ${c.text}`}>{jail.maxretry ?? 'N/A'}</span>
                </div>
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                    <span className="text-xs text-slate-600">Ventana de deteccion</span>
                  </div>
                  <span className={`text-sm font-semibold ${c.text}`}>{jail.findtime_human}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Utilidades ───────────────────────────────────────────────

function _typeLabel(type: string): string {
  switch (type) {
    case 'sasl_fail':
      return 'SASL Fallido';
    case 'auth_fail':
      return 'Auth Fallido';
    case 'brute_force':
      return 'Fuerza Bruta';
    default:
      return type;
  }
}
