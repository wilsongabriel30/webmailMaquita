// @ts-nocheck
import * as React from "react";

// Captura cualquier error de runtime de una seccion. Estrategia:
//  - Guarda SIEMPRE el detalle completo (message + stack + componentStack) en
//    consola y en localStorage["_eb_last_error"] para diagnostico posterior.
//  - Auto-recarga UNA vez por "episodio" (>30s desde la ultima recarga): los
//    errores transitorios (extension del navegador, parpadeo de red, render
//    race) se curan solos sin asustar al usuario. Si el error reaparece a los
//    pocos segundos de recargar = es persistente: se muestra la pantalla con el
//    stack completo para reportarlo.
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null, info: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    const detail = {
      message: (error && error.message) || String(error),
      stack: (error && error.stack) || null,
      componentStack: (info && info.componentStack) || null,
      url: location.href,
      ua: navigator.userAgent,
      ts: new Date().toISOString(),
    };
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary] seccion fallo:", detail);
    try { localStorage.setItem("_eb_last_error", JSON.stringify(detail)); } catch (e) {}

    this.setState({ info });

    const last = Number(sessionStorage.getItem("_eb_reload_ts") || 0);
    const now = Date.now();
    if (now - last > 30000) {
      // Transitorio: recarga una sola vez por episodio.
      sessionStorage.setItem("_eb_reload_ts", String(now));
      location.reload();
    }
    // Si <30s desde la ultima recarga => persistente: NO recargar, mostrar detalle.
  }

  render() {
    if (this.state.error) {
      const e = this.state.error;
      const info = this.state.info;
      const detalle =
        String((e && e.message) || e) +
        ((e && e.stack) ? "\n\n" + e.stack : "") +
        ((info && info.componentStack) ? "\n\nComponente:" + info.componentStack : "");
      return (
        <div style={{ padding: 40, fontFamily: "Segoe UI, sans-serif", color: "#323130", maxWidth: 760 }}>
          <h2 style={{ color: "#a4262c", marginBottom: 8 }}>Algo falló en esta sección</h2>
          <p style={{ color: "#605e5c" }}>
            Pulsa <b>Recargar</b> para continuar. Si vuelve a pasar, copia o haz captura del <b>detalle de abajo completo</b> y envíalo al equipo de Tecnología.
          </p>
          <button
            onClick={() => {
              sessionStorage.removeItem("_eb_reload_ts");
              window.location.href = "/";
            }}
            style={{ background: "#0078d4", color: "#fff", border: 0, padding: "10px 20px", borderRadius: 6, cursor: "pointer", fontSize: 14 }}
          >
            Recargar el panel
          </button>
          <pre style={{ marginTop: 24, color: "#605e5c", fontSize: 12, whiteSpace: "pre-wrap", background: "#f3f2f1", padding: 12, borderRadius: 6, maxHeight: 360, overflow: "auto" }}>
            {detalle}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}
