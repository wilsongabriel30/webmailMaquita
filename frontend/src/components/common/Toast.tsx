import { useEffect, useState } from 'react';

interface ToastData {
  id: string;
  message: string;
  action?: { label: string; onClick: () => void };
}

let toastListener: ((t: ToastData) => void) | null = null;

export function showToast(message: string, action?: { label: string; onClick: () => void }) {
  const id = Math.random().toString(36).slice(2);
  toastListener?.({ id, message, action });
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

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastData[]>([]);

  useEffect(() => {
    toastListener = (t) => {
      setToasts(prev => [...prev, t]);
      setTimeout(() => setToasts(prev => prev.filter(x => x.id !== t.id)), 6000);
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
