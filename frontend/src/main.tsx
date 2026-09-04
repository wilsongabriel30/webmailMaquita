import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "./lib/modoApp"
import "./index.css"
import "./dark-theme.css"
import App from "./App"
// T-49: PRIMERO se deja el caché del equipo cifrado y sin restos, y SOLO DESPUÉS se
// arrancan la cola de envío y la descarga sin conexión.
//
// El orden importa: borrar y recrear la base para que no queden restos de lo que antes se
// guardaba en claro es imposible mientras alguien la tenga abierta, y esos dos módulos la
// abren en cuanto se cargan. Por eso van con importación dinámica, después.
//
// Pase lo que pase con el cifrado, los dos se cargan: la cola de envío no puede quedarse
// sin arrancar por un asunto de higiene del disco.
import { migrarCacheACifrado, limpiarRestos } from "./lib/migracionCifrado"

async function prepararCacheLocal() {
  try {
    await migrarCacheACifrado()
    await limpiarRestos()
  } catch {
    /* se reintenta en el próximo arranque */
  }
}

prepararCacheLocal().finally(() => {
  import("./lib/syncQueue")
  import("./lib/descargaOffline")   // T-35: descarga proactiva del correo reciente
})

// Auto-recuperación de chunks tras un deploy: si falla la carga dinámica de un
// módulo (hash viejo en una pestaña abierta), recargar UNA vez para tomar la
// versión nueva. Guard en sessionStorage para no entrar en bucle.
window.addEventListener("vite:preloadError", (event) => {
  const key = "chunk-reload-" + window.location.pathname;
  if (!sessionStorage.getItem(key)) {
    sessionStorage.setItem(key, String(Date.now()));
    event.preventDefault();
    window.location.reload();
  }
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Register service worker for PWA / offline support
// Registro único: solo se registra una vez por sesión. Las actualizaciones
// se manejan con un banner en vez de recargas automáticas para evitar loops.
// Reset PWA install dismiss if not installed (allows re-prompt after uninstall)
if (!window.matchMedia('(display-mode: standalone)').matches) {
  const dismissed = localStorage.getItem('pwa-install-dismissed');
  if (dismissed && Date.now() - parseInt(dismissed) > 24 * 60 * 60 * 1000) {
    localStorage.removeItem('pwa-install-dismissed');
  }
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/webmail/sw.js")
      .then((reg) => {
        // Check for updates cada 30 min (no en cada carga)
        setInterval(() => reg.update(), 30 * 60 * 1000);

        reg.addEventListener("updatefound", () => {
          const newSW = reg.installing;
          if (newSW) {
            newSW.addEventListener("statechange", () => {
              // Solo notificar si ya hay un SW activo (no es primera instalación)
              if (newSW.state === "installed" && navigator.serviceWorker.controller) {
                // Nueva version: actualizar SOLA (2026-09-01). Aviso sin boton +
                // recarga automatica; si el usuario esta escribiendo, se espera.
                if ((window as any).__swReloadScheduled) return;
                (window as any).__swReloadScheduled = true;
                if (!document.getElementById("sw-update-banner")) {
                  const aviso = document.createElement("div");
                  aviso.id = "sw-update-banner";
                  aviso.style.cssText = "position:fixed;bottom:16px;left:50%;transform:translateX(-50%);z-index:9999;background:#0078d4;color:#fff;padding:8px 20px;border-radius:6px;font:13px/1.4 Calibri,sans-serif;box-shadow:0 4px 12px rgba(0,0,0,.2)";
                  aviso.textContent = "Actualizando a la nueva versión…";
                  document.body.appendChild(aviso);
                }
                const _editing = () => {
                  const el = document.activeElement as HTMLElement | null;
                  if (!el) return false;
                  const tag = (el.tagName || "").toLowerCase();
                  return tag === "input" || tag === "textarea" || el.isContentEditable === true;
                };
                const _tryReload = () => {
                  if (_editing()) { setTimeout(_tryReload, 4000); return; }
                  try { window.location.reload(); } catch { /* noop */ }
                };
                setTimeout(_tryReload, 2500);
              }
            });
          }
        });
      })
      .catch(() => {});
  });
}

// Listen for SW messages (offline outbox queuing)
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.addEventListener('message', async (event) => {
    if (event.data?.type === 'queue-outbox') {
      const { addToOutbox } = await import('./lib/offlineStore');
      await addToOutbox(event.data.payload);
    }
    if (event.data?.type === 'trigger-sync') {
      const { syncAll } = await import('./lib/syncQueue');
      const result = await syncAll();
      if (result.sent > 0 || result.actions > 0) {
        window.dispatchEvent(new CustomEvent('offline-sync-complete', { detail: result }));
        window.dispatchEvent(new CustomEvent('refresh-messages'));
      }
    }
  });
}

