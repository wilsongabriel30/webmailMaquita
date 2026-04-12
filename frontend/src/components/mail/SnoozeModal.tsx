import { useState, useEffect, useRef } from 'react';
import { useSnooze } from '../../hooks/useSnooze';

interface SnoozeModalProps {
  open: boolean;
  onClose: () => void;
  folder: string;
  uids: number[];
  onSnoozed?: () => void;
}

function addHours(date: Date, hours: number): Date {
  return new Date(date.getTime() + hours * 3600000);
}

function addDays(date: Date, days: number): Date {
  return new Date(date.getTime() + days * 86400000);
}

function tomorrowAt(hour: number): Date {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(hour, 0, 0, 0);
  return d;
}

function nextMondayAt(hour: number): Date {
  const d = new Date();
  const daysUntilMonday = ((8 - d.getDay()) % 7) || 7;
  d.setDate(d.getDate() + daysUntilMonday);
  d.setHours(hour, 0, 0, 0);
  return d;
}

function formatRelative(date: Date): string {
  const fmt = new Intl.DateTimeFormat('es', {
    weekday: 'short', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
  return fmt.format(date);
}

const SNOOZE_OPTIONS = [
  { label: 'En 1 hora', getDate: () => addHours(new Date(), 1) },
  { label: 'En 4 horas', getDate: () => addHours(new Date(), 4) },
  { label: 'Mañana a las 9:00', getDate: () => tomorrowAt(9) },
  { label: 'Próximo lunes 9:00', getDate: () => nextMondayAt(9) },
  { label: 'Próxima semana', getDate: () => addDays(new Date(), 7) },
];

const ICONS = [
  'M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z',
  'M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z',
  'M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z',
  'M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5',
  'M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5',
];

export function SnoozeModal({ open, onClose, folder, uids, onSnoozed }: SnoozeModalProps) {
  const [showCustom, setShowCustom] = useState(false);
  const [customDate, setCustomDate] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const modalRef = useRef<HTMLDivElement>(null);
  const { snoozeEmail } = useSnooze();

  useEffect(() => {
    if (open) {
      setShowCustom(false);
      setCustomDate('');
      setError('');
      modalRef.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (open && e.key === 'Escape') { e.preventDefault(); onClose(); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  const doSnooze = async (date: Date) => {
    setSaving(true);
    setError('');
    try {
      for (const uid of uids) {
        await snoozeEmail(folder, uid, date);
      }
      onSnoozed?.();
      onClose();
    } catch {
      setError('Error al posponer. Intenta de nuevo.');
    } finally {
      setSaving(false);
    }
  };

  const handleCustomSnooze = () => {
    if (!customDate) { setError('Selecciona una fecha y hora'); return; }
    const d = new Date(customDate);
    if (d <= new Date()) { setError('La fecha debe ser en el futuro'); return; }
    doSnooze(d);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 dark:bg-black/60" onClick={onClose}>
      <div
        ref={modalRef}
        tabIndex={-1}
        className="bg-white dark:bg-[#2d2d2d] rounded-lg shadow-xl w-full max-w-[360px] overflow-hidden outline-none border border-[#edebe9] dark:border-[#444]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#edebe9] dark:border-[#444]">
          <h3 className="text-[15px] font-semibold text-[#323130] dark:text-[#e0e0e0]">Posponer correo</h3>
          <button onClick={onClose} className="p-1 hover:bg-[#f3f2f1] dark:hover:bg-[#383838] rounded text-[#605e5c] dark:text-[#aaa]">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Options */}
        <div className="py-1">
          {SNOOZE_OPTIONS.map((opt, i) => {
            const date = opt.getDate();
            return (
              <button
                key={i}
                disabled={saving}
                onClick={() => doSnooze(date)}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-[#f3f2f1] dark:hover:bg-[#383838] disabled:opacity-50"
              >
                <svg className="w-4 h-4 text-[#605e5c] dark:text-[#aaa] flex-shrink-0" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d={ICONS[i]} />
                </svg>
                <span className="flex-1 text-[13px] text-[#323130] dark:text-[#e0e0e0]">{opt.label}</span>
                <span className="text-[11px] text-[#a19f9d] dark:text-[#777]">{formatRelative(date)}</span>
              </button>
            );
          })}

          {/* Custom option */}
          <button
            onClick={() => setShowCustom(!showCustom)}
            className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-[#f3f2f1] dark:hover:bg-[#383838] border-t border-[#edebe9] dark:border-[#444]"
          >
            <svg className="w-4 h-4 text-[#605e5c] dark:text-[#aaa]" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span className="flex-1 text-[13px] text-[#323130] dark:text-[#e0e0e0]">Personalizado...</span>
          </button>

          {showCustom && (
            <div className="px-4 py-3 border-t border-[#edebe9] dark:border-[#444] space-y-3">
              <input
                type="datetime-local"
                value={customDate}
                onChange={(e) => { setCustomDate(e.target.value); setError(''); }}
                min={new Date().toISOString().slice(0, 16)}
                className="w-full px-3 py-2 border border-[#edebe9] dark:border-[#444] rounded bg-white dark:bg-[#1e1e1e] text-[#323130] dark:text-[#e0e0e0] focus:border-[#0078d4] outline-none text-[14px]"
              />
              <button
                onClick={handleCustomSnooze}
                disabled={saving || !customDate}
                className="w-full px-4 py-2 bg-[#0078d4] text-white rounded hover:bg-[#106ebe] disabled:opacity-50 disabled:cursor-not-allowed text-[14px] font-medium"
              >
                {saving ? 'Posponiendo...' : 'Posponer'}
              </button>
            </div>
          )}
        </div>

        {error && (
          <div className="px-4 py-2 text-[12px] text-[#a4262c] dark:text-[#f1707b] border-t border-[#edebe9] dark:border-[#444]">
            {error}
          </div>
        )}

        {saving && (
          <div className="px-4 py-2 flex items-center gap-2 border-t border-[#edebe9] dark:border-[#444]">
            <div className="animate-spin rounded-full h-4 w-4 border-2 border-[#0078d4] border-t-transparent" />
            <span className="text-[12px] text-[#605e5c] dark:text-[#999]">Posponiendo {uids.length} correo{uids.length > 1 ? 's' : ''}...</span>
          </div>
        )}
      </div>
    </div>
  );
}
