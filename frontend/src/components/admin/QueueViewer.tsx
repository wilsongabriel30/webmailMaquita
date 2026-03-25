import { useEffect, useState } from 'react';
import { api } from '../../api/client';

interface QueueEntry {
  queue_id: string;
  queue_name: string;
  arrival_time: number;
  message_size: number;
  sender: string;
  recipients: { address: string; delay_reason: string }[];
}

export function QueueViewer() {
  const [queue, setQueue] = useState<QueueEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.get<QueueEntry[]>('/admin/queue')
      .then(setQueue)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const action = async (actionName: string, queueId?: string) => {
    try {
      await api.post('/admin/queue/action', { action: actionName, queue_id: queueId });
      load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Error');
    }
  };

  const formatTime = (ts: number) => {
    if (!ts) return '-';
    return new Date(ts * 1000).toLocaleString('es-EC');
  };

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Cola de Correo</h1>
        <div className="flex gap-2">
          <button onClick={load} className="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 text-sm">
            Refrescar
          </button>
          <button onClick={() => action('flush_all')} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm">
            Reenviar todo
          </button>
          <button onClick={() => { if (confirm('Eliminar TODOS los mensajes en cola?')) action('delete_all'); }}
            className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm">
            Eliminar todo
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-8 text-slate-400">Cargando...</div>
      ) : queue.length === 0 ? (
        <div className="text-center py-12 text-slate-400">
          <p className="text-lg">Cola vacía</p>
          <p className="text-sm mt-1">No hay mensajes pendientes</p>
        </div>
      ) : (
        <div className="space-y-3">
          {queue.map((entry) => (
            <div key={entry.queue_id} className="border border-slate-200 rounded-lg p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="font-mono text-sm font-medium text-slate-800">{entry.queue_id}</span>
                    <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 rounded">{entry.queue_name}</span>
                    <span className="text-xs text-slate-400">{formatTime(entry.arrival_time)}</span>
                  </div>
                  <p className="text-sm text-slate-600">
                    <span className="font-medium">De:</span> {entry.sender || '(vacío)'}
                  </p>
                  {entry.recipients.map((r, i) => (
                    <div key={i} className="mt-1">
                      <p className="text-sm text-slate-600">
                        <span className="font-medium">Para:</span> {r.address}
                      </p>
                      {r.delay_reason && (
                        <p className="text-xs text-red-600 mt-0.5 ml-4">{r.delay_reason}</p>
                      )}
                    </div>
                  ))}
                </div>
                <div className="flex gap-1 ml-4 shrink-0">
                  <button onClick={() => action('flush', entry.queue_id)}
                    className="px-3 py-1.5 text-xs bg-blue-50 text-blue-700 rounded hover:bg-blue-100">
                    Reenviar
                  </button>
                  <button onClick={() => action('hold', entry.queue_id)}
                    className="px-3 py-1.5 text-xs bg-yellow-50 text-yellow-700 rounded hover:bg-yellow-100">
                    Hold
                  </button>
                  <button onClick={() => action('delete', entry.queue_id)}
                    className="px-3 py-1.5 text-xs bg-red-50 text-red-700 rounded hover:bg-red-100">
                    Eliminar
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="mt-4 text-sm text-slate-400">{queue.length} mensaje(s) en cola</p>
    </div>
  );
}
