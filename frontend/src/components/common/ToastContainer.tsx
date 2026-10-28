import { useEffect, useState } from 'react';
import { suscribirAvisos, type ToastData } from './Toast';

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastData[]>([]);

  useEffect(() => suscribirAvisos({
    mostrar: (t) => {
      setToasts(prev => [...prev, t]);
      if (!t.fijo) setTimeout(() => setToasts(prev => prev.filter(x => x.id !== t.id)), 6000);
    },
    actualizar: (id, message) => {
      setToasts(prev => prev.map(x => x.id === id ? { ...x, message } : x));
    },
    cerrar: (id) => {
      setToasts(prev => prev.filter(x => x.id !== id));
    },
  }), []);

  if (!toasts.length) return null;

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[9999] flex flex-col gap-2">
      {toasts.map(t => (
        <div key={t.id} className="bg-[#323130] text-white px-4 py-2.5 rounded-md shadow-lg flex items-center gap-3 text-[13px] min-w-[300px] animate-in slide-in-from-bottom duration-200">
          <span className="flex-1">{t.message}</span>
          {t.action && (
            <button onClick={() => { t.action!.onClick(); setToasts(prev => prev.filter(x => x.id !== t.id)); }}
              className="text-[#71afe5] hover:underline font-medium shrink-0">{t.action.label}</button>
          )}
          <button onClick={() => setToasts(prev => prev.filter(x => x.id !== t.id))}
            className="text-white/60 hover:text-white shrink-0">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}
