import { useEffect, useState } from 'react';

interface ToastData {
  id: string;
  message: string;
  action?: { label: string; onClick: () => void };
  /** Si es true, no se cierra solo: queda hasta que la persona lo cierre (avisos de error importantes). */
  fijo?: boolean;
  /** Avisos con la misma clave se funden en uno (p. ej. «Enviados a la papelera: 3») en vez de apilarse. */
  clave?: string;
}

let toastListener: ((t: ToastData) => void) | null = null;

export function showToast(message: string, action?: { label: string; onClick: () => void }, opciones?: { fijo?: boolean; clave?: string }) {
  const id = Math.random().toString(36).slice(2);
  toastListener?.({ id, message, action, fijo: opciones?.fijo, clave: opciones?.clave });
  return id;
}

let updateListener: ((id: string, message: string) => void) | null = null;

export function updateToast(id: string, message: string) {
  updateListener?.(id, message);
}

let dismissListener: ((id: string) => void) | null = null;

export function dismissToast(id: string) {
  dismissListener?.(id);
}

/** Tiempo que un aviso no fijo permanece en pantalla. */
const DURACION_AVISO_MS = 10000;

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastData[]>([]);

  useEffect(() => {
    const temporizadores = new Map<string, ReturnType<typeof setTimeout>>();
    const programarCierre = (id: string) => {
      const previo = temporizadores.get(id);
      if (previo) clearTimeout(previo);
      temporizadores.set(id, setTimeout(() => { temporizadores.delete(id); setToasts(prev => prev.filter(x => x.id !== id)); }, DURACION_AVISO_MS));
    };
    toastListener = (t) => {
      setToasts(prev => {
        // Misma clave (borrar varios correos seguidos): se actualiza el aviso que ya está y se reinicia su tiempo (06/11/2026)
        const mismo = t.clave ? prev.find(x => x.clave === t.clave) : undefined;
        if (mismo) {
          programarCierre(mismo.id);
          return prev.map(x => x.id === mismo.id ? { ...x, message: t.message, action: t.action } : x);
        }
        return [...prev, t];
      });
      // 10 s: 6 s no alcanzaban para que una persona que lee despacio viera el aviso
      // (p. ej. un error al enviar). Los avisos con acción (Deshacer) duran lo mismo o son fijos.
      if (!t.fijo) programarCierre(t.id);
    };
    updateListener = (id, message) => {
      setToasts(prev => prev.map(x => x.id === id ? { ...x, message } : x));
    };
    dismissListener = (id) => {
      setToasts(prev => prev.filter(x => x.id !== id));
    };
    return () => { toastListener = null; updateListener = null; dismissListener = null; };
  }, []);

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
