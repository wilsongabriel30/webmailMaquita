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
// IMPORTANTE: El SW se auto-actualiza en cada carga de página.
// Al detectar nueva versión, recarga la página para aplicar cambios.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/webmail/sw.js")
      .then((reg) => {
        console.log("SW registered:", reg.scope);
        // Forzar check de actualizaciones cada vez que se carga
        reg.update();
        // Cuando hay un SW nuevo esperando, activarlo y recargar
        reg.addEventListener("updatefound", () => {
          const newSW = reg.installing;
          if (newSW) {
            newSW.addEventListener("statechange", () => {
              if (newSW.state === "activated" && navigator.serviceWorker.controller) {
                console.log("SW updated — reloading for new version");
                window.location.reload();
              }
            });
          }
        });
      })
      .catch((err) => console.error("SW registration failed:", err));
  });
  // Si el SW controlador cambia (otro tab activó nueva versión), recargar
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    window.location.reload();
  });
}
