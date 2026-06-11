import { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { showToast } from './Toast';

interface Rem {
  id: string;
  message: string;
  kind?: string;
  entityId?: string;
}

/** Tarjetas de recordatorio persistentes (abajo a la derecha), estilo Outlook.
 *  Se alimentan del evento global 'show-reminder' (WebSocket type=reminder). */
export function ReminderPopup() {
  const [items, setItems] = useState<Rem[]>([]);

  useEffect(() => {
    const h = (e: Event) => {
      const d = (e as CustomEvent).detail || {};
      const id = d.tag || `rem-${Math.random().toString(36).slice(2)}`;
      setItems(prev => prev.some(p => p.id === id)
        ? prev
        : [...prev, { id, message: d.message || 'Recordatorio', kind: d.kind, entityId: d.entity_id }]);
    };
    window.addEventListener('show-reminder', h);
    return () => window.removeEventListener('show-reminder', h);
  }, []);

  const dismiss = (id: string) => setItems(prev => prev.filter(p => p.id !== id));

  const snooze = async (r: Rem) => {
    try {
      const when = new Date(Date.now() + 10 * 60000).toISOString();
      await api.patch(`/tasks/tasks/${r.entityId}`, { reminder: when });
      showToast('Recordatorio pospuesto 10 minutos');
    } catch {
      showToast('No se pudo posponer el recordatorio');
    }
    dismiss(r.id);
  };

  if (items.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[300] flex flex-col gap-2 max-w-[340px]">
      {items.map(r => (
        <div key={r.id}
          className="bg-white dark:bg-[#2d2d2d] border border-[#edebe9] dark:border-[#444] rounded-lg shadow-xl p-3 flex flex-col gap-2 animate-[fadeIn_0.2s_ease]">
          <div className="flex items-start gap-2">
            <span className="text-[18px] leading-none mt-0.5">{r.kind === 'event' ? '📅' : '⏰'}</span>
            <span className="text-[13px] text-[#323130] dark:text-[#e0e0e0] flex-1">{r.message}</span>
            <button onClick={() => dismiss(r.id)} aria-label="Descartar recordatorio"
              className="text-[#605e5c] dark:text-[#999] hover:text-[#323130] dark:hover:text-[#e0e0e0] text-[16px] leading-none px-1">
              ×
            </button>
          </div>
          <div className="flex gap-2 justify-end">
            {r.kind === 'task' && r.entityId && (
              <button onClick={() => snooze(r)}
                className="px-3 py-1 text-[12px] rounded border border-[#0078d4] text-[#106ebe] hover:bg-[#deecf9] transition-colors">
                Posponer 10 min
              </button>
            )}
            <button onClick={() => dismiss(r.id)}
              className="px-3 py-1 text-[12px] rounded bg-[#0078d4] text-white hover:bg-[#106ebe] transition-colors">
              Descartar
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
