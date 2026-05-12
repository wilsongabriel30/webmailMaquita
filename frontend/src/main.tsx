import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "./index.css"
import "./dark-theme.css"
import App from "./App"
import "./lib/syncQueue"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Register service worker for PWA / offline support
// Registro único: solo se registra una vez por sesión. Las actualizaciones
// se manejan con un banner en vez de recargas automáticas para evitar loops.
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
                // Mostrar banner discreto en vez de recargar automáticamente
                const banner = document.createElement("div");
                banner.id = "sw-update-banner";
                banner.style.cssText = "position:fixed;bottom:16px;left:50%;transform:translateX(-50%);z-index:9999;background:#0078d4;color:#fff;padding:8px 20px;border-radius:6px;font:13px/1.4 Calibri,sans-serif;display:flex;align-items:center;gap:12px;box-shadow:0 4px 12px rgba(0,0,0,.2)";
                banner.textContent = 'Nueva versión disponible ';
                const btn = document.createElement('button');
                btn.textContent = 'Actualizar';
                btn.style.cssText = 'margin-left:12px;padding:4px 16px;border:none;background:#fff;color:#0078d4;border-radius:4px;cursor:pointer;font-weight:600';
                btn.addEventListener('click', () => window.location.reload());
                banner.appendChild(btn);
                if (!document.getElementById("sw-update-banner")) {
                  document.body.appendChild(banner);
                }
              }
            });
          }
        });
      })
      .catch(() => {});
  });
}
