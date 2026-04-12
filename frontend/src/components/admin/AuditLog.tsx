import { useEffect, useState } from 'react';
import { api } from '../../api/client';

interface AuditEntry {
  id: number;
  admin_user: string;
  action: string;
  target: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

interface AuditResponse {
  entries: AuditEntry[];
  total: number;
  page: number;
  per_page: number;
}

export function AuditLog() {
  const [data, setData] = useState<AuditResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [filterTarget, setFilterTarget] = useState('');

  const load = () => {
    setLoading(true);
    let url = `/admin/audit-log?page=${page}&per_page=30`;
    if (filterTarget) url += `&target=${encodeURIComponent(filterTarget)}`;
    api.get<AuditResponse>(url)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [page, filterTarget]);

  const totalPages = data ? Math.ceil(data.total / data.per_page) : 0;

  const actionLabels: Record<string, string> = {
    domain_create: 'Crear dominio',
    domain_update: 'Editar dominio',
    domain_delete: 'Eliminar dominio',
    mailbox_create: 'Crear buzón',
    mailbox_update: 'Editar buzón',
    mailbox_delete: 'Eliminar buzón',
    mailbox_toggle_active: 'Cambiar estado buzón',
    alias_create: 'Crear alias',
    alias_update: 'Editar alias',
    alias_delete: 'Eliminar alias',
    queue_flush: 'Reenviar mensaje',
    queue_delete: 'Eliminar de cola',
    queue_flush_all: 'Reenviar toda la cola',
    queue_delete_all: 'Vaciar cola',
    queue_hold: 'Retener mensaje',
    queue_release: 'Liberar mensaje',
  };

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Registro de Auditoría</h1>
        <div className="flex items-center gap-3">
          <input
            value={filterTarget}
            onChange={(e) => { setFilterTarget(e.target.value); setPage(1); }}
            placeholder="Buscar por objetivo..."
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm w-64"
          />
        </div>
      </div>

      {loading ? (
        <div className="text-center py-8 text-slate-400">Cargando...</div>
      ) : !data || data.entries.length === 0 ? (
        <div className="text-center py-12 text-slate-400">Sin entradas de auditoría</div>
      ) : (
        <>
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-200 text-left text-sm text-slate-500">
                <th className="pb-3 font-medium">Fecha</th>
                <th className="pb-3 font-medium">Administrador</th>
                <th className="pb-3 font-medium">Acción</th>
                <th className="pb-3 font-medium">Objetivo</th>
                <th className="pb-3 font-medium">IP</th>
              </tr>
            </thead>
            <tbody>
              {data.entries.map((entry) => (
                <tr key={entry.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-3 text-xs text-slate-500">
                    {new Date(entry.created_at).toLocaleString('es-EC')}
                  </td>
                  <td className="py-3 text-sm text-slate-700">{entry.admin_user}</td>
                  <td className="py-3 text-sm">
                    <span className="px-2 py-0.5 bg-orange-50 text-orange-700 rounded text-xs">
                      {actionLabels[entry.action] || entry.action}
                    </span>
                  </td>
                  <td className="py-3 text-sm text-slate-600">{entry.target || '-'}</td>
                  <td className="py-3 text-xs text-slate-400 font-mono">{entry.ip_address || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <p className="text-sm text-slate-400">{data.total} entradas</p>
              <div className="flex gap-1">
                <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
                  className="px-3 py-1 text-sm border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-50">
                  Anterior
                </button>
                <span className="px-3 py-1 text-sm text-slate-600">{page} / {totalPages}</span>
                <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages}
                  className="px-3 py-1 text-sm border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-50">
                  Siguiente
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
