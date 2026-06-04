import { useState } from 'react';
import { api } from '../../api/client';

interface TrackingEntry {
  timestamp: string;
  queue_id: string;
  from: string;
  to: string;
  status: string;
  dsn: string;
}

export function MessageTracking() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<TrackingEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const search = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const data = await api.get<TrackingEntry[]>(`/admin/message-tracking?q=${encodeURIComponent(query)}`);
      setResults(data);
    } catch { setResults([]); }
    setLoading(false);
  };

  const statusColor = (s: string) => {
    if (s === 'sent') return 'bg-green-100 text-green-700';
    if (s === 'deferred') return 'bg-yellow-100 text-yellow-700';
    if (s === 'bounced') return 'bg-red-100 text-red-700';
    return 'bg-slate-100 text-slate-600';
  };

  return (
    <div className="p-6 max-w-5xl">
      <h2 className="text-xl font-semibold text-slate-800 mb-2">Seguimiento de Mensajes</h2>
      <p className="text-sm text-slate-500 mb-6">Busca por dirección de correo, dominio o ID de cola para rastrear el estado de entrega.</p>

      <div className="flex gap-3 mb-6">
        <input value={query} onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && search()}
          placeholder="usuario@ejemplo.com o dominio.com"
          className="flex-1 px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-orange-300 focus:border-orange-400 outline-none" />
        <button onClick={search} disabled={loading}
          className="px-5 py-2.5 bg-orange-500 text-white rounded-lg text-sm font-medium hover:bg-orange-600 disabled:opacity-50">
          {loading ? 'Buscando...' : 'Buscar'}
        </button>
      </div>

      {searched && results.length === 0 && !loading && (
        <div className="text-center py-12 text-slate-400">
          <svg className="w-12 h-12 mx-auto mb-3 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <p>No se encontraron mensajes para "{query}"</p>
        </div>
      )}

      {results.length > 0 && (
        <div className="border border-slate-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Fecha/Hora</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">De</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Para</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Estado</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Queue ID</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2.5 text-slate-600 whitespace-nowrap">{r.timestamp}</td>
                  <td className="px-4 py-2.5 text-slate-800 truncate max-w-[200px]">{r.from}</td>
                  <td className="px-4 py-2.5 text-slate-800 truncate max-w-[200px]">{r.to}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs px-2 py-1 rounded-full font-medium ${statusColor(r.status)}`}>{r.status}</span>
                  </td>
                  <td className="px-4 py-2.5 text-slate-400 font-mono text-xs">{r.queue_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
