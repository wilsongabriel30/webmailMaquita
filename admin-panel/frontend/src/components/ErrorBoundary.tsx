// @ts-nocheck
import * as React from "react";

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error) {
    if (
      /dynamically imported module|Loading chunk|Failed to fetch|importing a module/i.test((error && error.message) || "") &&
      !sessionStorage.getItem("_eb_reloaded")
    ) {
      sessionStorage.setItem("_eb_reloaded", "1");
      window.location.reload();
    }
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 40, fontFamily: "Segoe UI, sans-serif", color: "#323130", maxWidth: 760 }}>
          <h2 style={{ color: "#a4262c", marginBottom: 8 }}>Algo falló en esta sección</h2>
          <p style={{ color: "#605e5c" }}>
            Pulsa <b>Recargar</b> para continuar. Si vuelve a pasar, avisa al equipo de Tecnología con el detalle de abajo.
          </p>
          <button
            onClick={() => {
              sessionStorage.removeItem("_eb_reloaded");
              window.location.href = "/";
            }}
            style={{ background: "#0078d4", color: "#fff", border: 0, padding: "10px 20px", borderRadius: 6, cursor: "pointer", fontSize: 14 }}
          >
            Recargar el panel
          </button>
          <pre style={{ marginTop: 24, color: "#605e5c", fontSize: 12, whiteSpace: "pre-wrap", background: "#f3f2f1", padding: 12, borderRadius: 6 }}>
            {String((this.state.error && this.state.error.message) || this.state.error)}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}
