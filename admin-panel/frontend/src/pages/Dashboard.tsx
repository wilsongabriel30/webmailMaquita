import { useEffect, useState } from "react";
import { api } from "../api/client";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area } from "recharts";

interface DashData {
  stats: { domains: number; mailboxes: number; active_mailboxes: number; aliases: number; total_quota: number };
  services: Record<string, string>;
  rspamd: { scanned?: number; actions?: Record<string, number>; uptime?: number };
  active_connections: number;
  connections: { username: string; service: string; connections: number }[];
}

const COLORS = ["#107c10", "#0078d4", "#d13438", "#5c2d91", "#ffb900", "#605e5c"];

export function Dashboard() {
  const [data, setData] = useState<DashData | null>(null);
  const [storage, setStorage] = useState<any>(null);
  const [volume, setVolume] = useState<any>(null);

  useEffect(() => {
    api.get<DashData>("/dashboard").then(setData).catch(() => {});
    api.get("/dashboard/storage").then((d: any) => setStorage(d || {})).catch(() => setStorage({}));
    api.get("/dashboard/mail-volume").then((d: any) => setVolume(d || {})).catch(() => setVolume({}));
  }, []);

  if (!data) return <div className="p-8 flex items-center justify-center h-full"><div className="animate-spin w-8 h-8 border-2 border-ms-blue border-t-transparent rounded-full" /></div>;

  const cards = [
    { label: "Dominios", value: data.stats.domains, color: "text-ms-blue", bg: "bg-ms-blue-lighter" },
    { label: "Buzones", value: data.stats.mailboxes, color: "text-ms-purple", bg: "bg-purple-50" },
    { label: "Activos", value: data.stats.active_mailboxes, color: "text-ms-green", bg: "bg-green-50" },
    { label: "Alias", value: data.stats.aliases, color: "text-ms-orange", bg: "bg-orange-50" },
    { label: "Conexiones", value: data.active_connections, color: "text-ms-blue", bg: "bg-blue-50" },
    { label: "Emails escaneados", value: data.rspamd?.scanned || 0, color: "text-ms-gray-130", bg: "bg-ms-gray-20" },
  ];

  const spamActions = data.rspamd?.actions || {};
  const pieData = Object.entries(spamActions).filter(([, v]) => (v as number) > 0).map(([k, v]) => ({ name: k, value: v as number }));

  const svcColors: Record<string, string> = {
    active: "bg-ms-green", inactive: "bg-ms-red", failed: "bg-ms-red", unknown: "bg-ms-gray-60",
  };

  const storageData: any[] = storage ? Object.entries(storage).map(([domain, info]: [string, any]) => ({
    domain, size_gb: +(info.total_bytes / 1073741824).toFixed(2), users: Object.keys(info.users).length,
  })) : [];

  const volumeData = volume?.hours ? Object.entries(volume.hours)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-24)
    .map(([hour, d]: [string, any]) => ({ hour: hour.slice(-5), ...d })) : [];

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130">Dashboard</h1>
        <span className="text-xs text-ms-gray-60">Última actualización: {new Date().toLocaleTimeString()}</span>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {cards.map((c) => (
          <div key={c.label} className={`${c.bg} rounded border border-ms-gray-30 p-4`}>
            <p className="text-[11px] font-medium text-ms-gray-90 uppercase">{c.label}</p>
            <p className={`text-2xl font-bold mt-1 ${c.color}`}>{c.value.toLocaleString()}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Services */}
        <div className="bg-white rounded border border-ms-gray-30 p-5">
          <h2 className="text-sm font-semibold text-ms-gray-130 mb-3">Servicios</h2>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(data.services).map(([name, status]) => (
              <div key={name} className="flex items-center justify-between p-2 rounded bg-ms-gray-10 border border-ms-gray-30">
                <span className="text-xs text-ms-gray-130 font-medium capitalize">{name.replace("-server", "").replace("-daemon", "")}</span>
                <div className="flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${svcColors[status as string] || svcColors.unknown}`} />
                  <span className="text-[10px] text-ms-gray-90">{status as string}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Rspamd Actions pie */}
        <div className="bg-white rounded border border-ms-gray-30 p-5">
          <h2 className="text-sm font-semibold text-ms-gray-130 mb-3">Rspamd - Acciones</h2>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart margin={{ top: 20, right: 20, bottom: 5, left: 20 }}>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={40} outerRadius={70} paddingAngle={2} dataKey="value" label={({ name, value }: any) => `${name}: ${value}`} labelLine={true}>
                  {pieData.map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : <p className="text-ms-gray-60 text-sm">Sin datos</p>}
        </div>

        {/* Mail volume chart */}
        <div className="bg-white rounded border border-ms-gray-30 p-5">
          <h2 className="text-sm font-semibold text-ms-gray-130 mb-3">Volumen de correo (24h)</h2>
          {volumeData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={volumeData}>
                <XAxis dataKey="hour" tick={{ fontSize: 10 }} interval={Math.max(0, Math.floor(volumeData.length / 6) - 1)} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Area type="monotone" dataKey="ham" stackId="1" stroke="#107c10" fill="#107c10" fillOpacity={0.3} name="Legítimo" />
                <Area type="monotone" dataKey="spam" stackId="1" stroke="#d13438" fill="#d13438" fillOpacity={0.3} name="Spam" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex flex-col items-center justify-center h-[200px] text-ms-gray-60">
              <svg className="w-8 h-8 mb-2 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z" /></svg>
              <p className="text-sm">Sin datos de volumen disponibles</p>
              <p className="text-xs mt-1">Los datos se generan al procesar correos</p>
            </div>
          )}
        </div>

        {/* Storage */}
        <div className="bg-white rounded border border-ms-gray-30 p-5">
          <h2 className="text-sm font-semibold text-ms-gray-130 mb-3">Almacenamiento por dominio</h2>
          {storageData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={storageData}>
                <XAxis dataKey="domain" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip formatter={(v: any) => `${v} GB`} />
                <Bar dataKey="size_gb" fill="#0078d4" radius={[4, 4, 0, 0]} name="GB" />
              </BarChart>
            </ResponsiveContainer>
          ) : storage === null ? (
            <div className="flex items-center justify-center h-[200px]">
              <div className="animate-spin w-5 h-5 border-2 border-ms-blue border-t-transparent rounded-full" />
              <span className="ml-2 text-sm text-ms-gray-60">Calculando almacenamiento...</span>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-[200px] text-ms-gray-60">
              <p className="text-sm">No se pudo obtener datos de almacenamiento</p>
              <button onClick={() => api.get("/dashboard/storage").then((d: any) => setStorage(d)).catch(() => setStorage({}))} className="mt-2 text-xs text-ms-blue hover:underline">Reintentar</button>
            </div>
          )}
        </div>

        {/* Active connections */}
        <div className="bg-white rounded border border-ms-gray-30 p-5 lg:col-span-2">
          <h2 className="text-sm font-semibold text-ms-gray-130 mb-3">Conexiones activas ({data.active_connections})</h2>
          {data.connections.length > 0 ? (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {data.connections.map((c: any, i: number) => (
                <div key={i} className="flex items-center justify-between p-2 bg-ms-gray-10 rounded border border-ms-gray-30 text-xs">
                  <span className="font-medium text-ms-gray-130 truncate">{c.username}</span>
                  <span className="px-1.5 py-0.5 bg-ms-blue-light text-ms-blue rounded text-[10px] shrink-0 ml-1">{c.service} ({c.connections})</span>
                </div>
              ))}
            </div>
          ) : <p className="text-ms-gray-60 text-sm">Sin conexiones activas</p>}
        </div>
      </div>
    </div>
  );
}
