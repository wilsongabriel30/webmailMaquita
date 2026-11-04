import { useEffect, useState } from 'react';
import { suscribirAvisos, type ToastData } from './Toast';

/** Tiempo que un aviso no fijo permanece en pantalla. */
const DURACION_AVISO_MS = 10000;

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastData[]>([]);

  useEffect(() => suscribirAvisos({
    mostrar: (t) => {
      setToasts(prev => [...prev, t]);
      // 10 s: 6 s no alcanzaban para que una persona que lee despacio viera el aviso
      // (p. ej. un error al enviar). Los avisos con acción (Deshacer) duran lo mismo o son fijos.
      if (!t.fijo) setTimeout(() => setToasts(prev => prev.filter(x => x.id !== t.id)), DURACION_AVISO_MS);
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
        <div key={t.id} className="bg-[#323130] text-white px-4 py-2.5 rounded-md shadow-lg flex items-center gap-3 text-[14px] min-w-[300px] max-w-[calc(100vw-2rem)] animate-in slide-in-from-bottom duration-200">
          <span className="flex-1" role="status">{t.message}</span>
          {t.action && (
            <button onClick={() => { t.action!.onClick(); setToasts(prev => prev.filter(x => x.id !== t.id)); }}
              className="text-[#71afe5] hover:underline font-medium shrink-0">{t.action.label}</button>
          )}
          <button onClick={() => setToasts(prev => prev.filter(x => x.id !== t.id))}
            aria-label="Cerrar aviso" title="Cerrar aviso"
            className="text-white/70 hover:text-white shrink-0 p-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}
