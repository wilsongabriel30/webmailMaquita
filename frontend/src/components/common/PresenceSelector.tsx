import { useState, useRef, useEffect } from 'react';
import { usePresence } from '../../hooks/usePresence';
import { PresenceDot } from './PresenceDot';

const STATUSES = [
  { value: 'online', label: 'Disponible', color: '#10b981' },
  { value: 'busy', label: 'Ocupado', color: '#ef4444' },
  { value: 'away', label: 'Ausente', color: '#f59e0b' },
  { value: 'offline', label: 'Desconectado', color: '#94a3b8' },
] as const;

export function PresenceSelector() {
  const { users, setStatus } = usePresence();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Get own status - find by matching current user
  const myEmail = document.cookie.match(/user=([^;]+)/)?.[1] || '';
  const myPresence = users[myEmail];
  const currentStatus = myPresence?.status || 'online';

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1.5 px-2 py-1 rounded hover:bg-black/10 transition-colors">
        <PresenceDot status={currentStatus} size={8} />
        <span className="text-xs text-white hidden sm:inline">{STATUSES.find(s => s.value === currentStatus)?.label}</span>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 bg-white rounded-lg shadow-lg border border-slate-200 py-1 z-50 min-w-[160px]">
          {STATUSES.map(s => (
            <button key={s.value}
              onClick={() => { setStatus(s.value); setOpen(false); }}
              className={`w-full flex items-center gap-2.5 px-3 py-2 text-sm hover:bg-slate-50 ${currentStatus === s.value ? 'font-medium' : ''}`}>
              <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: s.color }} />
              {s.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
