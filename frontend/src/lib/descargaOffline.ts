// T-35 · Correo sin conexión, como Outlook: descarga PROACTIVA de los últimos N días (recibidos y enviados) con cuerpos
// y adjuntos pequeños, para leerlos sin internet. Los cuerpos van a IndexedDB (offlineStore) y, además, el service worker
// guarda las respuestas de /api/mail/message y /api/mail/attachment, así que abrir un adjunto ya bajado funciona sin red.
// Corre sola al iniciar (tras 8 s) y cada 10 min; es incremental (no repite lo ya bajado) y se detiene si se pierde la red.
import { cacheFullMessage, getCachedMessage, type OfflineMessage } from './offlineStore';

export interface EstadoDescarga {
  activa: boolean; carpeta: string; hechos: number; total: number; adjuntos: number; ultima: number | null; error: string;
  dias: number; adjMB: number;
}

const CARPETAS = ['INBOX', 'Sent'];
const PAUSA_MS = 120;
const est: EstadoDescarga = { activa: false, carpeta: '', hechos: 0, total: 0, adjuntos: 0, ultima: null, error: '', dias: 30, adjMB: 5 };

function leerCfg() {
  try {
    est.dias = Math.min(60, Math.max(7, parseInt(localStorage.getItem('offline.dias') || '30', 10) || 30));
    est.adjMB = Math.min(25, Math.max(0, parseInt(localStorage.getItem('offline.adjMB') || '5', 10)));
  } catch { /* valores por defecto */ }
}
export function configurarDescarga(dias: number, adjMB: number) {
  try { localStorage.setItem('offline.dias', String(dias)); localStorage.setItem('offline.adjMB', String(adjMB)); } catch { /* sin almacenamiento */ }
  leerCfg(); emitir();
}
export function estadoDescarga(): EstadoDescarga { return { ...est }; }
function emitir() { window.dispatchEvent(new CustomEvent('offline-descarga', { detail: { ...est } })); }
const dormir = (ms: number) => new Promise(r => setTimeout(r, ms));

async function pedir<T>(url: string): Promise<T | null> {
  const r = await fetch(url, { credentials: 'include' });
  if (r.status === 401) throw new Error('sin sesión');
  if (!r.ok) return null;
  return r.json();
}

async function descargarAdjuntos(folder: string, uid: number, adj: OfflineMessage['attachments']) {
  for (const a of adj || []) {
    if (!a || a.is_inline || !a.size || a.size > est.adjMB * 1024 * 1024) continue;
    if (!navigator.onLine) return;
    try {
      // El service worker guarda la respuesta en su caché de API; solo hay que pedirla una vez.
      const r = await fetch(`/api/mail/attachment/${encodeURIComponent(folder)}/${uid}/${a.part_number}/${encodeURIComponent(a.filename)}`, { credentials: 'include' });
      if (r.ok) { await r.blob(); est.adjuntos++; }
    } catch { /* se reintenta en el próximo ciclo */ }
    await dormir(PAUSA_MS);
  }
}

type Bajable = OfflineMessage & { adjuntosBajados?: boolean };

export async function descargarAhora(): Promise<EstadoDescarga> {
  if (est.activa || !navigator.onLine) return estadoDescarga();
  leerCfg();
  est.activa = true; est.error = ''; est.hechos = 0; est.total = 0; emitir();
  const desde = Date.now() - est.dias * 86400000;
  try {
    for (const carpeta of CARPETAS) {
      if (!navigator.onLine) break;
      est.carpeta = carpeta; emitir();
      const lista = await pedir<{ messages: Array<{ uid: number; date: string | null; has_attachments: boolean }> }>(
        `/api/mail/messages/${encodeURIComponent(carpeta)}?page=1&per_page=300`);
      if (!lista) continue;
      const recientes = lista.messages.filter(m => !m.date || new Date(m.date).getTime() >= desde);
      est.total += recientes.length; emitir();
      for (const m of recientes) {
        if (!navigator.onLine) break;
        try {
          const ya = (await getCachedMessage(carpeta, m.uid)) as Bajable | null;
          if (ya && (ya.html_body || ya.text_body)) {
            if (m.has_attachments && ya.attachments?.length && !ya.adjuntosBajados) {
              await descargarAdjuntos(carpeta, m.uid, ya.attachments);
              await cacheFullMessage(carpeta, { ...ya, adjuntosBajados: true } as OfflineMessage);
            }
          } else {
            const full = await pedir<Record<string, unknown>>(`/api/mail/message/${encodeURIComponent(carpeta)}/${m.uid}`);
            if (full) {
              const reg = { ...full, id: `${carpeta}:${m.uid}`, uid: m.uid, folder: carpeta, cachedAt: Date.now() } as unknown as Bajable;
              await descargarAdjuntos(carpeta, m.uid, reg.attachments);
              reg.adjuntosBajados = true;
              await cacheFullMessage(carpeta, reg);
            }
          }
        } catch (e) {
          if (String((e as Error)?.message).includes('sin sesión')) { est.error = 'sin sesión'; est.activa = false; emitir(); return estadoDescarga(); }
        }
        est.hechos++; if (est.hechos % 5 === 0) emitir();
        await dormir(PAUSA_MS);
      }
    }
    est.ultima = Date.now();
    try { localStorage.setItem('offline.ultima', String(est.ultima)); } catch { /* sin almacenamiento */ }
  } catch (e) {
    est.error = (e as Error)?.message || 'error';
  } finally {
    est.activa = false; est.carpeta = ''; emitir();
  }
  return estadoDescarga();
}

// Arranque automático: a los 8 s de cargar y luego cada 10 min; también al recuperar la red.
if (typeof window !== 'undefined') {
  leerCfg();
  try { const u = localStorage.getItem('offline.ultima'); if (u) est.ultima = parseInt(u, 10); } catch { /* sin almacenamiento */ }
  setTimeout(() => { descargarAhora(); }, 8000);
  setInterval(() => { descargarAhora(); }, 10 * 60 * 1000);
  window.addEventListener('online', () => setTimeout(() => descargarAhora(), 4000));
  // Gancho para el candado (humo) y para soporte: window.__maquitaOffline
  Promise.all([import('./offlineStore'), import('./syncQueue')]).then(([store, sq]) => {
    (window as unknown as Record<string, unknown>).__maquitaOffline = { descargarAhora, estadoDescarga, configurarDescarga, ...store, ...sq };
  }).catch(() => { /* opcional */ });
}
