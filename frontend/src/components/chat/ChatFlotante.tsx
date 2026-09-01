import { useEffect, useRef, useState } from "react";

/* Chat institucional flotante — disponible en TODAS las vistas del correo.
   - Se activa/desactiva y parametriza desde: Administracion -> Chat
     (endpoint publico /api/chat-config: { enabled, embed_url }).
   - Si esta desactivado por el admin, el boton NO aparece.
   - Autodetecta ademas si la instalacion tiene chat (/api/chat): si no responde,
     el boton tampoco aparece.
   - El icono BRILLA cuando hay mensajes nuevos sin leer (NO usa la campanita).
   - Brillo INSTANTANEO: el iframe del chat avisa por postMessage al llegar un
     mensaje (reutiliza el socket del chat). El iframe se monta oculto desde el
     inicio para estar conectado aunque el panel este cerrado. Un sondeo cada 15s
     corrige el conteo (respaldo). */

const POLL_MS = 15000;

export function ChatFlotante() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [embedUrl, setEmbedUrl] = useState("/chat/?embed=1");
  const [disponible, setDisponible] = useState(false);
  const [abierto, setAbierto] = useState(false);
  const [noLeidos, setNoLeidos] = useState(0);
  const abiertoRef = useRef(false);

  // 1) Config del panel de control (activado + URL).
  useEffect(() => {
    fetch("/api/chat-config", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d && typeof d.enabled === "boolean") {
          setEnabled(d.enabled);
          if (d.embed_url) setEmbedUrl(d.embed_url);
        } else setEnabled(true);
      })
      .catch(() => setEnabled(true));
  }, []);

  // 2) Autodeteccion de disponibilidad del backend de chat.
  //    Se re-chequea cada 60 s y al volver el foco. Si el token de sesion expiro
  //    (cookie de 1 h), se intenta refrescar y se reintenta, para que la burbuja
  //    NO desaparezca "sin explicacion" tras una hora de uso.
  useEffect(() => {
    if (enabled === false) return;
    let vivo = true;
    const comprobar = async () => {
      try {
        let r = await fetch("/api/chat/conversations?limit=1", { credentials: "include" });
        if (r.status === 401) {
          await fetch("/api/auth/refresh", { method: "POST", credentials: "include" }).catch(() => {});
          r = await fetch("/api/chat/conversations?limit=1", { credentials: "include" });
        }
        if (vivo) setDisponible(r.ok);
      } catch {
        if (vivo) setDisponible(false);
      }
    };
    comprobar();
    const t = setInterval(comprobar, 60000);
    const onFocus = () => comprobar();
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onFocus);
    return () => {
      vivo = false;
      clearInterval(t);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onFocus);
    };
  }, [enabled]);

  // Helper: recalcular no leidos desde el servidor.
  const refrescarNoLeidos = () => {
    fetch("/api/chat/conversations", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        const lista = d.conversaciones || d.conversations || [];
        const total = lista.reduce(
          (acc: number, c: any) => acc + (c.mensajes_no_leidos || c.unread_count || 0),
          0
        );
        setNoLeidos(abiertoRef.current ? 0 : total);
      })
      .catch(() => {});
  };

  // 3) Sondeo de respaldo (corrige el conteo y limpia al leer en otro lado).
  useEffect(() => {
    if (enabled === false || !disponible) return;
    refrescarNoLeidos();
    const t = setInterval(refrescarNoLeidos, POLL_MS);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, disponible]);

  // 4) Aviso INSTANTANEO desde el iframe del chat (postMessage) al llegar mensaje.
  useEffect(() => {
    function onMsg(e: MessageEvent) {
      if (e.origin !== window.location.origin) return;
      const d: any = e.data;
      if (d && d.source === "maquita-chat" && d.type === "nuevo-mensaje") {
        if (!abiertoRef.current) {
          setNoLeidos((n) => (n > 0 ? n : 1)); // brillo inmediato
          refrescarNoLeidos(); // luego corrige el numero real
        }
      }
    }
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggle = () => {
    setAbierto((v) => {
      const nv = !v;
      abiertoRef.current = nv;
      if (nv) setNoLeidos(0);
      return nv;
    });
  };

  if (enabled === false || !disponible) return null;

  const brilla = !abierto && noLeidos > 0;

  return (
    <>
      <style>{`
        @keyframes chatGlow {
          0%,100% { box-shadow: 0 4px 16px rgba(0,120,212,.45); }
          50%     { box-shadow: 0 0 0 6px rgba(0,120,212,.25), 0 4px 22px rgba(0,120,212,.85); }
        }
        .chat-fab-glow { animation: chatGlow 1.1s ease-in-out infinite; }
      `}</style>

      {/* Panel (el iframe se monta SIEMPRE y oculto, para estar conectado). */}
      <div style={{
        position: "fixed", bottom: 84, right: 20, width: 440, height: 640,
        maxWidth: "calc(100vw - 40px)", maxHeight: "calc(100vh - 120px)",
        borderRadius: 12, boxShadow: "0 8px 32px rgba(0,0,0,.28)",
        overflow: "hidden", zIndex: 9998, background: "#fff",
        display: abierto ? "block" : "none",
      }}>
        <iframe src={embedUrl} title="Chat institucional"
          style={{ width: "100%", height: "100%", border: 0 }} />
      </div>

      {/* Boton flotante */}
      <button onClick={toggle}
        className={brilla ? "chat-fab-glow" : undefined}
        title={abierto ? "Cerrar el chat" : (noLeidos > 0 ? `Tienes ${noLeidos} mensaje(s) nuevo(s)` : "Chat institucional")}
        style={{
          position: "fixed", bottom: 20, right: 20, width: 52, height: 52,
          borderRadius: "50%", border: 0, cursor: "pointer", zIndex: 9999,
          background: brilla ? "#0091ff" : "#0078d4", color: "#fff", fontSize: 22,
          boxShadow: "0 4px 16px rgba(0,120,212,.45)",
        }}>
        {abierto ? "✕" : "💬"}
        {brilla && (
          <span style={{
            position: "absolute", top: -3, right: -3, minWidth: 20, height: 20,
            padding: "0 5px", borderRadius: 10, background: "#e11", color: "#fff",
            fontSize: 12, lineHeight: "20px", fontWeight: 700,
            boxShadow: "0 0 0 2px #fff",
          }}>{noLeidos > 99 ? "99+" : noLeidos}</span>
        )}
      </button>
    </>
  );
}
