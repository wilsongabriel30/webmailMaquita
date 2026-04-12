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
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/webmail/sw.js")
      .then((reg) => console.log("SW registered:", reg.scope))
      .catch((err) => console.error("SW registration failed:", err));
  });
}
