import { useEffect, useState } from 'react';
import { api } from '../../api/client';

interface DashboardData {
  stats: {
    domains: number;
    mailboxes: number;
    active_mailboxes: number;
    aliases: number;
  };
  services: Record<string, string>;
}

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<DashboardData>('/admin/dashboard')
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-orange-600 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!data) {
    return <div className="p-8 text-red-600">Error cargando dashboard</div>;
  }

  const statCards = [
    { label: 'Dominios', value: data.stats.domains, color: 'bg-blue-50 text-blue-700' },
    { label: 'Buzones', value: data.stats.mailboxes, color: 'bg-green-50 text-green-700' },
    { label: 'Activos', value: data.stats.active_mailboxes, color: 'bg-emerald-50 text-emerald-700' },
    { label: 'Aliases', value: data.stats.aliases, color: 'bg-purple-50 text-purple-700' },
  ];

  const serviceColors: Record<string, string> = {
    active: 'bg-green-100 text-green-800',
    inactive: 'bg-red-100 text-red-800',
    failed: 'bg-red-100 text-red-800',
    unknown: 'bg-slate-100 text-slate-600',
  };

  return (
    <div className="p-8 max-w-5xl">
      <h1 className="text-2xl font-bold text-slate-800 mb-6">Dashboard</h1>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {statCards.map((card) => (
          <div key={card.label} className={`rounded-xl p-5 ${card.color}`}>
            <p className="text-sm font-medium opacity-75">{card.label}</p>
            <p className="text-3xl font-bold mt-1">{card.value}</p>
          </div>
        ))}
      </div>

      {/* Services */}
      <h2 className="text-lg font-semibold text-slate-800 mb-3">Estado de Servicios</h2>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {Object.entries(data.services).map(([name, status]) => (
          <div key={name} className="border border-slate-200 rounded-lg p-4 flex items-center justify-between">
            <span className="font-medium text-slate-700 capitalize">{name.replace('-server', '')}</span>
            <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${serviceColors[status] || serviceColors.unknown}`}>
              {status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
