import { useState } from 'react';
import { api } from '../../api/client';

interface FreeSlot {
  start: string;
  end: string;
}

interface BusyPeriod {
  start: string;
  end: string;
}

interface SchedulingResult {
  date: string;
  attendees: string[];
  duration_minutes: number;
  busy_periods: BusyPeriod[];
  free_slots: FreeSlot[];
}

interface Props {
  onSelectSlot?: (start: string, end: string) => void;
  onClose: () => void;
}

export function SchedulingAssistant({ onSelectSlot, onClose }: Props) {
  const [attendees, setAttendees] = useState('');
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [duration, setDuration] = useState(30);
  const [result, setResult] = useState<SchedulingResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const search = async () => {
    if (!attendees.trim()) return;
    setLoading(true); setError('');
    try {
      const data = await api.get<SchedulingResult>(
        `/calendar/scheduling-assistant?attendees=${encodeURIComponent(attendees)}&date=${date}&duration=${duration}`
      );
      setResult(data);
    } catch (e: any) { setError(e.message); }
    setLoading(false);
  };

  const fmtTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl w-[520px] max-h-[80vh] overflow-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-800">Asistente de programación</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl">×</button>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Asistentes (emails separados por coma)</label>
            <input value={attendees} onChange={e => setAttendees(e.target.value)}
              placeholder="ana@ejemplo.com, carlos@ejemplo.com"
              className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-300 outline-none" />
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-sm font-medium text-slate-700 mb-1">Fecha</label>
              <input type="date" value={date} onChange={e => setDate(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-300 outline-none" />
            </div>
            <div className="w-28">
              <label className="block text-sm font-medium text-slate-700 mb-1">Duración</label>
              <select value={duration} onChange={e => setDuration(+e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-300 outline-none">
                <option value={15}>15 min</option>
                <option value={30}>30 min</option>
                <option value={45}>45 min</option>
                <option value={60}>1 hora</option>
                <option value={90}>1.5 horas</option>
                <option value={120}>2 horas</option>
              </select>
            </div>
          </div>
          <button onClick={search} disabled={loading || !attendees}
            className="w-full py-2.5 bg-[#0078d4] text-white rounded text-sm font-medium hover:bg-[#106ebe] disabled:opacity-50">
            {loading ? 'Buscando disponibilidad...' : 'Buscar horarios disponibles'}
          </button>
        </div>

        {error && <div className="mx-6 mb-4 p-3 bg-red-50 text-red-700 rounded text-sm">{error}</div>}

        {result && (
          <div className="px-6 pb-6">
            {result.busy_periods.length > 0 && (
              <div className="mb-4">
                <h4 className="text-sm font-medium text-slate-600 mb-2">Horarios ocupados</h4>
                <div className="flex flex-wrap gap-2">
                  {result.busy_periods.map((b, i) => (
                    <span key={i} className="text-xs px-2 py-1 bg-red-50 text-red-600 rounded">
                      {fmtTime(b.start)} - {fmtTime(b.end)}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <h4 className="text-sm font-medium text-slate-600 mb-2">
              Horarios disponibles ({result.free_slots.length})
            </h4>
            {result.free_slots.length === 0 ? (
              <p className="text-sm text-slate-400">No hay horarios disponibles este día</p>
            ) : (
              <div className="grid grid-cols-3 gap-2 max-h-48 overflow-auto">
                {result.free_slots.map((slot, i) => (
                  <button key={i}
                    onClick={() => { onSelectSlot?.(slot.start, slot.end); onClose(); }}
                    className="px-3 py-2 text-sm bg-green-50 text-green-700 rounded hover:bg-green-100 border border-green-200 transition-colors">
                    {fmtTime(slot.start)} - {fmtTime(slot.end)}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
